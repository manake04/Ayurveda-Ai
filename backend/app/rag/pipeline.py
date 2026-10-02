"""The question-answering pipeline: retrieve -> generate (streamed) -> cite.

Every answer is grounded in documents actually retrieved from the corpus. The model sees
only those documents, numbered [1]..[n], and any [n] it emits that doesn't match a
retrieved document is removed before the final answer is returned.
"""

import asyncio
import logging
import re
import time
from collections import OrderedDict
from collections.abc import AsyncIterator

from app.core.config import DISCLAIMER, Settings
from app.knowledge.graph import GraphStore
from app.llm import LLM, LLMError
from app.rag import prompts
from app.retrieval.corpus import Document
from app.retrieval.retriever import Jurisdiction, RetrievalResult, Retriever
from app.schemas.ask import (
    AskRequest,
    AskResponse,
    Citation,
    JurisdictionAnswer,
    RelatedSource,
)

log = logging.getLogger(__name__)

Event = dict  # {"type": "sources" | "delta" | "done" | "end", ...}

# Graph relations worth surfacing next to an answer. Excludes the auto-derived
# document->concept edges (regime, jurisdiction, category), which aren't citable sources.
_RELATED_RELATIONS = {
    "SUPPORTS",
    "ENFORCES",
    "APPLIES_ALONGSIDE",
    "DETAILS",
    "IMPLEMENTS",
    "REINFORCED_BY",
    "RELATED_TO",
    "COMPLEMENTS",
    "CONSTRAINED_BY",
    "LABELLING_GOVERNED_BY",
    "ENFORCED_BY",
    "ALTERNATIVE_TO",
    "INTERNATIONAL_COUNTERPART",
    "INTERNATIONAL_ROUTE",
    "GOVERNED_BY_BASELINE",
    "PRIORITY_GOVERNED_BY",
    "ALTERNATIVE_STRATEGY",
    "ANALOGOUS_TO",
    "UMBRELLA_OVER",
}
_REF = re.compile(r"\[(\d+)\]")


class RAGPipeline:
    def __init__(
        self,
        settings: Settings,
        retriever: Retriever,
        graph: GraphStore,
        llm: LLM | None,
    ):
        self.settings = settings
        self.retriever = retriever
        self.graph = graph
        self.llm = llm
        self._docs_by_id = {d["id"]: d for d in retriever.store.docs}
        self._cache: OrderedDict[tuple, list[JurisdictionAnswer]] = OrderedDict()

    # ---- public API ----

    async def stream(self, req: AskRequest) -> AsyncIterator[Event]:
        """Yield events as the answer is produced: sources first, then text deltas."""
        started = time.perf_counter()
        jurisdictions: list[Jurisdiction] = (
            ["india", "international"] if req.jurisdiction == "both" else [req.jurisdiction]
        )
        key = (" ".join(req.query.lower().split()), req.jurisdiction, req.language)

        cached = self._cache_get(key)
        if cached is not None:
            for answer in cached:
                yield self._sources_event(answer)
                yield {
                    "type": "done",
                    **answer.model_dump(include={"jurisdiction", "answer", "generated_by"}),
                }
        else:
            results = await self.retriever.retrieve(req.query, jurisdictions)
            answers: list[JurisdictionAnswer] = []
            async for event in self._generate_all(req, results, answers):
                yield event
            if all(not a.generated_by.endswith("(fallback)") for a in answers):
                self._cache_put(key, sorted(answers, key=lambda a: jurisdictions.index(a.jurisdiction)))

        yield {"type": "end", "latency_ms": int((time.perf_counter() - started) * 1000)}

    async def answer(self, req: AskRequest) -> AskResponse:
        """Non-streaming variant: run the stream to completion and collect the result."""
        answers: dict[str, dict] = {}
        latency = 0
        async for event in self.stream(req):
            if event["type"] == "sources":
                answers[event["jurisdiction"]] = {k: v for k, v in event.items() if k != "type"}
            elif event["type"] == "done":
                answers[event["jurisdiction"]].update(
                    answer=event["answer"], generated_by=event["generated_by"]
                )
            elif event["type"] == "end":
                latency = event["latency_ms"]
        return AskResponse(
            query=req.query,
            answers=[JurisdictionAnswer(**a) for a in answers.values()],
            disclaimer=DISCLAIMER,
            latency_ms=latency,
        )

    # ---- generation ----

    async def _generate_all(
        self,
        req: AskRequest,
        results: dict[Jurisdiction, RetrievalResult],
        answers: list[JurisdictionAnswer],
    ) -> AsyncIterator[Event]:
        """Run one generation per jurisdiction concurrently, interleaving their events."""
        queue: asyncio.Queue = asyncio.Queue()

        async def run(result: RetrievalResult) -> None:
            try:
                async for event in self._generate_one(req, result, answers):
                    await queue.put(event)
            finally:
                await queue.put(None)

        tasks = [asyncio.create_task(run(r)) for r in results.values()]
        try:
            remaining = len(tasks)
            while remaining:
                event = await queue.get()
                if event is None:
                    remaining -= 1
                else:
                    yield event
        finally:
            for task in tasks:
                task.cancel()

    async def _generate_one(
        self, req: AskRequest, result: RetrievalResult, answers: list[JurisdictionAnswer]
    ) -> AsyncIterator[Event]:
        jurisdiction = result.jurisdiction
        citations = [self._citation(n, doc, score) for n, (doc, score) in enumerate(result.hits, 1)]
        answer = JurisdictionAnswer(
            jurisdiction=jurisdiction,
            answer="",
            confidence=result.confidence,
            abstained=result.abstained,
            citations=[] if result.abstained else citations,
            related=[] if result.abstained else self._related(result),
            generated_by="none",
        )
        yield self._sources_event(answer)

        if result.abstained:
            answer.answer = prompts.ABSTENTION_TEXT[jurisdiction]
        elif self.llm is None:
            answer.answer = prompts.extractive_answer(result.hits)
            answer.generated_by = "extractive"
        else:
            parts: list[str] = []
            try:
                async for text in self.llm.stream(
                    prompts.build_system_prompt(req.language),
                    prompts.build_user_prompt(req.query, jurisdiction, result.hits),
                ):
                    parts.append(text)
                    yield {"type": "delta", "jurisdiction": jurisdiction, "text": text}
                answer.answer = self._strip_unknown_refs("".join(parts), len(citations))
                answer.generated_by = self.llm.name
            except LLMError as exc:
                log.warning("LLM failed, falling back to extractive answer: %s", exc)
                answer.answer = prompts.extractive_answer(result.hits)
                answer.generated_by = "extractive (fallback)"

        answers.append(answer)
        yield {"type": "done", **answer.model_dump(include={"jurisdiction", "answer", "generated_by"})}

    # ---- helpers ----

    @staticmethod
    def _sources_event(answer: JurisdictionAnswer) -> Event:
        return {
            "type": "sources",
            **answer.model_dump(include={"jurisdiction", "confidence", "abstained", "citations", "related"}),
        }

    @staticmethod
    def _strip_unknown_refs(text: str, n_sources: int) -> str:
        return _REF.sub(lambda m: m.group(0) if 1 <= int(m.group(1)) <= n_sources else "", text)

    @staticmethod
    def _citation(ref: int, doc: Document, score: float) -> Citation:
        return Citation(
            ref=ref,
            score=round(score, 4),
            **{k: doc.get(k) for k in Citation.model_fields if k not in ("ref", "score")},
        )

    def _related(self, result: RetrievalResult, limit: int = 4) -> list[RelatedSource]:
        """Documents linked in the knowledge graph to the top two hits, same jurisdiction."""
        label = "India" if result.jurisdiction == "india" else "International"
        seen = {doc["id"] for doc, _ in result.hits}
        related: list[RelatedSource] = []
        for doc, _ in result.hits[:2]:
            for node in self.graph.related(doc["id"], hops=1):
                if (
                    node["node_type"] != "document"
                    or node["relation"] not in _RELATED_RELATIONS
                    or node["id"] in seen
                    or node.get("jurisdiction") != label
                ):
                    continue
                seen.add(node["id"])
                d = self._docs_by_id[node["id"]]
                related.append(
                    RelatedSource(
                        id=d["id"],
                        title=d["title"],
                        citation=d["citation"],
                        instrument=d["instrument"],
                        source_url=d["source_url"],
                        relation=node["relation"],
                    )
                )
                if len(related) >= limit:
                    return related
        return related

    def _cache_get(self, key: tuple) -> list[JurisdictionAnswer] | None:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def _cache_put(self, key: tuple, value: list[JurisdictionAnswer]) -> None:
        if self.settings.answer_cache_size <= 0:
            return
        self._cache[key] = value
        if len(self._cache) > self.settings.answer_cache_size:
            self._cache.popitem(last=False)
