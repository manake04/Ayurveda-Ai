"""Loads the curated JSON corpus files from the /corpus directory."""
import json
from pathlib import Path
from typing import Dict, List


_NON_DOCUMENT_FILES = {"graph_edges.json"}


def load_corpus(corpus_dir: Path) -> List[Dict]:
    """Load every document-list *.json file in corpus_dir (each a list of document dicts).

    Excludes non-document corpus files such as graph_edges.json, which holds the
    hand-authored knowledge-graph edges (a dict, not a list of documents) rather than
    citable corpus entries.
    """
    docs: List[Dict] = []
    seen_ids = set()
    for path in sorted(corpus_dir.glob("*.json")):
        if path.name in _NON_DOCUMENT_FILES:
            continue
        with open(path, "r", encoding="utf-8") as f:
            entries = json.load(f)
        for entry in entries:
            if entry["id"] in seen_ids:
                raise ValueError(f"Duplicate corpus id '{entry['id']}' found in {path.name}")
            seen_ids.add(entry["id"])
            docs.append(entry)
    return docs


def embedding_text(doc: Dict) -> str:
    """The text used to build the retrieval index for one document."""
    parts = [
        doc.get("title", ""),
        doc.get("instrument", ""),
        doc.get("citation", ""),
        doc.get("summary", ""),
        " ".join(doc.get("tags", [])),
    ]
    return ". ".join(p for p in parts if p)
