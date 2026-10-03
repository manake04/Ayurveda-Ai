"""A local model served by Ollama (`/api/chat`)."""

import json
from collections.abc import AsyncIterator

import httpx

from app.core.config import Settings
from app.llm.base import LLMError


class OllamaLLM:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.name = f"ollama:{settings.ollama_llm_model}"
        self._url = settings.ollama_base_url.rstrip("/") + "/api/chat"
        self._settings = settings
        self._client = client

    def _payload(self, system: str, prompt: str, **extra) -> dict:
        return {
            "model": self._settings.ollama_llm_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "think": False,  # answer directly; thinking is slow and isn't shown anyway
            "keep_alive": self._settings.ollama_keep_alive,
            "options": {
                "temperature": self._settings.llm_temperature,
                "num_predict": self._settings.llm_max_output_tokens,
            },
            **extra,
        }

    async def stream(self, system: str, prompt: str) -> AsyncIterator[str]:
        try:
            async with self._client.stream(
                "POST",
                self._url,
                json=self._payload(system, prompt, stream=True),
                timeout=self._settings.ollama_timeout_seconds,
            ) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode("utf-8", "replace")
                    raise LLMError(f"Ollama returned HTTP {resp.status_code}: {body[:300]}")
                async for line in resp.aiter_lines():
                    if line:
                        text = json.loads(line).get("message", {}).get("content")
                        if text:
                            yield text
        except httpx.HTTPError as exc:
            raise LLMError(f"Ollama request failed: {exc!r}") from exc

    async def complete_json(self, system: str, prompt: str, schema: dict) -> dict:
        # Ollama's `format` isn't honoured by every model (qwen3.5 with thinking off replies
        # in prose), so the schema is also spelled out in the prompt and parsed leniently.
        system = (
            f"{system}\n\nReply with only a JSON object, no other text, matching this JSON Schema:\n"
            f"{json.dumps(schema)}"
        )
        try:
            resp = await self._client.post(
                self._url,
                json=self._payload(system, prompt, stream=False, format=schema),
                timeout=self._settings.ollama_timeout_seconds,
            )
            if resp.status_code != 200:
                raise LLMError(f"Ollama returned HTTP {resp.status_code}: {resp.text[:300]}")
            return _parse_json_object(resp.json()["message"]["content"])
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise LLMError(f"Ollama JSON request failed: {exc!r}") from exc


def _parse_json_object(text: str) -> dict:
    """The JSON object in a model reply, tolerating code fences or text around it."""
    text = text.strip()
    try:
        value = json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError(f"no JSON object in reply: {text[:120]!r}") from None
        value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object, got {type(value).__name__}")
    return value
