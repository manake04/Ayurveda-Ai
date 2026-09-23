"""Re-check one corpus entry against its live `source_url`.

Statuses (worst-wins):
    ``ok``            – reachable, and any `full_text_excerpt` still present.
    ``stale``         – reachable and consistent, but `last_verified` is older
                        than the staleness threshold.
    ``excerpt_drift`` – reachable, but the entry's `full_text_excerpt` no longer
                        appears on the page (needs a human to re-read the source).
    ``unreachable``   – the `source_url` did not return a 2xx response.
    ``unverifiable``  – reachable, but the body can't be checked (a PDF with no
                        `pypdf` installed, or a `not_automatable` source). Never a
                        false ``ok``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Dict, Optional
from urllib.parse import urlparse

from app.ingest import extract
from app.ingest.fetch import FetchResult, extract_text, fetch
from app.ingest.sources import source_for_url

Fetcher = Callable[[str], FetchResult]


@dataclass
class VerifyResult:
    id: str
    status: str
    source_url: str
    last_verified: str
    staleness_days: Optional[int]
    checks: Dict[str, bool] = field(default_factory=dict)
    detail: str = ""

    def as_dict(self) -> Dict:
        return {
            "id": self.id,
            "status": self.status,
            "source_url": self.source_url,
            "last_verified": self.last_verified,
            "staleness_days": self.staleness_days,
            "checks": self.checks,
            "detail": self.detail,
        }


def _staleness_days(last_verified: str, today: date) -> Optional[int]:
    try:
        return (today - date.fromisoformat(last_verified)).days
    except (ValueError, TypeError):
        return None


def verify_entry(
    entry: Dict,
    *,
    fetcher: Fetcher = fetch,
    today: Optional[date] = None,
    stale_days: int = 180,
) -> VerifyResult:
    today = today or date.today()
    url = entry.get("source_url", "")
    last_verified = entry.get("last_verified", "")
    staleness = _staleness_days(last_verified, today)
    checks: Dict[str, bool] = {}

    src = source_for_url(url)
    if src is not None and not src.automatable:
        return VerifyResult(
            id=entry["id"],
            status="unverifiable",
            source_url=url,
            last_verified=last_verified,
            staleness_days=staleness,
            checks={"reachable": False},
            detail=f"source '{src.id}' is not automatable: {src.access_notes[:120]}",
        )

    if not urlparse(url).scheme.startswith("http"):
        return VerifyResult(
            id=entry["id"],
            status="unreachable",
            source_url=url,
            last_verified=last_verified,
            staleness_days=staleness,
            checks={"reachable": False},
            detail="source_url is not an http(s) URL",
        )

    result = fetcher(url)
    checks["reachable"] = result.ok
    if not result.ok:
        return VerifyResult(
            id=entry["id"],
            status="unreachable",
            source_url=url,
            last_verified=last_verified,
            staleness_days=staleness,
            checks=checks,
            detail=result.error or f"HTTP {result.status}",
        )

    excerpt = entry.get("full_text_excerpt")
    extracted = extract_text(result)

    if extracted.ok and extract.looks_like_soft_404(extracted.text):
        return VerifyResult(
            id=entry["id"],
            status="unreachable",
            source_url=url,
            last_verified=last_verified,
            staleness_days=staleness,
            checks={"reachable": False},
            detail="HTTP 200 but the page body is a 'not found' message (soft 404)",
        )

    status = "ok"
    detail = ""
    if excerpt:
        if not extracted.ok:
            status = "unverifiable"
            detail = f"could not extract body text ({extracted.parser}); reachability only"
            checks["excerpt_present"] = False
        elif extract.excerpt_present(extracted.text, excerpt):
            checks["excerpt_present"] = True
        else:
            status = "excerpt_drift"
            detail = "full_text_excerpt no longer found on the page — re-read the source"
            checks["excerpt_present"] = False
    elif not extracted.ok:
        # nothing to check against the body, and we couldn't read it anyway
        status = "unverifiable"
        detail = f"reachable, but body not parseable ({extracted.parser})"

    if status == "ok" and staleness is not None and staleness > stale_days:
        status = "stale"
        detail = f"last verified {staleness} days ago (threshold {stale_days})"

    return VerifyResult(
        id=entry["id"],
        status=status,
        source_url=url,
        last_verified=last_verified,
        staleness_days=staleness,
        checks=checks,
        detail=detail,
    )
