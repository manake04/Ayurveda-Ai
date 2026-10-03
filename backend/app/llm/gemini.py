"""Google Gemini via the REST API (server-sent events), no SDK needed."""

import json
from collections.abc import AsyncIterator

import httpx

from app.core.config import Settings
from app.llm.base import LLMError

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiLLM:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        if not settings.gemini_api_key:
            raise LLMError("LLM_PROVIDER=gemini requires GEMINI_API_KEY in backend/.env")
        self.name = f"gemini:{settings.gemini_model}"
        self._url = f"{_BASE}/{settings.gemini_model}:streamGenerateContent?alt=sse"
        self._headers = {"x-goog-api-key": settings.gemini_api_key}
        self._settings = settings
        self._client = client
        # Some Gemini models reject a thinking budget; drop it after the first refusal.
        self._send_thinking_config = settings.gemini_thinking_budget >= 0

    def _payload(self, system: str, prompt: str) -> dict:
        generation = {
            "temperature": self._settings.llm_temperature,
            "maxOutputTokens": self._settings.llm_max_output_tokens,
        }
        if self._send_thinking_config:
            generation["thinkingConfig"] = {"thinkingBudget": self._settings.gemini_thinking_budget}
        return {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": generation,
        }

    async def stream(self, system: str, prompt: str) -> AsyncIterator[str]:
        try:
            for attempt in range(2):
                async with self._client.stream(
                    "POST",
                    self._url,
                    headers=self._headers,
                    json=self._payload(system, prompt),
                    timeout=self._settings.llm_timeout_seconds,
                ) as resp:
                    if resp.status_code != 200:
                        body = (await resp.aread()).decode("utf-8", "replace")
                        if (
                            attempt == 0
                            and resp.status_code == 400
                            and self._send_thinking_config
                            and "thinking" in body.lower()
                        ):
                            self._send_thinking_config = False
                            continue
                        raise LLMError(f"Gemini returned HTTP {resp.status_code}: {body[:300]}")
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        chunk = json.loads(line[5:])
                        for candidate in chunk.get("candidates", []):
                            for part in candidate.get("content", {}).get("parts", []):
                                if part.get("text") and not part.get("thought"):
                                    yield part["text"]
                    return
        except httpx.HTTPError as exc:
            raise LLMError(f"Gemini request failed: {exc}") from exc
