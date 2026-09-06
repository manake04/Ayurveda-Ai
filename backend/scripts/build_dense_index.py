#!/usr/bin/env python
"""Build the optional dense multilingual embedding index (see requirements-dense.txt).

Run this after `pip install -r requirements-dense.txt`, whenever the corpus changes:
    cd backend && python scripts/build_dense_index.py

Safe to run even if the optional library isn't installed -- it prints instructions and
exits cleanly rather than crashing, since this whole feature is meant to be strictly
optional.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.corpus_loader import embedding_text, load_corpus  # noqa: E402
from app.embeddings import DENSE_LIB_AVAILABLE, DEFAULT_MODEL_NAME, DenseIndex  # noqa: E402


def main():
    if not DENSE_LIB_AVAILABLE:
        print(
            "sentence-transformers is not installed -- this is an optional extra.\n"
            "Install it with:  pip install -r requirements-dense.txt\n"
            "then re-run this script. The app works fine without it (pure TF-IDF)."
        )
        return

    docs = load_corpus(config.CORPUS_DIR)
    texts = [embedding_text(d) for d in docs]

    print(f"Encoding {len(docs)} corpus documents with '{DEFAULT_MODEL_NAME}' "
          f"(first run downloads the model, ~470MB)...")
    index = DenseIndex()
    n = index.build(docs, texts, config.DENSE_DIR, model_name=DEFAULT_MODEL_NAME)
    print(f"Built dense index for {n} documents -> {config.DENSE_DIR}")
    print("Restart the backend (or just re-run your next request) to pick it up.")


if __name__ == "__main__":
    main()
