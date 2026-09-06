"""Optional dense multilingual embedding index -- a pluggable upgrade over pure TF-IDF.

This is intentionally NOT a hard dependency (see requirements-dense.txt, kept separate from
requirements.txt): the MVP must keep working, unchanged, for anyone who just does
`pip install -r requirements.txt`. When `sentence-transformers` *is* installed and a dense
index has been built (`python scripts/build_dense_index.py`), `VectorStore` picks it up
automatically and uses it to re-rank TF-IDF's candidate pool (see vectorstore.py) -- nothing
else in the codebase needs to change either way.

Why this matters beyond "better ranking": the chosen model
(paraphrase-multilingual-MiniLM-L12-v2) embeds ~50 languages into the same vector space, so
a Hindi-phrased query can land near an English corpus chunk about the same concept even
though they share zero surface words -- something TF-IDF structurally cannot do. That's a
real, if partial, pull-forward of the "full multilingual retrieval" the roadmap places at
Stage 4: this doesn't translate the *answer*, but it does mean a query in another Indian
language is no longer guaranteed to retrieve nothing.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

try:
    from sentence_transformers import SentenceTransformer

    DENSE_LIB_AVAILABLE = True
except ImportError:  # pragma: no cover -- exercised by not installing the optional extra
    DENSE_LIB_AVAILABLE = False

DEFAULT_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


class DenseIndex:
    def __init__(self):
        self.model: Optional["SentenceTransformer"] = None
        self.model_name: Optional[str] = None
        self.doc_ids: List[str] = []
        self.embeddings: Optional[np.ndarray] = None

    @property
    def is_ready(self) -> bool:
        return self.embeddings is not None and bool(self.doc_ids)

    # ---- build (offline, one-time per corpus change) ----
    def build(self, docs: List[Dict], texts: List[str], dense_dir: Path, model_name: str = DEFAULT_MODEL_NAME) -> int:
        if not DENSE_LIB_AVAILABLE:
            raise RuntimeError(
                "sentence-transformers is not installed. Run "
                "`pip install -r requirements-dense.txt` first (this is an optional extra, "
                "not part of the default install)."
            )
        model = SentenceTransformer(model_name)
        embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        embeddings = np.asarray(embeddings, dtype=np.float32)

        dense_dir.mkdir(parents=True, exist_ok=True)
        np.save(dense_dir / "embeddings.npy", embeddings)
        with open(dense_dir / "meta.json", "w", encoding="utf-8") as f:
            json.dump({"model_name": model_name, "doc_ids": [d["id"] for d in docs]}, f)

        self.model = model
        self.model_name = model_name
        self.doc_ids = [d["id"] for d in docs]
        self.embeddings = embeddings
        return len(docs)

    # ---- load (fast, at server startup) ----
    def load(self, dense_dir: Path) -> None:
        with open(dense_dir / "meta.json", "r", encoding="utf-8") as f:
            meta = json.load(f)
        self.model_name = meta["model_name"]
        self.doc_ids = meta["doc_ids"]
        self.embeddings = np.load(dense_dir / "embeddings.npy")

    # ---- query at request time ----
    def encode_query(self, query: str) -> np.ndarray:
        if not DENSE_LIB_AVAILABLE:
            raise RuntimeError("sentence-transformers is not installed; cannot encode a query.")
        if self.model is None:
            self.model = SentenceTransformer(self.model_name)
        vec = self.model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
        return np.asarray(vec, dtype=np.float32)

    def similarities_by_doc_id(self, query_vec: np.ndarray) -> Dict[str, float]:
        """Cosine similarity (embeddings are pre-normalised, so this is a dot product)
        between the query and every indexed document, keyed by doc id."""
        sims = self.embeddings @ query_vec
        return dict(zip(self.doc_ids, sims.tolist()))
