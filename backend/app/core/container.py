"""Builds the long-lived services once at startup and shares them across requests."""

import logging
from dataclasses import dataclass

import httpx

from app.core.config import Settings
from app.i18n.bhashini import BhashiniTranslator
from app.knowledge.graph import GraphStore
from app.llm import LLM, create_llms
from app.rag.pipeline import RAGPipeline
from app.retrieval.corpus import Document, load_corpus
from app.retrieval.embeddings import create_embedder
from app.retrieval.reranker import CrossEncoderReranker
from app.retrieval.retriever import Retriever
from app.retrieval.vector_store import load_or_build
from app.store import Store

log = logging.getLogger(__name__)


@dataclass
class Container:
    settings: Settings
    http: httpx.AsyncClient
    docs: list[Document]
    graph: GraphStore
    retriever: Retriever
    llms: list[LLM]
    pipeline: RAGPipeline
    store: Store
    translator: BhashiniTranslator | None = None

    @classmethod
    async def create(cls, settings: Settings) -> "Container":
        http = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0))
        docs = load_corpus(settings.corpus_dir)
        graph = GraphStore.build(docs, settings.corpus_dir / "graph_edges.json")

        embedder = create_embedder(settings, http)
        store = await load_or_build(settings.index_dir, docs, embedder)
        reranker = CrossEncoderReranker(settings.reranker_model) if settings.reranker_model else None
        retriever = Retriever(settings, store, embedder, reranker)

        llms = create_llms(settings, http)
        translator = BhashiniTranslator(settings, http) if settings.bhashini_enabled else None
        pipeline = RAGPipeline(settings, retriever, graph, llms, translator)

        store = Store(settings.database_path, settings.audit_store_query_text)
        purged = store.purge_older_than(settings.audit_retention_days)
        log.info(
            "Ready: %d documents, embeddings=%s, reranker=%s, llms=%s, bhashini=%s, purged %d old records",
            len(docs),
            embedder.name,
            settings.reranker_model or "off",
            [llm.name for llm in llms] or "extractive",
            "on" if translator else "off",
            purged,
        )
        return cls(settings, http, docs, graph, retriever, llms, pipeline, store, translator)

    async def close(self) -> None:
        await self.http.aclose()
        self.store.close()
