"""Pydantic request/response schemas for the API."""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Jurisdiction = Literal["india", "international", "both"]
Language = Literal["en", "hi"]


class Citation(BaseModel):
    id: str
    title: str
    instrument: str
    citation: str
    jurisdiction: str
    regime: str
    source_url: str
    source_name: str
    last_verified: str
    score: float
    full_text_excerpt: Optional[str] = None


class RelatedCitation(Citation):
    relation: str
    hops: int


class JurisdictionAnswer(BaseModel):
    jurisdiction: str
    label: Optional[str] = None  # display override, e.g. "India — Patent law" for an agentic step
    answer_text: str
    citations: List[Citation]
    graph_related: List[RelatedCitation] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"]
    abstained: bool


class AgenticStep(BaseModel):
    step_index: int
    jurisdiction: str
    regime: Optional[str] = None
    reason: str


class AgenticAnswer(BaseModel):
    query: str
    disclaimer: str
    plan_summary: str
    steps: List[AgenticStep]
    sections: List[JurisdictionAnswer]


class AskRequest(BaseModel):
    query: str = Field(..., min_length=3, description="The user's IP/regulatory question")
    jurisdiction: Jurisdiction = "india"
    language: Language = "en"
    top_k: Optional[int] = None


class AskResponse(BaseModel):
    query: str
    disclaimer: str
    answers: List[JurisdictionAnswer]


class ClassifyRequest(BaseModel):
    answers: List[str] = Field(default_factory=list, description="Answers given so far, in order ('yes'/'no')")


class ClassifyResponse(BaseModel):
    done: bool
    question_id: Optional[str] = None
    question_text: Optional[str] = None
    options: Optional[List[str]] = None
    result: Optional[dict] = None
    path_so_far: List[str] = Field(default_factory=list)


class ABSRequest(BaseModel):
    uses_biological_material: bool
    sourced_from_india: bool
    ip_or_commercialisation_sought: bool
    user_is_registered_ayush_practitioner: bool = False
    knowledge_is_codified_traditional_knowledge: bool = False
    exporting_or_partnering_abroad: bool = False


class ABSResponseItem(BaseModel):
    step: str
    applies: bool
    detail: str
    citation_ids: List[str]


class ABSResponse(BaseModel):
    checklist: List[ABSResponseItem]
    disclaimer: str


class TKDLPointerResponse(BaseModel):
    query: str
    guidance: str
    search_links: List[dict]
    citation: Citation


class ConnectorConsentRequest(BaseModel):
    connector_name: str
    granted: bool
    user_note: Optional[str] = None


class ConnectorConsentResponse(BaseModel):
    connector_name: str
    granted: bool
    logged_at: str
    message: str


class AuditEntry(BaseModel):
    timestamp: str
    endpoint: str
    jurisdiction: Optional[str] = None
    summary: str


class GraphNode(BaseModel):
    id: str
    node_type: str
    label: str
    jurisdiction: Optional[str] = None
    regime: Optional[str] = None
    source_url: Optional[str] = None


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: Optional[str] = None


class GraphExportResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class GraphRelatedNode(BaseModel):
    id: str
    node_type: str
    label: str
    relation: Optional[str] = None
    hops: int = 0
    jurisdiction: Optional[str] = None
    regime: Optional[str] = None
    source_url: Optional[str] = None


class GraphRelatedResponse(BaseModel):
    node_id: str
    related: List[GraphRelatedNode]


class GraphPathResponse(BaseModel):
    source: str
    target: str
    path: Optional[List[GraphRelatedNode]] = None
    found: bool
