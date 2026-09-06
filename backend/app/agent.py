"""Rule-based agentic planner: multi-step retrieval + graph orchestration, no LLM required.

The problem statement calls for "agentic, multi-source orchestration" to "deepen multi-step
reasoning" as a later stage on top of the retrieval MVP. A real LLM-driven planner is the
long-run version of this (see `Planner.plan`'s docstring for exactly where it plugs in) --
but a genuinely useful *rule-based* version doesn't need to wait for one. This module
decomposes a query into a small ordered plan using signals already available for free from
the retrieval layer itself:

1. Jurisdiction: if the jurisdiction the caller asked for is "both", or if the *other*
   jurisdiction also turns out to score confidently against the same query, both are
   planned as separate steps (kept visibly separate, per the jurisdiction-switch
   requirement -- agentic mode never merges them).
2. Regime: within a jurisdiction, if the query's top hits span two or more distinct legal
   regimes above the confidence threshold (e.g. both `drug_regulatory` and
   `biodiversity_abs` score strongly), that's a real signal the question is compound --
   the plan adds one focused sub-step per regime instead of one blended lookup.
3. Graph cross-linking: after all steps run, a final pass expands the *union* of every
   step's citations one hop through the knowledge graph, surfacing requirements that don't
   share vocabulary with the query at all (see `app.graph` / `app.rag.graph_expand`).

Each step is executed through the exact same grounded retrieval path as `/ask` (same
extractive/LLM answer synthesis, same "never cite what wasn't retrieved" guarantee) --
this module only decides *how many* lookups to run and *what to ask each one*, never
generates answer text itself.
"""
from typing import List, Optional

from app import config
from app.graph import GraphStore
from app.models import AgenticAnswer, AgenticStep, JurisdictionAnswer
from app.rag import answer_for_jurisdiction, graph_expand
from app.vectorstore import VectorStore

_OTHER_JURISDICTION = {"india": "international", "international": "india"}


def _plan_jurisdictions(store: VectorStore, query: str, requested_jurisdiction: str) -> List[str]:
    """Which jurisdiction(s) actually warrant a step, per rule (1) above."""
    if requested_jurisdiction == "both":
        return ["india", "international"]

    jurisdictions = [requested_jurisdiction]
    other = _OTHER_JURISDICTION[requested_jurisdiction]
    # Use the standard (absolute) confidence bar here -- this decides whether to add a whole
    # *second jurisdiction section*, which is a bigger step than splitting by regime, so it
    # should only happen when the other jurisdiction is confidently, not just marginally,
    # relevant on its own terms.
    other_hits = store.search(query, top_k=3, jurisdiction=other)
    if other_hits and other_hits[0][1] >= config.CONFIDENCE_MEDIUM_THRESHOLD:
        jurisdictions.append(other)
    return jurisdictions


def _plan_regimes_for(store: VectorStore, query: str, jurisdiction: str) -> List[Optional[str]]:
    """Per rule (2): one entry per regime if the query is compound within this jurisdiction,
    else a single `None` entry meaning "search the whole jurisdiction, unsplit"."""
    regimes = store.top_regimes(query, jurisdiction, limit=8)
    if len(regimes) >= 2:
        return regimes
    return [None]


def build_plan(store: VectorStore, query: str, requested_jurisdiction: str) -> List[AgenticStep]:
    """Rule-based planning. A future LLM-backed planner would replace this function's body
    with a model call that reasons over the query and available tools (retrieve, graph
    traversal, classifier, ABS helper) and emits the same List[AgenticStep] shape -- every
    other part of this module and the API response format stays unchanged."""
    steps: List[AgenticStep] = []
    jurisdictions = _plan_jurisdictions(store, query, requested_jurisdiction)

    step_index = 0
    for jurisdiction in jurisdictions:
        regimes = _plan_regimes_for(store, query, jurisdiction)
        jur_label = "India" if jurisdiction == "india" else "International"
        for regime in regimes:
            if regime is None:
                reason = f"Look up {jur_label} sources most relevant to the question as a whole."
            else:
                reason = (
                    f"The question scores strongly against multiple {jur_label} regimes; "
                    f"looking up the '{regime}' regime specifically so it isn't diluted by the others."
                )
            steps.append(AgenticStep(step_index=step_index, jurisdiction=jurisdiction, regime=regime, reason=reason))
            step_index += 1

    return steps


def _plan_summary(steps: List[AgenticStep], requested_jurisdiction: str) -> str:
    n_jur = len({s.jurisdiction for s in steps})
    n_regime_steps = sum(1 for s in steps if s.regime is not None)
    parts = [f"Planned {len(steps)} retrieval step(s)"]
    if n_jur > 1:
        parts.append("spanning both India and International sources (kept in separate sections below)")
    if n_regime_steps:
        parts.append(f"with {n_regime_steps} step(s) split out by legal regime because the question is compound")
    if len(steps) == 1 and steps[0].regime is None:
        parts.append("-- this looked like a single-regime, single-jurisdiction question, so no decomposition was needed")
    return " ".join(parts) + "."


def run_agentic(
    store: VectorStore,
    graph_store: Optional[GraphStore],
    query: str,
    requested_jurisdiction: str,
    top_k: int,
) -> AgenticAnswer:
    steps = build_plan(store, query, requested_jurisdiction)
    sections: List[JurisdictionAnswer] = []

    for step in steps:
        section = answer_for_jurisdiction(
            store, query, step.jurisdiction, top_k, graph_store=graph_store, regime=step.regime
        )
        if step.regime:
            section.label = f"{section.jurisdiction} — {step.regime.replace('_', ' ')}"
        sections.append(section)

    # Cross-cutting graph pass: expand once more across every citation collected from every
    # step, so a requirement linked to *any* of the steps' findings (not just the top hit of
    # one of them) still has a chance to surface. Skipped if nothing was found at all.
    if graph_store is not None:
        doc_by_id = {d["id"]: d for d in store.docs}
        all_cited_ids = [c.id for section in sections for c in section.citations]
        already = {c.id for section in sections for c in section.citations}
        already |= {c.id for section in sections for c in section.graph_related}
        if all_cited_ids:
            cross_related = graph_expand(
                graph_store, doc_by_id, all_cited_ids, already_included=already,
                jurisdiction="both", max_related=6,
            )
            for item in cross_related:
                for section in sections:
                    if section.jurisdiction == item.jurisdiction and not section.abstained:
                        section.graph_related.append(item)
                        break

    return AgenticAnswer(
        query=query,
        disclaimer=config.DISCLAIMER,
        plan_summary=_plan_summary(steps, requested_jurisdiction),
        steps=steps,
        sections=sections,
    )
