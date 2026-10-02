"""Turn a source id + a locator into a corpus entry (see corpus/SCHEMA.md)."""
from __future__ import annotations

from datetime import date
from typing import Callable, Dict, Optional

from app import config
from app.ingest import extract
from app.ingest.fetch import FetchResult, extract_text, fetch
from app.ingest.sources import Source, get_source

Fetcher = Callable[[str], FetchResult]

# every key SCHEMA.md marks as required
_REQUIRED_FIELDS = (
    "id", "jurisdiction", "regime", "title", "instrument", "citation",
    "instrument_type", "summary", "source_url", "source_name", "last_verified", "tags",
)


class ScaffoldError(RuntimeError):
    pass


def _llm_summary(query_title: str, page_text: str) -> Optional[str]:
    """Optional: an LLM summary grounded strictly in the fetched page text.

    Mirrors app/rag.py:_llm_answer — lazy import, strict grounding instruction,
    and any failure just returns None so the caller falls back to the extractive
    summary. Only runs when an API key is configured.
    """
    if not (config.ANTHROPIC_API_KEY or config.OPENAI_API_KEY):
        return None
    context = page_text[:6000]
    system = (
        "You write one plain-language paragraph (3-5 sentences) explaining what a legal / "
        "regulatory provision says and why it matters for Ayurveda intellectual-property or "
        "regulatory strategy. Use ONLY the source text provided. Do not add facts, section "
        "numbers, dates or citations that are not in the source text. If the source text is "
        "insufficient, reply exactly with: INSUFFICIENT."
    )
    user = f"Provision: {query_title}\n\nSource text:\n{context}"
    try:
        if config.ANTHROPIC_API_KEY:
            import anthropic

            client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
            resp = client.messages.create(
                model=config.ANTHROPIC_MODEL,
                max_tokens=400,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            out = resp.content[0].text.strip()
        else:
            import openai

            client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
            resp = client.chat.completions.create(
                model=config.OPENAI_MODEL,
                max_tokens=400,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            out = resp.choices[0].message.content.strip()
    except Exception:  # noqa: BLE001 - LLM is a bonus, never required
        return None
    if not out or "INSUFFICIENT" in out:
        return None
    return out


def scaffold_entry(
    source_id: str,
    locator: str,
    *,
    regime: str,
    id_slug: str,
    jurisdiction: Optional[str] = None,
    title: Optional[str] = None,
    instrument: Optional[str] = None,
    citation: Optional[str] = None,
    instrument_type: Optional[str] = None,
    fetcher: Fetcher = fetch,
    today: Optional[date] = None,
) -> Dict:
    """Build a corpus entry dict. Fetches the source, extracts what it can, and
    marks the result ``review_status="unreviewed"``.

    ``full_text_excerpt`` is only included when the operative sentence for the
    cited section is found literally in the fetched page.
    """
    src: Source = get_source(source_id)
    if not src.automatable:
        raise ScaffoldError(
            f"source '{src.id}' is not automatable — {src.access_notes} "
            "Add this entry by hand instead."
        )

    today = today or date.today()
    url = src.build_url(locator)
    result = fetcher(url)
    if not result.ok:
        raise ScaffoldError(f"could not fetch {url} (HTTP {result.status}{'; ' + result.error if result.error else ''})")

    extracted = extract_text(result)
    body = extracted.text
    if extracted.ok and extract.looks_like_soft_404(body):
        raise ScaffoldError(
            f"{url} returned HTTP {result.status} but the body is a 'not found' page — "
            "check the locator."
        )

    resolved_title = title or extract.guess_title(body, fallback=id_slug.replace("-", " ").title())
    resolved_instrument = instrument or resolved_title
    resolved_citation = citation or ""

    summary = _llm_summary(resolved_title, body) if extracted.ok else None
    summary_source = "llm" if summary else "extractive"
    if not summary:
        summary = extract.lead_summary(body) if extracted.ok else ""
    if not summary:
        summary_source = "none"
        summary = (
            f"[UNREVIEWED SCAFFOLD] Source body could not be parsed automatically "
            f"({extracted.parser}). Read {url} and write this summary by hand before use."
        )

    entry: Dict = {
        "id": id_slug,
        "jurisdiction": jurisdiction or src.jurisdiction,
        "regime": regime,
        "title": resolved_title,
        "instrument": resolved_instrument,
        "citation": resolved_citation,
        "instrument_type": instrument_type or src.default_instrument_type,
        "summary": summary,
        "source_url": url,
        "source_name": src.source_name_for(resolved_instrument),
        "last_verified": today.isoformat(),
        "tags": extract.keyword_tags(body, resolved_title) if extracted.ok else [],
        "review_status": "unreviewed",
        "provenance": {
            "method": "ingest-scaffold",
            "source_id": src.id,
            "locator": locator,
            "fetched_at": result.fetched_at,
            "parser": extracted.parser,
            "summary_source": summary_source,
        },
    }

    if resolved_citation and extracted.ok:
        excerpt = extract.find_excerpt(body, resolved_citation)
        if excerpt and extract.excerpt_present(body, excerpt):
            entry["full_text_excerpt"] = excerpt

    return entry


def missing_required_fields(entry: Dict) -> list[str]:
    return [f for f in _REQUIRED_FIELDS if f not in entry or (not entry[f] and entry[f] != [])]
