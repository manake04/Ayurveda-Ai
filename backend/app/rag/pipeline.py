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
from dataclasses import dataclass

from app.core.config import DISCLAIMER, Settings
from app.i18n import BHASHINI_LANGUAGES
from app.i18n.bhashini import BhashiniTranslator, TranslationError
from app.knowledge.graph import GraphStore
from app.llm import LLM, LLMError
from app.rag import agent, prompts
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

Event = dict  # {"type": "plan" | "step" | "sources" | "delta" | "done" | "end", ...}

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


@dataclass
class _Job:
    """What one request asks the generator to do."""

    query: str  # the question as the model sees it (English if it was translated)
    language: str  # language rule for the prompt: auto | en | hi
    parts: list[str] | None = None  # agentic sub-questions (all jurisdictions)
    translate_to: str | None = None  # Bhashini target language for the final answer


class RAGPipeline:
    def __init__(
        self,
        settings: Settings,
        retriever: Retriever,
        graph: GraphStore,
        llms: list[LLM],
        translator: BhashiniTranslator | None = None,
    ):
        self.settings = settings
        self.retriever = retriever
        self.graph = graph
        self.llms = llms  # tried in order; empty means extractive answers
        self.translator = translator
        self._docs_by_id = {d["id"]: d for d in retriever.store.docs}
        self._cache: OrderedDict[tuple, tuple[list[str] | None, list[JurisdictionAnswer]]] = OrderedDict()

    # ---- public API ----

    async def stream(self, req: AskRequest) -> AsyncIterator[Event]:
        """Yield events as the answer is produced: plan (agentic), sources, text, done."""
        started = time.perf_counter()
        jurisdictions: list[Jurisdiction] = (
            ["india", "international"] if req.jurisdiction == "both" else [req.jurisdiction]
        )
        key = (" ".join(req.query.lower().split()), req.jurisdiction, req.language, req.mode)

        cached = self._cache_get(key)
        if cached is not None:
            plan_questions, answers = cached
            if plan_questions:
                yield {"type": "plan", "steps": [{"question": q} for q in plan_questions]}
            for answer in answers:
                yield self._sources_event(answer)
                yield self._done_event(answer)
        else:
            job = await self._prepare(req)
            results = None
            if req.mode == "agentic":
                steps = await agent.plan(self.llms, job.query, jurisdictions, self.settings.agentic_max_steps)
                if len(steps) >= 2:
                    yield {
                        "type": "plan",
                        "steps": [
                            {"question": st.question, "jurisdictions": st.jurisdictions} for st in steps
                        ],
                    }
                    vectors = await self.retriever.embedder.embed_queries([st.question for st in steps])
                    per_step = []
                    for index, (step, vector) in enumerate(zip(steps, vectors, strict=True)):
                        step_results = await self.retriever.retrieve(
                            step.question, step.jurisdictions, vector
                        )
                        per_step.append(step_results)
                        found = {j: 0 if r.abstained else len(r.hits) for j, r in step_results.items()}
                        yield {"type": "step", "index": index, "found": found}
                    results = {
                        j: agent.merge(j, steps, per_step, self.settings.agentic_max_sources)
                        for j in jurisdictions
                    }
                    job.parts = [st.question for st in steps]
            if results is None:
                results = await self.retriever.retrieve(job.query, jurisdictions)

            answers: list[JurisdictionAnswer] = []
            async for event in self._generate_all(job, results, answers):
                yield event
            if all("fallback" not in a.generated_by and "failed" not in a.generated_by for a in answers):
                ordered = sorted(answers, key=lambda a: jurisdictions.index(a.jurisdiction))
                self._cache_put(key, (job.parts, ordered))

        yield {"type": "end", "latency_ms": int((time.perf_counter() - started) * 1000)}

    async def answer(self, req: AskRequest) -> AskResponse:
        """Non-streaming variant: run the stream to completion and collect the result."""
        answers: dict[str, dict] = {}
        plan_questions = None
        latency = 0
        async for event in self.stream(req):
            if event["type"] == "plan":
                plan_questions = [st["question"] for st in event["steps"]]
            elif event["type"] == "sources":
                answers[event["jurisdiction"]] = {k: v for k, v in event.items() if k != "type"}
            elif event["type"] == "done":
                answers[event["jurisdiction"]].update(
                    answer=event["answer"], generated_by=event["generated_by"]
                )
            elif event["type"] == "end":
                latency = event["latency_ms"]
        return AskResponse(
            query=req.query,
            plan=plan_questions,
            answers=[JurisdictionAnswer(**a) for a in answers.values()],
            disclaimer=DISCLAIMER,
            latency_ms=latency,
        )

    # ---- generation ----

    async def _prepare(self, req: AskRequest) -> _Job:
        """Translate the question to English first when the answer language needs Bhashini."""
        if req.language in BHASHINI_LANGUAGES and self.translator is not None:
            try:
                english = await self.translator.translate(req.query, req.language, "en")
                return _Job(query=english, language="en", translate_to=req.language)
            except TranslationError as exc:
                log.warning("Question translation failed, answering in the question's language: %s", exc)
        language = req.language if req.language in ("en", "hi") else "auto"
        return _Job(query=req.query, language=language)

    async def _generate_all(
        self,
        job: _Job,
        results: dict[Jurisdiction, RetrievalResult],
        answers: list[JurisdictionAnswer],
    ) -> AsyncIterator[Event]:
        """Run one generation per jurisdiction concurrently, interleaving their events."""
        queue: asyncio.Queue = asyncio.Queue()

        async def run(result: RetrievalResult) -> None:
            try:
                async for event in self._generate_one(job, result, answers):
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
        self, job: _Job, result: RetrievalResult, answers: list[JurisdictionAnswer]
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
        elif not self.llms:
            answer.answer = prompts.extractive_answer(result.hits)
            answer.generated_by = "extractive"
        else:
            # A jurisdiction with one relevant sub-question gets a normal single-part answer.
            parts = result.parts if result.parts and len(result.parts) > 1 else None
            system = prompts.build_system_prompt(job.language, multi_part=bool(parts))
            user = prompts.build_user_prompt(
                job.query, jurisdiction, result.hits, parts, result.provenance if parts else None
            )
            for llm in self.llms:
                chunks: list[str] = []
                try:
                    async for text in llm.stream(system, user):
                        chunks.append(text)
                        if job.translate_to is None:  # translated answers are sent whole at the end
                            yield {"type": "delta", "jurisdiction": jurisdiction, "text": text}
                    answer.answer = self._strip_unknown_refs("".join(chunks), len(citations))
                    answer.generated_by = llm.name
                    break
                except LLMError as exc:
                    log.warning("%s failed: %s", llm.name, exc)
                    if chunks:  # part of this answer was already shown; don't splice in another model
                        break
            if not answer.answer:
                answer.answer = prompts.extractive_answer(result.hits)
                answer.generated_by = "extractive (fallback)"

        if job.translate_to is not None:
            try:
                answer.answer = await self.translator.translate(answer.answer, "en", job.translate_to)
                answer.generated_by += " + bhashini"
            except TranslationError as exc:
                log.warning("Answer translation failed, returning English: %s", exc)
                answer.generated_by += " (translation failed)"

        answers.append(answer)
        yield self._done_event(answer)

    # ---- helpers ----

    @staticmethod
    def _done_event(answer: JurisdictionAnswer) -> Event:
        return {"type": "done", **answer.model_dump(include={"jurisdiction", "answer", "generated_by"})}

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

    def _cache_get(self, key: tuple):
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def _cache_put(self, key: tuple, value: tuple) -> None:
        if self.settings.answer_cache_size <= 0:
            return
        self._cache[key] = value
        if len(self._cache) > self.settings.answer_cache_size:
            self._cache.popitem(last=False)
