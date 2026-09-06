"""Citation-grounded retrieval + answer synthesis.

Design goal: it must be structurally impossible for this module to cite a source that
was not actually retrieved. The LLM branch is instructed to answer ONLY from the
supplied chunks and is never allowed to invent a citation id; the extractive branch
(default, no API key needed) does not generate free text about the law at all -- it
assembles the answer directly out of the retrieved chunks' own summaries, so there is
nothing for it to hallucinate.
"""
from typing import Dict, List, Optional, Tuple

from app import config
from app.graph import GraphStore
from app.models import Citation, JurisdictionAnswer, RelatedCitation
from app.vectorstore import VectorStore


def _confidence_bucket(top_score: float) -> str:
    if top_score >= config.CONFIDENCE_HIGH_THRESHOLD:
        return "high"
    if top_score >= config.CONFIDENCE_MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def _to_citation(doc: Dict, score: float) -> Citation:
    return Citation(
        id=doc["id"],
        title=doc["title"],
        instrument=doc["instrument"],
        citation=doc["citation"],
        jurisdiction=doc["jurisdiction"],
        regime=doc["regime"],
        source_url=doc["source_url"],
        source_name=doc["source_name"],
        last_verified=doc["last_verified"],
        score=round(score, 4),
        full_text_excerpt=doc.get("full_text_excerpt"),
    )


ABSTENTION_TEXT = (
    "I don't have a confidently-relevant source for this in my current curated corpus, "
    "so I'm not going to guess. This may be outside this MVP's coverage (a hand-curated "
    "starter set of India + international provisions), a fast-changing area not yet in the "
    "corpus, or a question that genuinely needs a human IP facilitator's judgment. Please "
    "rephrase with more specifics, switch jurisdiction, or use the 'Escalate to a human IP "
    "facilitator' option."
)

# Graph relations that are informative to surface as "related requirements" alongside a
# direct answer. Deliberately excludes the auto-derived BELONGS_TO_REGIME/IN_JURISDICTION/
# RELEVANT_TO_CATEGORY edges here -- those connect a document to a *concept*, not to another
# citable source, and would just add noise to an answer (they're still useful for the
# dedicated /graph endpoints and the graph visualisation).
_ANSWER_RELEVANT_RELATIONS = {
    "SUPPORTS", "ENFORCES", "APPLIES_ALONGSIDE", "DETAILS", "IMPLEMENTS", "REINFORCED_BY",
    "RELATED_TO", "COMPLEMENTS", "CONSTRAINED_BY", "LABELLING_GOVERNED_BY", "ENFORCED_BY",
    "ALTERNATIVE_TO", "INTERNATIONAL_COUNTERPART", "INTERNATIONAL_ROUTE",
    "GOVERNED_BY_BASELINE", "PRIORITY_GOVERNED_BY", "ALTERNATIVE_STRATEGY",
    "ANALOGOUS_TO", "UMBRELLA_OVER",
}


def graph_expand(
    graph_store: Optional[GraphStore],
    doc_by_id: Dict[str, Dict],
    seed_ids: List[str],
    already_included: set,
    jurisdiction: str,
    max_related: int = 4,
) -> List[RelatedCitation]:
    """One-hop graph expansion from the top retrieved hits.

    This is what lets the assistant surface a genuinely relevant source that shares no
    vocabulary with the query -- e.g. a phytopharmaceutical-classification query pulling in
    the Biological Diversity Act via a hand-authored graph edge, not because the words
    overlap but because the two requirements are known to apply together. Every item
    returned is still a real corpus document with its own citation -- the graph only
    decides *which* additional real sources to surface, never generates new text.
    """
    if graph_store is None or not graph_store.is_ready:
        return []

    target_jurisdiction = None
    if jurisdiction == "india":
        target_jurisdiction = "India"
    elif jurisdiction == "international":
        target_jurisdiction = "International"

    seen = set(already_included)
    related: List[RelatedCitation] = []
    for seed_id in seed_ids:
        for neighbor in graph_store.related(seed_id, hops=1):
            if neighbor["node_type"] != "document":
                continue
            if neighbor["relation"] not in _ANSWER_RELEVANT_RELATIONS:
                continue
            if neighbor["id"] in seen:
                continue
            if target_jurisdiction and neighbor.get("jurisdiction") != target_jurisdiction:
                continue
            doc = doc_by_id.get(neighbor["id"])
            if not doc:
                continue
            seen.add(neighbor["id"])
            base = _to_citation(doc, score=0.0)
            related.append(
                RelatedCitation(**base.model_dump(), relation=neighbor["relation"], hops=neighbor["hops"])
            )
            if len(related) >= max_related:
                return related
    return related


def _extractive_answer(query: str, hits: List[Tuple[Dict, float]]) -> str:
    if not hits:
        return ABSTENTION_TEXT
    lines = [
        f"Here is what the curated corpus says that's most relevant to “{query}”. "
        "Each point is grounded in one source below -- read the cited section/article before relying on it."
    ]
    for i, (doc, score) in enumerate(hits, start=1):
        lines.append(
            f"\n{i}. **{doc['title']}** ({doc['instrument']}, {doc['citation']}): {doc['summary']}"
        )
    return "\n".join(lines)


def _llm_answer(query: str, hits: List[Tuple[Dict, float]]) -> str:
    """Optional LLM-synthesised answer, strictly grounded in the retrieved chunks.

    Only called when an API key is configured. Falls back to the extractive answer on
    any error so the assistant never goes silent or crashes a demo because of a flaky
    network call.
    """
    context_blocks = []
    for doc, _ in hits:
        context_blocks.append(
            f"[{doc['id']}] {doc['title']} -- {doc['instrument']}, {doc['citation']}\n{doc['summary']}\nSource: {doc['source_url']}"
        )
    context = "\n\n".join(context_blocks)

    system_prompt = (
        "You are IP-SAKTI Sahayak, an assistant giving INFORMATION (not legal advice) about "
        "intellectual property and regulatory rules for Ayurveda. Answer the user's question "
        "using ONLY the numbered source context provided below. For every substantive claim, "
        "cite the source by its bracketed id, e.g. [in-patents-3p]. If the context does not "
        "contain enough information to answer, say so plainly instead of guessing -- never "
        "invent a citation, a section number, or a fact not present in the context. Keep the "
        "answer concise and plain-language."
    )
    user_prompt = f"Context sources:\n\n{context}\n\nQuestion: {query}"

    try:
        if config.ANTHROPIC_API_KEY:
            import anthropic  # imported lazily so it's not a hard dependency

            client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
            resp = client.messages.create(
                model=config.ANTHROPIC_MODEL,
                max_tokens=700,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return resp.content[0].text
        if config.OPENAI_API_KEY:
            import openai  # imported lazily

            client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
            resp = client.chat.completions.create(
                model=config.OPENAI_MODEL,
                max_tokens=700,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return resp.choices[0].message.content
    except Exception as exc:  # noqa: BLE001 -- deliberate broad catch for demo robustness
        return _extractive_answer(query, hits) + f"\n\n_(LLM synthesis unavailable, showing extractive answer: {exc})_"

    return _extractive_answer(query, hits)


def answer_for_jurisdiction(
    store: VectorStore,
    query: str,
    jurisdiction: str,
    top_k: int,
    graph_store: Optional[GraphStore] = None,
    regime: Optional[str] = None,
) -> JurisdictionAnswer:
    hits = store.search(query, top_k=top_k, jurisdiction=jurisdiction, regime=regime)
    top_score = hits[0][1] if hits else 0.0
    confidence = _confidence_bucket(top_score)
    abstained = confidence == "low"

    graph_related: List[RelatedCitation] = []
    if abstained:
        text = ABSTENTION_TEXT
        citations: List[Citation] = []
    else:
        if config.ANTHROPIC_API_KEY or config.OPENAI_API_KEY:
            text = _llm_answer(query, hits)
        else:
            text = _extractive_answer(query, hits)
        citations = [_to_citation(doc, score) for doc, score in hits]

        if graph_store is not None:
            doc_by_id = {d["id"]: d for d in store.docs}
            seed_ids = [doc["id"] for doc, _ in hits[:2]]  # expand from the top-2 hits only
            graph_related = graph_expand(
                graph_store,
                doc_by_id,
                seed_ids,
                already_included={c.id for c in citations},
                jurisdiction=jurisdiction,
            )

    label = "India" if jurisdiction == "india" else "International"
    return JurisdictionAnswer(
        jurisdiction=label,
        answer_text=text,
        citations=citations,
        graph_related=graph_related,
        confidence=confidence,
        abstained=abstained,
    )


def ask(
    store: VectorStore,
    query: str,
    jurisdiction: str,
    top_k: int,
    graph_store: Optional[GraphStore] = None,
) -> List[JurisdictionAnswer]:
    if jurisdiction == "both":
        return [
            answer_for_jurisdiction(store, query, "india", top_k, graph_store),
            answer_for_jurisdiction(store, query, "international", top_k, graph_store),
        ]
    return [answer_for_jurisdiction(store, query, jurisdiction, top_k, graph_store)]
