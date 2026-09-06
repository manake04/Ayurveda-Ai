"""A small, dependency-light TF-IDF vector store, with an optional dense-embedding re-ranker.

Why TF-IDF as the foundation: the corpus is a small set of precisely-worded legal/
regulatory chunks with distinctive terminology (section numbers, treaty names, defined
terms) -- exactly the setting where sparse lexical retrieval is strong, reliable, fully
free, and installs in seconds with no model download. It is also easy for a reviewer to
audit ("why was this cited?" -> shared keywords, inspectable). This remains the
zero-configuration default: `pip install -r requirements.txt` alone gets a fully working,
tested retrieval pipeline with no download beyond the pip packages themselves.

The optional upgrade: if `python scripts/build_dense_index.py` has been run (which requires
the separate `requirements-dense.txt` extra), `VectorStore` opportunistically loads that
dense multilingual index and uses it to *re-rank* TF-IDF's own candidate pool via
Reciprocal Rank Fusion -- see `search()` below. Crucially, the *score* attached to each
returned document is always the original TF-IDF cosine similarity, never a fused score --
that's what keeps the carefully-tuned confidence/abstention thresholds (see
docs/ROADMAP.md's eval numbers) valid whether or not dense re-ranking is active. Without a
built dense index, behaviour is byte-for-byte identical to the TF-IDF-only MVP.
"""
import json
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.corpus_loader import embedding_text, load_corpus
from app.embeddings import DenseIndex

_RRF_K = 60  # standard Reciprocal Rank Fusion constant


class VectorStore:
    def __init__(self):
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.matrix = None
        self.docs: List[Dict] = []
        self.dense: Optional[DenseIndex] = None

    # ---- build ----
    def build(self, corpus_dir: Path, index_dir: Path) -> int:
        self.docs = load_corpus(corpus_dir)
        texts = [embedding_text(d) for d in self.docs]
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            stop_words="english",
            sublinear_tf=True,
        )
        self.matrix = self.vectorizer.fit_transform(texts)

        index_dir.mkdir(parents=True, exist_ok=True)
        with open(index_dir / "vectorizer.pkl", "wb") as f:
            pickle.dump(self.vectorizer, f)
        with open(index_dir / "matrix.pkl", "wb") as f:
            pickle.dump(self.matrix, f)
        with open(index_dir / "docs.json", "w", encoding="utf-8") as f:
            json.dump(self.docs, f, ensure_ascii=False, indent=2)
        return len(self.docs)

    # ---- load ----
    def load(self, index_dir: Path) -> None:
        with open(index_dir / "vectorizer.pkl", "rb") as f:
            self.vectorizer = pickle.load(f)
        with open(index_dir / "matrix.pkl", "rb") as f:
            self.matrix = pickle.load(f)
        with open(index_dir / "docs.json", "r", encoding="utf-8") as f:
            self.docs = json.load(f)

    @property
    def is_ready(self) -> bool:
        return self.vectorizer is not None and self.matrix is not None and bool(self.docs)

    def attach_dense(self, dense: DenseIndex) -> None:
        """Wire in a pre-built dense index, iff it was built from the same corpus (by doc id
        set, not just count) -- a stale dense index for a since-changed corpus is worse than
        none, so a mismatch is silently ignored rather than risking a wrong re-rank."""
        current_ids = {d["id"] for d in self.docs}
        if dense.is_ready and set(dense.doc_ids) == current_ids:
            self.dense = dense

    # ---- search ----
    def search(
        self,
        query: str,
        top_k: int = 5,
        jurisdiction: Optional[str] = None,
        regime: Optional[str] = None,
    ) -> List[Tuple[Dict, float]]:
        if not self.is_ready:
            raise RuntimeError("Vector store not built/loaded. Run scripts/build_index.py first.")

        query_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(query_vec, self.matrix).flatten()

        order = np.argsort(-sims)
        filtered_order: List[int] = []
        for idx in order:
            doc = self.docs[idx]
            if jurisdiction and jurisdiction != "both":
                target = "India" if jurisdiction == "india" else "International"
                if doc["jurisdiction"] != target:
                    continue
            if regime and doc["regime"] != regime:
                continue
            filtered_order.append(idx)
        if not filtered_order:
            return []

        final_order = filtered_order[:top_k]
        if self.dense is not None and self.dense.is_ready:
            final_order = self._dense_rerank(query, filtered_order, top_k)

        return [(self.docs[idx], float(sims[idx])) for idx in final_order]

    def _dense_rerank(self, query: str, filtered_order: List[int], top_k: int) -> List[int]:
        """Reciprocal Rank Fusion of the TF-IDF ranking with the dense-embedding ranking,
        over a widened candidate pool from TF-IDF (so dense re-ranking can only reshuffle
        documents TF-IDF already considered plausible, never invent new candidates out of
        thin air)."""
        pool = filtered_order[: max(top_k * 4, 20)]
        try:
            query_vec = self.dense.encode_query(query)
        except Exception:  # noqa: BLE001 -- any dense-side failure just falls back to TF-IDF order
            return filtered_order[:top_k]
        dense_sims_by_id = self.dense.similarities_by_doc_id(query_vec)

        tfidf_rank = {idx: r for r, idx in enumerate(pool)}
        dense_order = sorted(pool, key=lambda idx: -dense_sims_by_id.get(self.docs[idx]["id"], -1.0))
        dense_rank = {idx: r for r, idx in enumerate(dense_order)}

        fused = sorted(pool, key=lambda idx: -(1 / (_RRF_K + tfidf_rank[idx]) + 1 / (_RRF_K + dense_rank[idx])))
        return fused[:top_k]

    def top_regimes(self, query: str, jurisdiction: Optional[str], limit: int = 6, relative_ratio: float = 0.55, floor: float = 0.075) -> List[str]:
        """Distinct regimes represented among the top `limit` hits, ordered by best score.

        Used by the agentic planner to detect a compound, multi-regime question. A single
        absolute score cutoff (like the one used for answer confidence/abstention) doesn't
        work well here: a compound query's relevance to any *one* regime is naturally lower
        than a single-topic query's relevance to its one topic, since the query's own text
        is split across multiple concerns. So this uses a threshold relative to the query's
        own top score instead (a regime counts if its best hit scores at least
        `relative_ratio` of the top hit's score, or `floor`, whichever is higher) -- this
        adapts to each query's own score scale rather than assuming a fixed bar.
        """
        hits = self.search(query, top_k=limit, jurisdiction=jurisdiction)
        if not hits:
            return []
        top_score = hits[0][1]
        threshold = max(top_score * relative_ratio, floor)
        regimes: List[str] = []
        for doc, score in hits:
            if score >= threshold and doc["regime"] not in regimes:
                regimes.append(doc["regime"])
        return regimes


_store: Optional[VectorStore] = None


def get_store(corpus_dir: Path, index_dir: Path, dense_dir: Optional[Path] = None) -> VectorStore:
    """Singleton accessor: loads the persisted index, building it first if missing.

    If `dense_dir` is given and holds a dense index built by scripts/build_dense_index.py
    (and sentence-transformers is installed), it's attached opportunistically. Any failure
    here (missing files, missing optional library) is silently ignored -- dense re-ranking
    is a bonus, never a requirement to run this app.
    """
    global _store
    if _store is not None and _store.is_ready:
        return _store
    _store = VectorStore()
    try:
        _store.load(index_dir)
    except FileNotFoundError:
        _store.build(corpus_dir, index_dir)

    if dense_dir is not None:
        try:
            dense = DenseIndex()
            dense.load(dense_dir)
            _store.attach_dense(dense)
        except Exception:  # noqa: BLE001 -- optional upgrade; never block startup on it
            pass

    return _store
