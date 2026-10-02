"""Prompt construction and the no-LLM (extractive) answer."""

from app.retrieval.corpus import Document

JURISDICTION_LABEL = {"india": "India", "international": "International (outside India)"}

SYSTEM_PROMPT = """You are IP-SAKTI Sahayak, an assistant that explains intellectual-property \
and regulatory rules for Ayurvedic products. You give information, not legal advice.

Rules:
- Answer ONLY from the numbered sources provided. Never add legal facts, section numbers, \
dates or deadlines that are not in the sources.
- Cite every factual sentence with its source number(s) in square brackets, e.g. [1] or [2][3]. \
Only use numbers that appear in the sources.
- If the sources only partly answer the question, answer that part and say plainly what \
they don't cover. Never guess.
- Stay within the jurisdiction you are told to cover.
- Format: open with a one or two sentence direct answer, then up to five short bullet \
points with the practical requirements or next steps. Markdown, no headings, about 200 \
words at most.
- {language_rule}"""

LANGUAGE_RULES = {
    "auto": "Reply in the same language the question is written in.",
    "en": "Reply in English.",
    "hi": "Reply in Hindi (Devanagari script). Keep statute names and section numbers as written.",
}

ABSTENTION_TEXT = {
    "india": (
        "I couldn't find a source in the curated Indian corpus that answers this confidently, "
        "so I won't guess. Try rephrasing with more specifics (the product type, the right you "
        "want, or the regulator involved), check the International view, or ask a registered "
        "IP facilitator."
    ),
    "international": (
        "I couldn't find a source in the curated international corpus that answers this "
        "confidently, so I won't guess. Try rephrasing with more specifics (the target country "
        "or treaty), check the India view, or ask a registered IP facilitator."
    ),
}


def build_system_prompt(language: str) -> str:
    return SYSTEM_PROMPT.format(language_rule=LANGUAGE_RULES.get(language, LANGUAGE_RULES["auto"]))


def build_user_prompt(query: str, jurisdiction: str, hits: list[tuple[Document, float]]) -> str:
    blocks = []
    for n, (doc, _) in enumerate(hits, start=1):
        block = (
            f"[{n}] {doc['title']}\n"
            f"Instrument: {doc['instrument']}, {doc['citation']} ({doc['jurisdiction']})\n"
            f"Summary: {doc['summary']}"
        )
        if doc.get("full_text_excerpt"):
            block += f"\nExact text: {doc['full_text_excerpt']}"
        blocks.append(block)
    sources = "\n\n".join(blocks)
    return (
        f"Jurisdiction to cover: {JURISDICTION_LABEL[jurisdiction]}\n\n"
        f"Sources:\n\n{sources}\n\n"
        f"Question: {query}"
    )


def extractive_answer(hits: list[tuple[Document, float]]) -> str:
    """Answer assembled verbatim from source summaries, used when no LLM is available."""
    lines = ["Here is what the most relevant sources say:"]
    for n, (doc, _) in enumerate(hits[:3], start=1):
        lines.append(
            f"\n- **{doc['title']}** ({doc['instrument']}, {doc['citation']}): {doc['summary']} [{n}]"
        )
    return "\n".join(lines)
