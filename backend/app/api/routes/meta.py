"""Health and corpus metadata."""

from collections import Counter

from fastapi import APIRouter

from app.api.deps import ContainerDep
from app.core.config import DISCLAIMER

router = APIRouter(tags=["meta"])


@router.get("/health")
def health(c: ContainerDep):
    return {
        "status": "ok",
        "documents": len(c.docs),
        "embeddings": c.retriever.embedder.name,
        "reranker": c.settings.reranker_model or None,
        "llm": c.llm.name if c.llm else "extractive",
        "disclaimer": DISCLAIMER,
    }


@router.get("/corpus/stats")
def corpus_stats(c: ContainerDep):
    return {
        "documents": len(c.docs),
        "by_jurisdiction": Counter(d["jurisdiction"] for d in c.docs),
        "by_regime": Counter(d["regime"] for d in c.docs),
    }
