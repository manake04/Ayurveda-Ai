"""FAISS vector store over the corpus, persisted to `data/index/`."""

import json
import logging
from pathlib import Path
from typing import Optional

import faiss
import numpy as np

from app.retrieval.corpus import Document, corpus_fingerprint, document_text
from app.retrieval.embeddings import Embedder

log = logging.getLogger(__name__)

_INDEX_FILE = "index.faiss"
_META_FILE = "meta.json"


class VectorStore:
    def __init__(self, index: faiss.Index, docs: list[Document]):
        self.index = index
        self.docs = docs

    @classmethod
    async def build(cls, docs: list[Document], embedder: Embedder) -> "VectorStore":
        vectors = await embedder.embed_documents([document_text(d) for d in docs])
        # Exact inner-product search: vectors are normalised, so this is cosine similarity.
        # A flat index is the right choice up to ~100k chunks; beyond that, switch to HNSW.
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        return cls(index, docs)

    def save(self, index_dir: Path, embedder_name: str) -> None:
        index_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(index_dir / _INDEX_FILE))
        meta = {
            "embedder": embedder_name,
            "dimension": self.index.d,
            "fingerprint": corpus_fingerprint(self.docs),
            "doc_ids": [d["id"] for d in self.docs],
        }
        (index_dir / _META_FILE).write_text(json.dumps(meta, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, index_dir: Path, docs: list[Document], embedder_name: str) -> Optional["VectorStore"]:
        """Load a persisted index, or return None if it's missing or stale."""
        meta_path = index_dir / _META_FILE
        if not meta_path.exists():
            return None
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("embedder") != embedder_name:
            log.info("Index was built with %s, not %s -- rebuilding", meta.get("embedder"), embedder_name)
            return None
        if meta.get("fingerprint") != corpus_fingerprint(docs):
            log.info("Corpus changed since the index was built -- rebuilding")
            return None
        by_id = {d["id"]: d for d in docs}
        ordered = [by_id[i] for i in meta["doc_ids"]]
        return cls(faiss.read_index(str(index_dir / _INDEX_FILE)), ordered)

    def search(self, query_vector: np.ndarray, k: int) -> list[tuple[Document, float]]:
        k = min(k, len(self.docs))
        scores, ids = self.index.search(query_vector.reshape(1, -1).astype("float32"), k)
        return [(self.docs[i], float(s)) for s, i in zip(scores[0], ids[0], strict=False) if i != -1]


async def load_or_build(index_dir: Path, docs: list[Document], embedder: Embedder) -> VectorStore:
    store = VectorStore.load(index_dir, docs, embedder.name)
    if store is None:
        log.info("Embedding %d documents with %s ...", len(docs), embedder.name)
        store = await VectorStore.build(docs, embedder)
        store.save(index_dir, embedder.name)
    return store
