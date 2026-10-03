"""Answer-generation models.

LLM_PROVIDER picks the primary model and LLM_FALLBACK_PROVIDER an optional second one
(gemini | ollama | none). The pipeline tries them in order.
"""

import logging

import httpx

from app.core.config import Settings
from app.llm.base import LLM, LLMError
from app.llm.gemini import GeminiLLM
from app.llm.ollama import OllamaLLM

log = logging.getLogger(__name__)


def _create(provider: str, settings: Settings, client: httpx.AsyncClient) -> LLM | None:
    if provider == "gemini":
        if not settings.gemini_api_key:
            log.warning("GEMINI_API_KEY is not set -- skipping Gemini")
            return None
        return GeminiLLM(settings, client)
    if provider == "ollama":
        return OllamaLLM(settings, client)
    return None


def create_llms(settings: Settings, client: httpx.AsyncClient) -> list[LLM]:
    """Configured models in the order to try them. Empty means extractive answers only."""
    llms: list[LLM] = []
    for provider in (settings.llm_provider, settings.llm_fallback_provider):
        llm = _create(provider, settings, client)
        if llm is not None and all(existing.name != llm.name for existing in llms):
            llms.append(llm)
    if not llms:
        log.warning("No LLM configured -- answers will be quoted from sources (extractive)")
    return llms


async def complete_json(llms: list[LLM], system: str, prompt: str, schema: dict) -> dict:
    """complete_json on the first model that succeeds."""
    errors = []
    for llm in llms:
        try:
            return await llm.complete_json(system, prompt, schema)
        except LLMError as exc:
            log.warning("%s failed on a JSON request: %s", llm.name, exc)
            errors.append(f"{llm.name}: {exc}")
    raise LLMError("; ".join(errors) or "no LLM configured")


__all__ = ["LLM", "LLMError", "complete_json", "create_llms"]
