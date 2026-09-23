"""Heuristics that pull candidate corpus fields out of fetched source text.

Everything here is best-effort and deliberately conservative: a machine-scaffolded
entry is tagged ``review_status="unreviewed"`` and a human is expected to tighten
the ``title`` / ``instrument`` / ``citation`` / ``summary`` before it is trusted.
The one field held to a hard standard is ``full_text_excerpt`` — :func:`find_excerpt`
only ever returns text that is literally present in the fetched page.
"""
from __future__ import annotations

import re
from typing import List, Optional

_WS = re.compile(r"\s+")
_SENT_SPLIT = re.compile(r"(?<=[.;:])\s+(?=[A-Z0-9(\"'“])")

_STOPWORDS = {
    "the", "and", "for", "that", "with", "this", "from", "any", "are", "not", "which",
    "under", "such", "shall", "been", "has", "have", "may", "its", "into", "was", "were",
    "act", "rules", "rule", "section", "article", "means", "including", "other", "than",
    "person", "made", "make", "made", "upon", "where", "when", "each", "all", "our",
}


def normalise(text: str) -> str:
    return _WS.sub(" ", (text or "").replace(" ", " ")).strip()


def guess_title(text: str, fallback: str = "") -> str:
    """Best candidate line for a document title: the first mixed-case line of a
    sensible length that isn't obvious page chrome."""
    chrome = ("skip to", "menu", "search", "home ", "contents:", "back to top")
    best_short = ""
    for raw in (text or "").splitlines():
        line = normalise(raw)
        low = line.lower()
        if low.startswith(chrome) or not (12 <= len(line) <= 160):
            continue
        has_lower = any(c.islower() for c in line)
        if has_lower and not line.endswith(":"):
            return line
        best_short = best_short or line
    return best_short or fallback


def _sentences(text: str) -> List[str]:
    flat = normalise(text)
    return [s.strip() for s in _SENT_SPLIT.split(flat) if s.strip()]


def _anchor_patterns(citation_hint: str) -> List[str]:
    """Regex fragments to locate the cited provision in body text, best first."""
    hint = citation_hint or ""
    patterns: List[str] = []

    # "3(p)", "10(4)(ii)(D)" — a number immediately followed by parenthetical labels
    for compact in re.findall(r"\d+[A-Za-z]?(?:\([^)\s]{1,6}\))+", hint):
        patterns.append(re.escape(compact))
        # the trailing clause label on its own, e.g. "(p)" or "(D)"
        last = re.findall(r"\([^)\s]{1,6}\)", compact)[-1]
        patterns.append(re.escape(last))

    # "Section 3", "Article 27", "Rule 170"
    for kind, num in re.findall(
        r"(?i)\b(section|sec|article|art|rule|clause|regulation|reg|para(?:graph)?)\.?\s*(\d+[A-Za-z]?)", hint
    ):
        patterns.append(rf"\b{kind}\.?\s*{re.escape(num)}\b")
        patterns.append(rf"\b{re.escape(num)}\b")

    # dedupe, keep order
    return list(dict.fromkeys(patterns))


def find_excerpt(text: str, citation_hint: str, *, max_chars: int = 600) -> Optional[str]:
    """Return the operative sentence(s) around the cited provision, verbatim.

    Only returns text that is literally a substring of `text` (after whitespace
    normalisation), so a caller can always re-verify it against a live fetch.
    Returns None when the cited provision can't be located.
    """
    flat = normalise(text)
    for pattern in _anchor_patterns(citation_hint):
        for match in re.finditer(pattern, flat):
            idx = match.start()
            start = flat.rfind(". ", 0, idx)
            start = 0 if start == -1 else start + 2
            window = flat[start : start + max_chars].strip()
            cut = window.rfind(". ")
            if cut > 60:
                window = window[: cut + 1]
            if len(window) >= 40:
                return window
    return None


def lead_summary(text: str, *, n_sentences: int = 3, max_chars: int = 700) -> str:
    """A plain extractive summary: the first few substantive sentences of the page."""
    out: List[str] = []
    for sentence in _sentences(text):
        if len(sentence) < 40:
            continue
        low = sentence.lower()
        if any(bad in low for bad in ("cookie", "javascript", "browser", "newsletter", "all rights reserved")):
            continue
        out.append(sentence)
        if len(out) >= n_sentences:
            break
    summary = " ".join(out)
    if len(summary) > max_chars:
        summary = summary[:max_chars].rsplit(" ", 1)[0].strip() + " …"
    return summary


def keyword_tags(text: str, title: str = "", *, limit: int = 6) -> List[str]:
    """Cheap frequency-based keyword tags from the title + body."""
    words = re.findall(r"[a-z]{4,}", f"{title} {text}".lower())
    freq: dict[str, int] = {}
    for w in words:
        if w in _STOPWORDS:
            continue
        freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq, key=lambda w: (-freq[w], w))
    return ranked[:limit]


_SOFT_404_MARKERS = (
    "page cannot be found",
    "page not found",
    "404 not found",
    "the page you are looking for",
    "this page does not exist",
    "no longer available",
)


def looks_like_soft_404(text: str) -> bool:
    """True for a short page carrying an unmistakable 'not found' message — some
    sites return these with an HTTP 200."""
    flat = normalise(text).lower()
    if len(flat) > 2500:
        return False
    return any(marker in flat for marker in _SOFT_404_MARKERS)


def excerpt_present(text: str, excerpt: str, *, min_overlap: float = 0.9) -> bool:
    """True if `excerpt` still appears in `text` — exact (whitespace-normalised) or
    as a >= `min_overlap` token-overlap match (tolerates a reworded connective)."""
    flat = normalise(text).lower()
    target = normalise(excerpt).lower()
    if not target:
        return False
    if target in flat:
        return True
    target_tokens = set(re.findall(r"[a-z0-9()]+", target))
    if not target_tokens:
        return False
    page_tokens = set(re.findall(r"[a-z0-9()]+", flat))
    hit = len(target_tokens & page_tokens) / len(target_tokens)
    return hit >= min_overlap
