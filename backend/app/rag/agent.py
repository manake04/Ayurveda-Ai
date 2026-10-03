"""Agentic ("deep research") mode: plan sub-questions, retrieve for each, then merge.

A compound question such as "Can I patent my new formulation and register its brand in
the EU?" spans several legal topics. Retrieving once for the whole question tends to
surface sources for only the dominant topic. Here an LLM first splits the question into
self-contained sub-questions; each is retrieved separately (embedded in one batch), and
the hits are merged per jurisdiction with a note of which sub-question found them. The
answer is then written by the normal pipeline, so citation checking and abstention apply
unchanged.
"""

import logging
from dataclasses import dataclass

from app.llm import LLM, LLMError, complete_json
from app.retrieval.retriever import Jurisdiction, RetrievalResult

log = logging.getLogger(__name__)

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "jurisdictions": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["india", "international"]},
                    },
                },
                "required": ["question", "jurisdictions"],
            },
        }
    },
    "required": ["steps"],
}

PLANNER_SYSTEM = """You plan research for an assistant that explains intellectual-property \
and regulatory law for Ayurvedic products.

Split the user's question into the smallest set of self-contained sub-questions (at most \
{max_steps}). Each sub-question must target ONE legal topic, for example: patentability, \
trademark or GI registration, biodiversity / access-and-benefit-sharing approval, drug \
classification and licensing, advertising and labelling rules, or export market access. \
Only split when the question really asks about several distinct things; otherwise return \
exactly one step. Write every sub-question in English, phrased so it can be searched on \
its own. Tag each with the jurisdictions it concerns, chosen only from: {allowed}."""


@dataclass
class PlanStep:
    question: str
    jurisdictions: list[Jurisdiction]


async def plan(llms: list[LLM], query: str, allowed: list[Jurisdiction], max_steps: int) -> list[PlanStep]:
    """Sub-questions for `query`, or [] if planning isn't possible."""
    if not llms:
        return []
    system = PLANNER_SYSTEM.format(max_steps=max_steps, allowed=", ".join(allowed))
    try:
        data = await complete_json(llms, system, f"Question: {query}", PLAN_SCHEMA)
    except LLMError as exc:
        log.warning("Planning failed, using standard retrieval: %s", exc)
        return []
    steps = []
    for raw in (data.get("steps") or [])[:max_steps]:
        question = str(raw.get("question", "")).strip()
        jurisdictions = [j for j in raw.get("jurisdictions") or [] if j in allowed] or list(allowed)
        if len(question) >= 3:
            steps.append(PlanStep(question, list(dict.fromkeys(jurisdictions))))
    return steps


def merge(
    jurisdiction: Jurisdiction,
    steps: list[PlanStep],
    per_step: list[dict[Jurisdiction, RetrievalResult]],
    max_sources: int,
) -> RetrievalResult:
    """Union of the confident hits each sub-question found for one jurisdiction.

    Only sub-questions tagged with this jurisdiction count, and only they are passed on as
    the parts to answer, so the India answer isn't asked about an EU-only sub-question."""
    relevant = [i for i, step in enumerate(steps) if jurisdiction in step.jurisdictions]
    parts = [steps[i].question for i in relevant]
    best: dict[str, tuple] = {}  # doc id -> (doc, score)
    provenance: dict[str, list[int]] = {}
    confidences = []
    for part_index, step_index in enumerate(relevant):
        result = per_step[step_index].get(jurisdiction)
        if result is None or result.abstained:
            continue
        confidences.append(result.confidence)
        for doc, score in result.hits:
            if doc["id"] not in best or score > best[doc["id"]][1]:
                best[doc["id"]] = (doc, score)
            provenance.setdefault(doc["id"], []).append(part_index)

    if not best:
        return RetrievalResult(jurisdiction, [], "low", parts=parts, provenance={})
    hits = sorted(best.values(), key=lambda h: -h[1])[:max_sources]
    kept = {doc["id"] for doc, _ in hits}
    return RetrievalResult(
        jurisdiction,
        hits,
        "high" if "high" in confidences else "medium",
        parts=parts,
        provenance={k: v for k, v in provenance.items() if k in kept},
    )
