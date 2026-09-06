#!/usr/bin/env python
"""Rebuild the TF-IDF retrieval index from the /corpus JSON files.

Run this whenever a corpus file changes:
    cd backend && python scripts/build_index.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.vectorstore import VectorStore  # noqa: E402


def main():
    store = VectorStore()
    n = store.build(config.CORPUS_DIR, config.INDEX_DIR)
    print(f"Indexed {n} corpus documents from {config.CORPUS_DIR}")
    print(f"Index written to {config.INDEX_DIR}")


if __name__ == "__main__":
    main()
