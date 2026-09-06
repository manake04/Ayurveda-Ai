#!/usr/bin/env python
"""Rebuild the knowledge graph from /corpus + corpus/graph_edges.json + classifier.TREE.

Run this whenever the corpus, graph_edges.json, or the classifier tree changes:
    cd backend && python scripts/build_graph.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.graph import GraphStore  # noqa: E402


def main():
    store = GraphStore()
    g = store.build(config.CORPUS_DIR, config.GRAPH_EDGES_PATH, config.GRAPH_DIR)
    print(f"Built graph: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges")
    by_type = {}
    for _, data in g.nodes(data=True):
        by_type[data["node_type"]] = by_type.get(data["node_type"], 0) + 1
    print("Nodes by type:", by_type)
    print(f"Graph written to {config.GRAPH_DIR / 'graph.json'}")


if __name__ == "__main__":
    main()
