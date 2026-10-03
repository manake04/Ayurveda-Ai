"""Google Gemini via the REST API, no SDK needed."""

import asyncio
import json
from collections.abc import AsyncIterator

import httpx

from app.core.config import Settings
from app.llm.base import LLMError

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_TRANSIENT = {429, 500, 502, 503, 504}


def _gemini_schema(schema: dict) -> dict:
    """Gemini's responseSchema uses upper-case type names (OBJECT, STRING...)."""
    out = {}
    for key, value in schema.items():
        if key == "type":
            out[key] = value.upper()
        elif key == "properties":
            out[key] = {k: _gemini_schema(v) for k, v in value.items()}
        elif key == "items":
            out[key] = _gemini_schema(value)
        elif key in ("required", "enum", "description", "minItems", "maxItems"):
            out[key] = value
    return out


class GeminiLLM:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        if not settings.gemini_api_key:
            raise LLMError("LLM_PROVIDER=gemini requires GEMINI_API_KEY in backend/.env")
        self.name = f"gemini:{settings.gemini_model}"
        self._model_url = f"{_BASE}/{settings.gemini_model}"
        self._headers = {"x-goog-api-key": settings.gemini_api_key}
        self._settings = settings
        self._client = client
        # Some Gemini models reject a thinking budget; see _retry_delay.
        self._send_thinking_config = settings.gemini_thinking_budget >= 0
        self.backoff = (1.0, 3.0)  # waits before retrying a 429/5xx

    def _payload(self, system: str, prompt: str, **generation_extra) -> dict:
        generation = {
            "temperature": self._settings.llm_temperature,
            "maxOutputTokens": self._settings.llm_max_output_tokens,
            **generation_extra,
        }
        if self._send_thinking_config:
            generation["thinkingConfig"] = {"thinkingBudget": self._settings.gemini_thinking_budget}
        return {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": generation,
        }

    def _retry_delay(self, status: int, state: dict) -> float | None:
        """Seconds to wait before retrying a failed request, or None to give up.

        - 429/5xx (e.g. 503 "model is experiencing high demand") are usually brief:
          retry after a short backoff before the caller falls back to another model.
        - Some models reject a thinking budget with a plain 400 that doesn't say so:
          retry once without it, and keep it off only if that retry gets past the 400.
        """
        if status == 400 and self._send_thinking_config and not state["dropped_thinking"]:
            self._send_thinking_config = False
            state["dropped_thinking"] = True
            return 0.0
        if status == 400 and state["dropped_thinking"]:
            self._send_thinking_config = self._settings.gemini_thinking_budget >= 0
            return None
        if status in _TRANSIENT and state["transient"] < len(self.backoff):
            state["transient"] += 1
            return self.backoff[state["transient"] - 1]
        return None

    async def stream(self, system: str, prompt: str) -> AsyncIterator[str]:
        state = {"dropped_thinking": False, "transient": 0}
        try:
            while True:
                async with self._client.stream(
                    "POST",
                    f"{self._model_url}:streamGenerateContent?alt=sse",
                    headers=self._headers,
                    json=self._payload(system, prompt),
                    timeout=self._settings.llm_timeout_seconds,
                ) as resp:
                    if resp.status_code != 200:
                        body = (await resp.aread()).decode("utf-8", "replace")
                        delay = self._retry_delay(resp.status_code, state)
                        if delay is None:
                            raise LLMError(f"Gemini returned HTTP {resp.status_code}: {body[:300]}")
                        await asyncio.sleep(delay)
                        continue
                    async for line in resp.aiter_lines():
                        if line.startswith("data:"):
                            for text in _texts(json.loads(line[5:])):
                                yield text
                    return
        except httpx.HTTPError as exc:
            raise LLMError(f"Gemini request failed: {exc}") from exc

    async def complete_json(self, system: str, prompt: str, schema: dict) -> dict:
        extra = {"responseMimeType": "application/json", "responseSchema": _gemini_schema(schema)}
        state = {"dropped_thinking": False, "transient": 0}
        try:
            while True:
                resp = await self._client.post(
                    f"{self._model_url}:generateContent",
                    headers=self._headers,
                    json=self._payload(system, prompt, **extra),
                    timeout=self._settings.llm_timeout_seconds,
                )
                if resp.status_code == 200:
                    return json.loads("".join(_texts(resp.json())))
                delay = self._retry_delay(resp.status_code, state)
                if delay is None:
                    raise LLMError(f"Gemini returned HTTP {resp.status_code}: {resp.text[:300]}")
                await asyncio.sleep(delay)
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError(f"Gemini JSON request failed: {exc}") from exc


def _texts(chunk: dict) -> list[str]:
    """Answer text parts of a Gemini response, skipping any "thought" parts."""
    return [
        part["text"]
        for candidate in chunk.get("candidates", [])
        for part in candidate.get("content", {}).get("parts", [])
        if part.get("text") and not part.get("thought")
    ]
