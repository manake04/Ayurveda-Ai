"""Application settings, read from environment variables and `backend/.env`."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    # --- Paths ---
    corpus_dir: Path = BACKEND_DIR.parent / "corpus"
    index_dir: Path = BACKEND_DIR / "data" / "index"

    # --- LLM (answer generation) ---
    llm_provider: Literal["gemini", "ollama", "none"] = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"
    # 0 disables "thinking" on Gemini 2.5-class models (much lower latency); -1 omits the
    # setting entirely and lets the model decide.
    gemini_thinking_budget: int = 0
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_llm_model: str = "qwen3:8b"
    llm_temperature: float = 0.2
    llm_max_output_tokens: int = 1024
    llm_timeout_seconds: float = 60.0

    # --- Embeddings ---
    embedding_provider: Literal["ollama", "gemini"] = "ollama"
    embedding_model: str = "embeddinggemma"
    # Instruction prefixes the embedding model was trained with. Defaults match
    # embeddinggemma; see .env.example for other models.
    embedding_query_prefix: str = "task: search result | query: "
    embedding_document_prefix: str = "title: none | text: "

    # --- Reranker (optional cross-encoder; empty string disables it) ---
    reranker_model: str = ""
    rerank_candidates: int = 12

    # --- Retrieval ---
    top_k: int = 5
    # Similarity of the best hit: below `abstain` the assistant declines to answer.
    # Model-specific -- re-tune with `python -m eval.run_eval` after changing models.
    confidence_high: float = 0.50
    confidence_abstain: float = 0.30
    # When the reranker is enabled, its raw scores are used instead.
    rerank_confidence_high: float = 2.0
    rerank_confidence_abstain: float = -4.0
    answer_cache_size: int = 256

    # --- HTTP ---
    # Comma-separated list of allowed browser origins.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @field_validator("corpus_dir", "index_dir", mode="after")
    @classmethod
    def _resolve(cls, value: Path) -> Path:
        return value if value.is_absolute() else (BACKEND_DIR / value).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()


DISCLAIMER = (
    "IP-SAKTI Sahayak provides general information about Indian and international IP and "
    "regulatory frameworks relevant to Ayurveda. It is not legal advice. Verify against the "
    "cited primary source and consult a qualified IP attorney or registered patent/trade-mark "
    "agent before making a filing, commercial or compliance decision."
)
