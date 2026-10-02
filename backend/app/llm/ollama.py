"""A local model served by Ollama (`/api/chat`, streamed)."""

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

    async def stream(self, system: str, prompt: str) -> AsyncIterator[str]:
        payload = {
            "model": self._settings.ollama_llm_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": True,
            "think": False,
            "options": {
                "temperature": self._settings.llm_temperature,
                "num_predict": self._settings.llm_max_output_tokens,
            },
        }
        try:
            async with self._client.stream(
                "POST", self._url, json=payload, timeout=self._settings.llm_timeout_seconds
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
            raise LLMError(f"Ollama request failed: {exc}") from exc
