"""Request/response models for the question-answering endpoints."""

from typing import Literal

from pydantic import BaseModel, Field

JurisdictionChoice = Literal["india", "international", "both"]
Language = Literal["auto", "en", "hi"]
Confidence = Literal["high", "medium", "low"]


class AskRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=2000)
    jurisdiction: JurisdictionChoice = "india"
    language: Language = "auto"


class Citation(BaseModel):
    """A corpus document the answer is grounded in. `ref` is the [n] marker used in the text."""

    ref: int
    id: str
    title: str
    instrument: str
    citation: str
    jurisdiction: str
    regime: str
    summary: str
    source_url: str
    source_name: str
    last_verified: str
    score: float
    full_text_excerpt: str | None = None


class RelatedSource(BaseModel):
    """A document linked to a cited one in the knowledge graph (not retrieved directly)."""

    id: str
    title: str
    citation: str
    instrument: str
    source_url: str
    relation: str


class JurisdictionAnswer(BaseModel):
    jurisdiction: Literal["india", "international"]
    answer: str
    confidence: Confidence
    abstained: bool
    citations: list[Citation]
    related: list[RelatedSource] = Field(default_factory=list)
    generated_by: str  # "gemini:<model>", "ollama:<model>", or "extractive"


class AskResponse(BaseModel):
    query: str
    answers: list[JurisdictionAnswer]
    disclaimer: str
    latency_ms: int
