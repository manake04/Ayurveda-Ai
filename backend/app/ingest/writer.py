"""Merge scaffolded entries into corpus/india.json / corpus/international.json.

Write policy (agreed with the maintainer): new entries ARE written straight into
the corpus files. But an entry that is already there and is hand-curated
(``review_status`` absent, ``"curated"`` or ``"verified"``) is never overwritten
unless ``force=True`` — machine output must not clobber reviewed content.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List

from app import config
from app.corpus_loader import load_corpus

_PROTECTED_STATUSES = {None, "curated", "verified"}

_FILE_BY_JURISDICTION = {"India": "india.json", "International": "international.json"}


@dataclass
class WriteReport:
    added: List[str] = field(default_factory=list)
    updated: List[str] = field(default_factory=list)
    skipped_protected: List[str] = field(default_factory=list)
    files_written: List[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.added or self.updated)


def _load_file(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _dump_file(path: Path, entries: List[Dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
        f.write("\n")


def upsert_entries(
    entries: List[Dict],
    corpus_dir: Path = config.CORPUS_DIR,
    *,
    force: bool = False,
) -> WriteReport:
    report = WriteReport()

    # id -> jurisdiction, across the whole corpus, to catch a cross-file id clash
    existing_all = {d["id"]: d for d in load_corpus(corpus_dir)}

    by_file: Dict[str, List[Dict]] = {}
    for entry in entries:
        jurisdiction = entry.get("jurisdiction")
        filename = _FILE_BY_JURISDICTION.get(jurisdiction)
        if filename is None:
            raise ValueError(
                f"entry {entry.get('id')!r} has jurisdiction {jurisdiction!r}; "
                f"expected one of {sorted(_FILE_BY_JURISDICTION)}"
            )

        prior = existing_all.get(entry["id"])
        if prior is not None:
            prior_file = _FILE_BY_JURISDICTION.get(prior.get("jurisdiction"))
            if prior_file != filename:
                raise ValueError(
                    f"entry {entry['id']!r} already exists in {prior_file} with a different "
                    f"jurisdiction ({prior.get('jurisdiction')!r}) — refusing to move it"
                )
            if prior.get("review_status") in _PROTECTED_STATUSES and not force:
                report.skipped_protected.append(entry["id"])
                continue

        by_file.setdefault(filename, []).append(entry)

    for filename, new_entries in by_file.items():
        path = corpus_dir / filename
        current = _load_file(path)
        index = {d["id"]: i for i, d in enumerate(current)}
        for entry in new_entries:
            if entry["id"] in index:
                current[index[entry["id"]]] = entry
                report.updated.append(entry["id"])
            else:
                current.append(entry)
                report.added.append(entry["id"])
        _dump_file(path, current)
        report.files_written.append(filename)

    return report


def bump_last_verified(
    ids: Iterable[str],
    corpus_dir: Path = config.CORPUS_DIR,
    *,
    today: date | None = None,
) -> List[str]:
    """Set `last_verified` to today for the given corpus ids, in place. Returns the
    ids actually changed."""
    today = today or date.today()
    wanted = set(ids)
    changed: List[str] = []
    for filename in _FILE_BY_JURISDICTION.values():
        path = corpus_dir / filename
        entries = _load_file(path)
        touched = False
        for entry in entries:
            if entry["id"] in wanted and entry.get("last_verified") != today.isoformat():
                entry["last_verified"] = today.isoformat()
                changed.append(entry["id"])
                touched = True
        if touched:
            _dump_file(path, entries)
    return changed
