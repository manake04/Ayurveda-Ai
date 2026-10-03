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
            return httpx.Response(400, json={"error": {"message": "Thinking budget is not supported"}})
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
