"""Health and corpus metadata."""

from collections import Counter

from fastapi import APIRouter

from app.api.deps import ContainerDep
from app.core.config import DISCLAIMER
from app.i18n import BHASHINI_LANGUAGES, NATIVE_LANGUAGES

router = APIRouter(tags=["meta"])


@router.get("/health")
def health(c: ContainerDep):
    return {
        "status": "ok",
        "documents": len(c.docs),
        "embeddings": c.retriever.embedder.name,
        "reranker": c.settings.reranker_model or None,
        "llms": [llm.name for llm in c.llms] or ["extractive"],
    }


@router.get("/config")
def config(c: ContainerDep):
    """What the UI needs to know about this deployment."""
    s = c.settings
    languages = [{"code": "auto", "label": "Auto"}] + [
        {"code": k, "label": v} for k, v in NATIVE_LANGUAGES.items()
    ]
    if c.translator is not None:
        languages += [{"code": k, "label": v} for k, v in BHASHINI_LANGUAGES.items()]
    return {
        "disclaimer": DISCLAIMER,
        "languages": languages,
        "bhashini": c.translator is not None,
        "agentic": bool(c.llms),
        "escalation": {
            "name": s.escalation_name or None,
            "email": s.escalation_email or None,
            "url": s.escalation_url or "https://ipindia.gov.in/",
            "url_label": "IP facilitation"
            if s.escalation_url
            else "Find a registered patent / trade-mark agent",
        },
    }


@router.get("/corpus/stats")
def corpus_stats(c: ContainerDep):
    return {
        "documents": len(c.docs),
        "by_jurisdiction": Counter(d["jurisdiction"] for d in c.docs),
        "by_regime": Counter(d["regime"] for d in c.docs),
    }
