"""Guided tools: formulation classifier, ABS checklist, TKDL pointer."""

from fastapi import APIRouter, HTTPException, Query

from app.domain.abs_checklist import build_checklist
from app.domain.classifier import step as classify_step
from app.domain.tkdl import build_pointer
from app.schemas.tools import (
    ABSRequest,
    ABSResponse,
    ClassifyRequest,
    ClassifyResponse,
    TKDLPointerResponse,
)

router = APIRouter(tags=["tools"])


@router.post("/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest):
    try:
        result = classify_step(req.answers)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ClassifyResponse(path_so_far=req.answers, **result)


@router.post("/abs-checklist", response_model=ABSResponse)
def abs_checklist(req: ABSRequest):
    return ABSResponse(checklist=build_checklist(req))


@router.get("/tkdl-pointer", response_model=TKDLPointerResponse)
def tkdl_pointer(query: str = Query(..., min_length=2, max_length=300)):
    return build_pointer(query)
