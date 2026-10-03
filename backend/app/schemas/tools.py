"""Models for the guided tools: formulation classifier, ABS checklist, TKDL pointer."""

from pydantic import BaseModel, Field


class ClassifyRequest(BaseModel):
    answers: list[str] = Field(default_factory=list, description="'yes'/'no' answers so far, in order")


class ClassifyResponse(BaseModel):
    done: bool
    question_id: str | None = None
    question_text: str | None = None
    options: list[str] | None = None
    result: dict | None = None
    path_so_far: list[str] = Field(default_factory=list)


class ABSRequest(BaseModel):
    uses_biological_material: bool
    sourced_from_india: bool
    ip_or_commercialisation_sought: bool
    user_is_registered_ayush_practitioner: bool = False
    knowledge_is_codified_traditional_knowledge: bool = False
    exporting_or_partnering_abroad: bool = False


class ABSChecklistItem(BaseModel):
    step: str
    applies: bool
    detail: str
    citation_ids: list[str]


class ABSResponse(BaseModel):
    checklist: list[ABSChecklistItem]


class SearchLink(BaseModel):
    name: str
    url: str
    note: str


class TKDLPointerResponse(BaseModel):
    query: str
    guidance: str
    search_links: list[SearchLink]
    tkdl_source_url: str
