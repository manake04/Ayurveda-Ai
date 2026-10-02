"""FastAPI app for IP-SAKTI Sahayak."""
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import audit, config
from app.abs_helper import build_checklist
from app.agent import run_agentic
from app.classifier import step as classify_step
from app.graph import get_graph_store
from app.i18n import get_ui_strings, translate_via_bhashini
from app.connectors import get_consents, set_consent
from app.models import (
    ABSRequest,
    ABSResponse,
    AgenticAnswer,
    AskRequest,
    AskResponse,
    ClassifyRequest,
    ClassifyResponse,
    ConnectorConsentRequest,
    ConnectorConsentResponse,
    CorpusVerifyReportResponse,
    GraphExportResponse,
    GraphPathResponse,
    GraphRelatedResponse,
    SourceInfo,
)
from app.ingest.sources import SOURCE_REGISTRY
from app.rag import ask as rag_ask
from app.tkdl import build_pointer
from app.vectorstore import get_store

app = FastAPI(
    title="IP-SAKTI Sahayak API",
    description="Multilingual, RAG-based, source-cited IP & regulatory guidance for Ayurveda (MVP).",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    store = get_store(config.CORPUS_DIR, config.INDEX_DIR, config.DENSE_DIR)
    return {
        "status": "ok",
        "corpus_documents": len(store.docs),
        "dense_retrieval_active": store.dense is not None,
        "disclaimer": config.DISCLAIMER,
    }


@app.get("/corpus/stats")
def corpus_stats():
    store = get_store(config.CORPUS_DIR, config.INDEX_DIR, config.DENSE_DIR)
    by_jurisdiction: dict = {}
    by_regime: dict = {}
    for doc in store.docs:
        by_jurisdiction[doc["jurisdiction"]] = by_jurisdiction.get(doc["jurisdiction"], 0) + 1
        by_regime[doc["regime"]] = by_regime.get(doc["regime"], 0) + 1
    return {
        "total_documents": len(store.docs),
        "by_jurisdiction": by_jurisdiction,
        "by_regime": by_regime,
    }


@app.get("/corpus/sources", response_model=list[SourceInfo])
def corpus_sources():
    """The registry of authoritative public sources the corpus is assembled from
    (see app/ingest/sources.py and scripts/ingest.py)."""
    return [
        SourceInfo(
            id=s.id,
            name=s.name,
            display_name=s.display_name,
            jurisdiction=s.jurisdiction,
            homepage=s.homepage,
            fetch_kind=s.fetch_kind,
            automatable=s.automatable,
            locator_help=s.locator_help,
            access_notes=s.access_notes,
        )
        for s in SOURCE_REGISTRY.values()
    ]


@app.get("/corpus/verify", response_model=CorpusVerifyReportResponse)
def corpus_verify():
    """The most recent corpus-verification report. Read-only and offline — it never
    hits the network from a request. Run `python scripts/ingest.py verify` to refresh it."""
    path = config.VERIFY_REPORT_PATH
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail="No verification report yet. Run: cd backend && python scripts/ingest.py verify",
        )
    audit.log_event(endpoint="/corpus/verify", summary=f"served report from {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/i18n/{language}")
def i18n_strings(language: str):
    return get_ui_strings(language)


@app.post("/i18n/translate")
def i18n_translate(text: str, target_lang: str):
    return translate_via_bhashini(text, target_lang)


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    store = get_store(config.CORPUS_DIR, config.INDEX_DIR, config.DENSE_DIR)
    graph_store = get_graph_store(config.CORPUS_DIR, config.GRAPH_EDGES_PATH, config.GRAPH_DIR)
    top_k = req.top_k or config.TOP_K
    try:
        answers = rag_ask(store, req.query, req.jurisdiction, top_k, graph_store)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    audit.log_event(
        endpoint="/ask",
        jurisdiction=req.jurisdiction,
        summary=f"query='{req.query}' -> confidences={[a.confidence for a in answers]}",
    )

    return AskResponse(query=req.query, disclaimer=config.DISCLAIMER, answers=answers)


@app.post("/ask/agentic", response_model=AgenticAnswer)
def ask_agentic(req: AskRequest):
    """Multi-step version of /ask: plans a small sequence of retrieval (+ graph-expansion)
    steps instead of one lookup, for compound questions that span jurisdictions and/or
    multiple legal regimes. See app/agent.py for how the (rule-based, no-LLM-required)
    planner decides how many steps to run."""
    store = get_store(config.CORPUS_DIR, config.INDEX_DIR, config.DENSE_DIR)
    graph_store = get_graph_store(config.CORPUS_DIR, config.GRAPH_EDGES_PATH, config.GRAPH_DIR)
    top_k = req.top_k or config.TOP_K
    try:
        result = run_agentic(store, graph_store, req.query, req.jurisdiction, top_k)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    audit.log_event(
        endpoint="/ask/agentic",
        jurisdiction=req.jurisdiction,
        summary=f"query='{req.query}' -> {len(result.steps)} step(s), plan='{result.plan_summary}'",
    )
    return result


@app.post("/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest):
    try:
        result = classify_step(req.answers)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    audit.log_event(
        endpoint="/classify",
        summary=f"answers={req.answers} -> done={result['done']} category={(result['result'] or {}).get('category')}",
    )
    return ClassifyResponse(path_so_far=req.answers, **result)


@app.post("/abs-helper", response_model=ABSResponse)
def abs_helper(req: ABSRequest):
    checklist = build_checklist(req)
    audit.log_event(endpoint="/abs-helper", summary=f"request={req.model_dump()}")
    return ABSResponse(checklist=checklist, disclaimer=config.DISCLAIMER)


@app.get("/tkdl-pointer")
def tkdl_pointer(query: str):
    result = build_pointer(query)
    audit.log_event(endpoint="/tkdl-pointer", summary=f"query='{query}'")
    return result


@app.post("/connectors/consent", response_model=ConnectorConsentResponse)
def connectors_consent(req: ConnectorConsentRequest):
    return set_consent(req)


@app.get("/connectors/consent")
def connectors_consent_status():
    return get_consents()


@app.get("/audit/recent")
def audit_recent(limit: int = 20):
    return audit.read_recent(limit=limit)


@app.get("/graph/export", response_model=GraphExportResponse)
def graph_export():
    """Full knowledge graph, for the frontend's force-directed visualisation."""
    graph_store = get_graph_store(config.CORPUS_DIR, config.GRAPH_EDGES_PATH, config.GRAPH_DIR)
    return graph_store.export()


@app.get("/graph/node/{node_id}/related", response_model=GraphRelatedResponse)
def graph_related(node_id: str, hops: int = 1):
    graph_store = get_graph_store(config.CORPUS_DIR, config.GRAPH_EDGES_PATH, config.GRAPH_DIR)
    if graph_store.node(node_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown graph node id: {node_id}")
    return GraphRelatedResponse(node_id=node_id, related=graph_store.related(node_id, hops=hops))


@app.get("/graph/path", response_model=GraphPathResponse)
def graph_path(source: str, target: str):
    graph_store = get_graph_store(config.CORPUS_DIR, config.GRAPH_EDGES_PATH, config.GRAPH_DIR)
    path = graph_store.path(source, target)
    return GraphPathResponse(source=source, target=target, path=path, found=path is not None)
