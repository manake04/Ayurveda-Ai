"""Retrieval: embed the query once, search FAISS, split by jurisdiction, optionally rerank."""

from dataclasses import dataclass
from typing import Literal

from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.retrieval.corpus import Document, document_text
from app.retrieval.embeddings import Embedder
from app.retrieval.reranker import Reranker
from app.retrieval.vector_store import VectorStore

Jurisdiction = Literal["india", "international"]
_LABEL = {"india": "India", "international": "International"}


@dataclass
class RetrievalResult:
    jurisdiction: Jurisdiction
    hits: list[tuple[Document, float]]  # best first
    confidence: Literal["high", "medium", "low"]

    @property
    def abstained(self) -> bool:
        return self.confidence == "low"


class Retriever:
    def __init__(
        self,
        settings: Settings,
        store: VectorStore,
        embedder: Embedder,
        reranker: Reranker | None = None,
    ):
        self.settings = settings
        self.store = store
        self.embedder = embedder
        self.reranker = reranker

    async def retrieve(
        self, query: str, jurisdictions: list[Jurisdiction]
    ) -> dict[Jurisdiction, RetrievalResult]:
        s = self.settings
        query_vector = await self.embedder.embed_query(query)
        # One search over the whole corpus, then partition: cheaper than one per jurisdiction.
        ranked = self.store.search(query_vector, k=len(self.store.docs))

        results: dict[Jurisdiction, RetrievalResult] = {}
        for jurisdiction in jurisdictions:
            hits = [(d, sc) for d, sc in ranked if d["jurisdiction"] == _LABEL[jurisdiction]]
            if self.reranker is not None:
                hits = await self._rerank(query, hits[: s.rerank_candidates])
                high, abstain = s.rerank_confidence_high, s.rerank_confidence_abstain
            else:
                high, abstain = s.confidence_high, s.confidence_abstain
            hits = hits[: s.top_k]
            top = hits[0][1] if hits else float("-inf")
            confidence = "high" if top >= high else "medium" if top >= abstain else "low"
            results[jurisdiction] = RetrievalResult(jurisdiction, hits, confidence)
        return results

    async def _rerank(self, query: str, hits: list[tuple[Document, float]]) -> list[tuple[Document, float]]:
        if not hits:
            return hits
        texts = [document_text(d) for d, _ in hits]
        scores = await run_in_threadpool(self.reranker.score, query, texts)
        return sorted(((d, sc) for (d, _), sc in zip(hits, scores, strict=False)), key=lambda x: -x[1])
