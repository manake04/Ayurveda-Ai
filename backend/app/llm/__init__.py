"""Answer-generation models. Pick one with LLM_PROVIDER (gemini | ollama | none)."""

import logging

import httpx

from app.core.config import Settings
from app.llm.base import LLM, LLMError
from app.llm.gemini import GeminiLLM
from app.llm.ollama import OllamaLLM

log = logging.getLogger(__name__)


def create_llm(settings: Settings, client: httpx.AsyncClient) -> LLM | None:
    """Return the configured model, or None for extractive (no-LLM) answers."""
    if settings.llm_provider == "gemini":
        if not settings.gemini_api_key:
            log.warning("GEMINI_API_KEY is not set -- answers will be quoted from sources (extractive)")
            return None
        return GeminiLLM(settings, client)
    if settings.llm_provider == "ollama":
        return OllamaLLM(settings, client)
    return None


__all__ = ["LLM", "LLMError", "create_llm"]
