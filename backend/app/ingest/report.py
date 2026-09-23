"""Run `verify_entry` across the whole corpus and persist a report."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

from app import config
from app.corpus_loader import load_corpus
from app.ingest.fetch import FetchResult, fetch
from app.ingest.verify import VerifyResult, verify_entry

Fetcher = Callable[[str], FetchResult]

_OK_STATUSES = {"ok", "stale"}


@dataclass
class CorpusVerifyReport:
    generated_at: str
    stale_days: int
    total: int
    counts: Dict[str, int]
    results: List[Dict] = field(default_factory=list)

    @property
    def has_failures(self) -> bool:
        return any(s not in _OK_STATUSES and n for s, n in self.counts.items())

    def as_dict(self) -> Dict:
        return {
            "generated_at": self.generated_at,
            "stale_days": self.stale_days,
            "total": self.total,
            "counts": self.counts,
            "results": self.results,
        }

    def write(self, path: Optional[Path] = None) -> Path:
        path = path or config.VERIFY_REPORT_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.as_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path


def verify_corpus(
    corpus_dir: Path = config.CORPUS_DIR,
    *,
    stale_days: int = 180,
    fetcher: Fetcher = fetch,
    today: Optional[date] = None,
) -> CorpusVerifyReport:
    docs = load_corpus(corpus_dir)
    results: List[VerifyResult] = [
        verify_entry(doc, fetcher=fetcher, today=today, stale_days=stale_days) for doc in docs
    ]
    counts: Dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    return CorpusVerifyReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        stale_days=stale_days,
        total=len(docs),
        counts=counts,
        results=[r.as_dict() for r in results],
    )
