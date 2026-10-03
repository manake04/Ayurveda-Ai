"""The interface every answer-generating model implements."""

from collections.abc import AsyncIterator
from typing import Protocol


class LLMError(RuntimeError):
    """Raised when the model can't produce an answer (network, quota, bad key...)."""


class LLM(Protocol):
    name: str

    def stream(self, system: str, prompt: str) -> AsyncIterator[str]:
        """Yield the answer as text chunks, as soon as the model produces them."""
        ...

    async def complete_json(self, system: str, prompt: str, schema: dict) -> dict:
        """Return a JSON object matching `schema` (a plain JSON Schema)."""
        ...
