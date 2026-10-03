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
    database_path: Path = BACKEND_DIR / "data" / "app.db"

    # --- LLM (answer generation) ---
    llm_provider: Literal["gemini", "ollama", "none"] = "gemini"
    # Used when the primary model fails before producing any text (quota, network...).
    llm_fallback_provider: Literal["gemini", "ollama", "none"] = "none"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"
    # 0 disables "thinking" on Gemini 2.5-class models (much lower latency); -1 omits the
    # setting entirely and lets the model decide.
    gemini_thinking_budget: int = 0
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_llm_model: str = "qwen3.5:latest"
    # How long Ollama keeps a model in memory after a request. Reloading a large model
    # costs ~10 s, so keep it warm well beyond Ollama's 5-minute default.
    ollama_keep_alive: str = "30m"
    llm_temperature: float = 0.2
    llm_max_output_tokens: int = 1024
    # Max wait between chunks. Local CPU models can take a minute to start answering.
    llm_timeout_seconds: float = 60.0
    ollama_timeout_seconds: float = 300.0

    # --- Embeddings ---
    embedding_provider: Literal["ollama", "gemini"] = "ollama"
    embedding_model: str = "qwen3-embedding:8b-q8_0"
    # Instruction prefixes the embedding model was trained with. Defaults match
    # Qwen3-Embedding; see .env.example for other models.
    embedding_query_prefix: str = (
        "Instruct: Given a question about intellectual property or regulation of Ayurvedic "
        "products, retrieve the legal provisions that answer it\nQuery: "
    )
    embedding_document_prefix: str = ""

    # --- Reranker (optional cross-encoder; empty string disables it) ---
    reranker_model: str = ""
    rerank_candidates: int = 12

    # --- Retrieval ---
    top_k: int = 5
    # Similarity of the best hit: below `abstain` the assistant declines to answer.
    # Model-specific -- re-tune with `python -m eval.run_eval` after changing models.
    confidence_high: float = 0.72
    confidence_abstain: float = 0.615
    # When the reranker is enabled, its raw scores are used instead.
    rerank_confidence_high: float = 2.0
    rerank_confidence_abstain: float = -4.0
    answer_cache_size: int = 256

    # --- Agentic (deep research) mode ---
    agentic_max_steps: int = 3
    agentic_max_sources: int = 8

    # --- Privacy / audit (DPDP) ---
    # Audit events store a hash and length of the question, not its text, unless enabled.
    audit_store_query_text: bool = False
    audit_retention_days: int = 90

    # --- Escalation to a human IP facilitator ---
    escalation_name: str = ""
    escalation_email: str = ""
    escalation_url: str = ""
    # If set, each escalation ticket is also POSTed here as JSON (e.g. a helpdesk or chat hook).
    escalation_webhook_url: str = ""

    # --- Bhashini (translation for languages beyond English/Hindi) ---
    bhashini_user_id: str = ""
    bhashini_api_key: str = ""
    bhashini_pipeline_id: str = ""
    bhashini_config_url: str = "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"

    # --- HTTP ---
    # Comma-separated list of allowed browser origins.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def bhashini_enabled(self) -> bool:
        return bool(self.bhashini_user_id and self.bhashini_api_key and self.bhashini_pipeline_id)

    @field_validator("corpus_dir", "index_dir", "database_path", mode="after")
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
