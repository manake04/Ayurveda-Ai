"""Loading the curated corpus (`corpus/*.json`)."""

import hashlib
import json
from pathlib import Path

# Corpus files that hold graph metadata rather than citable documents.
_NON_DOCUMENT_FILES = {"graph_edges.json"}

Document = dict  # one corpus entry; see corpus/README.md


def load_corpus(corpus_dir: Path) -> list[Document]:
    docs: list[Document] = []
    seen = set()
    for path in sorted(corpus_dir.glob("*.json")):
        if path.name in _NON_DOCUMENT_FILES:
            continue
        for entry in json.loads(path.read_text(encoding="utf-8")):
            if entry["id"] in seen:
                raise ValueError(f"Duplicate corpus id '{entry['id']}' in {path.name}")
            seen.add(entry["id"])
            docs.append(entry)
    return docs


def document_text(doc: Document) -> str:
    """The text that represents a document for embedding and reranking."""
    parts = [
        doc.get("title", ""),
        f"{doc.get('instrument', '')}, {doc.get('citation', '')}",
        doc.get("summary", ""),
        doc.get("full_text_excerpt", ""),
        "Keywords: " + ", ".join(doc.get("tags", [])),
    ]
    return "\n".join(p for p in parts if p.strip(" ,"))


def corpus_fingerprint(docs: list[Document]) -> str:
    """Hash of everything that affects embeddings, used to detect a stale index."""
    payload = json.dumps([document_text(d) for d in docs], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
