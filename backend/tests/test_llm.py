"""Gemini and Ollama clients against a mocked HTTP transport."""

import json

import httpx
import pytest

from app.llm import LLMError
from app.llm.gemini import GeminiLLM
from app.llm.ollama import OllamaLLM


def sse(*texts):
    lines = [
        f"data: {json.dumps({'candidates': [{'content': {'parts': [{'text': t}]}}]})}\n\n" for t in texts
    ]
    return "".join(lines).encode()


def client_for(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def collect(llm):
    return [t async for t in llm.stream("system", "prompt")]


async def test_gemini_streams_text_and_skips_thoughts(settings):
    def handler(request):
        assert request.headers["x-goog-api-key"] == "k"
        body = sse("Hello ", "world") + (
            b'data: {"candidates":[{"content":{"parts":[{"text":"hidden","thought":true}]}}]}\n\n'
        )
        return httpx.Response(200, content=body)

    llm = GeminiLLM(settings.model_copy(update={"gemini_api_key": "k"}), client_for(handler))
    assert await collect(llm) == ["Hello ", "world"]


async def test_gemini_retries_without_thinking_config_when_rejected(settings):
    payloads = []

    def handler(request):
        payload = json.loads(request.content)
        payloads.append(payload)
        if "thinkingConfig" in payload["generationConfig"]:
            return httpx.Response(400, json={"error": {"message": "Request contains an invalid argument."}})
        return httpx.Response(200, content=sse("ok"))

    llm = GeminiLLM(settings.model_copy(update={"gemini_api_key": "k"}), client_for(handler))
    assert await collect(llm) == ["ok"]
    assert len(payloads) == 2
    assert await collect(llm) == ["ok"]  # remembered: no second refusal
    assert len(payloads) == 3


async def test_gemini_error_raises_llm_error(settings):
    llm = GeminiLLM(
        settings.model_copy(update={"gemini_api_key": "bad"}),
        client_for(lambda r: httpx.Response(403, json={"error": {"message": "API key not valid"}})),
    )
    with pytest.raises(LLMError, match="403"):
        await collect(llm)


async def test_ollama_streams_chat_chunks(settings):
    def handler(request):
        lines = [{"message": {"content": "a"}}, {"message": {"content": "b"}}, {"done": True}]
        return httpx.Response(200, content="\n".join(json.dumps(x) for x in lines).encode())

    assert await collect(OllamaLLM(settings, client_for(handler))) == ["a", "b"]


async def test_gemini_complete_json_sends_schema_and_parses(settings):
    def handler(request):
        payload = json.loads(request.content)
        assert request.url.path.endswith(":generateContent")
        gen = payload["generationConfig"]
        assert gen["responseMimeType"] == "application/json"
        assert gen["responseSchema"]["type"] == "OBJECT"
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"steps": []}'}]}}]})

    llm = GeminiLLM(settings.model_copy(update={"gemini_api_key": "k"}), client_for(handler))
    assert await llm.complete_json("s", "p", {"type": "object", "properties": {}}) == {"steps": []}


async def test_ollama_sends_think_false_and_keep_alive(settings):
    def handler(request):
        payload = json.loads(request.content)
        assert payload["think"] is False and payload["keep_alive"] == settings.ollama_keep_alive
        assert payload["format"] == {"type": "object"}
        return httpx.Response(200, json={"message": {"content": '{"ok": true}'}})

    llm = OllamaLLM(settings, client_for(handler))
    assert await llm.complete_json("s", "p", {"type": "object"}) == {"ok": True}


async def test_complete_json_tries_models_in_order(settings):
    from app.llm import complete_json
    from tests.conftest import FakeLLM

    assert await complete_json([FakeLLM(fail=True), FakeLLM(plan={"steps": [1]})], "s", "p", {}) == {
        "steps": [1]
    }
    with pytest.raises(LLMError):
        await complete_json([FakeLLM(fail=True)], "s", "p", {})


async def test_gemini_keeps_thinking_config_when_retry_also_fails(settings):
    payloads = []

    def handler(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(400, json={"error": {"message": "bad request"}})

    llm = GeminiLLM(settings.model_copy(update={"gemini_api_key": "k"}), client_for(handler))
    with pytest.raises(LLMError):
        await collect(llm)
    assert len(payloads) == 2
    assert "thinkingConfig" in payloads[0]["generationConfig"]
    assert "thinkingConfig" not in payloads[1]["generationConfig"]
    with pytest.raises(LLMError):
        await collect(llm)
    assert "thinkingConfig" in payloads[2]["generationConfig"]  # the 400 wasn't about thinking


async def test_gemini_retries_transient_errors_then_succeeds(settings):
    statuses = iter([503, 429, 200])

    def handler(request):
        status = next(statuses)
        if status != 200:
            return httpx.Response(status, json={"error": {"message": "high demand"}})
        return httpx.Response(200, content=sse("ok"))

    llm = GeminiLLM(settings.model_copy(update={"gemini_api_key": "k"}), client_for(handler))
    llm.backoff = (0, 0)
    assert await collect(llm) == ["ok"]


async def test_gemini_gives_up_after_backoff_is_exhausted(settings):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503, json={"error": {"message": "high demand"}})

    llm = GeminiLLM(settings.model_copy(update={"gemini_api_key": "k"}), client_for(handler))
    llm.backoff = (0, 0)
    with pytest.raises(LLMError, match="503"):
        await llm.complete_json("s", "p", {"type": "object"})
    assert len(calls) == 3


@pytest.mark.parametrize(
    "content",
    ['{"steps": []}', '```json\n{"steps": []}\n```', 'Here is the plan:\n{"steps": []}\nDone.'],
)
async def test_ollama_json_tolerates_text_around_the_object(settings, content):
    def handler(request):
        assert "JSON Schema" in json.loads(request.content)["messages"][0]["content"]
        return httpx.Response(200, json={"message": {"content": content}})

    assert await OllamaLLM(settings, client_for(handler)).complete_json("s", "p", {"type": "object"}) == {
        "steps": []
    }


async def test_ollama_json_prose_reply_is_an_llm_error(settings):
    def handler(request):
        return httpx.Response(200, json={"message": {"content": "1. First question\n2. Second question"}})

    with pytest.raises(LLMError):
        await OllamaLLM(settings, client_for(handler)).complete_json("s", "p", {"type": "object"})
