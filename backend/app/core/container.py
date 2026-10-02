"""Builds the long-lived services once at startup and shares them across requests."""

import logging
from dataclasses import dataclass

import httpx

from app.core.config import Settings
from app.knowledge.graph import GraphStore
from app.llm import LLM, create_llm
from app.rag.pipeline import RAGPipeline
from app.retrieval.corpus import Document, load_corpus
from app.retrieval.embeddings import create_embedder
from app.retrieval.reranker import CrossEncoderReranker
from app.retrieval.retriever import Retriever
from app.retrieval.vector_store import load_or_build

log = logging.getLogger(__name__)


@dataclass
class Container:
    settings: Settings
    http: httpx.AsyncClient
    docs: list[Document]
    graph: GraphStore
    retriever: Retriever
    llm: LLM | None
    pipeline: RAGPipeline

    @classmethod
    async def create(cls, settings: Settings) -> "Container":
        http = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0))
        docs = load_corpus(settings.corpus_dir)
        graph = GraphStore.build(docs, settings.corpus_dir / "graph_edges.json")

        embedder = create_embedder(settings, http)
        store = await load_or_build(settings.index_dir, docs, embedder)
        reranker = CrossEncoderReranker(settings.reranker_model) if settings.reranker_model else None
        retriever = Retriever(settings, store, embedder, reranker)

        llm = create_llm(settings, http)
        log.info(
            "Ready: %d documents, embeddings=%s, reranker=%s, llm=%s",
            len(docs),
            embedder.name,
            settings.reranker_model or "off",
            llm.name if llm else "extractive",
        )
        return cls(settings, http, docs, graph, retriever, llm, RAGPipeline(settings, retriever, graph, llm))

    async def close(self) -> None:
        await self.http.aclose()
