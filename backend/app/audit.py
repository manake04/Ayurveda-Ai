"""A minimal local audit log, aligned in spirit with the DPDP Act's transparency/consent
expectations: every substantive call is recorded with a timestamp and a short summary so
the user (or a reviewer) can see what the assistant was asked and what it returned.

This is an MVP-grade, append-only local JSONL file -- production would add encryption at
rest, retention limits, and a proper consent-linked data-subject-access flow (see
docs/ROADMAP.md). It deliberately never logs full free-text queries by default beyond
what's needed for the demo transparency panel -- see `redact` below.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from app import config


def _redact(text: str, max_len: int = 160) -> str:
    text = text.strip().replace("\n", " ")
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def log_event(endpoint: str, summary: str, jurisdiction: Optional[str] = None) -> None:
    config.AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint,
        "jurisdiction": jurisdiction,
        "summary": _redact(summary),
    }
    with open(config.AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_recent(limit: int = 20) -> List[dict]:
    if not config.AUDIT_LOG_PATH.exists():
        return []
    with open(config.AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
    entries = [json.loads(line) for line in lines[-limit:]]
    entries.reverse()
    return entries
