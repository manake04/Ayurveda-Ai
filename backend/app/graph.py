"""Lightweight, embedded knowledge graph over the corpus (NetworkX + JSON -- no server to run).

Why a graph on top of retrieval at all: TF-IDF/lexical search only surfaces documents that
share words with the query. A compound question like "I have a phytopharmaceutical using an
Indian plant and want to file in the EU -- what applies?" needs requirements that don't share
vocabulary with each other (a drug-classification rule, an ABS approval duty, and an EU
market-access directive) to be pulled together anyway. That's what this graph is for: it
connects corpus documents to each other and to shared concepts (regime, jurisdiction,
formulation category, administering institution) so retrieval can be *expanded* one hop
along real relationships, not just re-ranked by keyword overlap.

Node id namespaces:
    <corpus-id>            -- a document node, exactly as it appears in corpus/*.json
    regime:<regime>        -- a regime concept node (patent, gi, trademark, ...)
    jurisdiction:<name>    -- "jurisdiction:India" / "jurisdiction:International"
    category:<leaf-id>     -- a formulation-classification leaf, from classifier.TREE
    institution:<name>     -- an administering body (NBA, CDSCO, FSSAI, WIPO, CCPA)

Regime, jurisdiction and formulation-category edges are derived automatically from the
corpus and from classifier.TREE at build time -- they cannot drift out of sync with either.
Only institution links and doc-to-doc relations are hand-authored, in corpus/graph_edges.json,
because those genuinely require a human judgment call about what relates to what.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional

import networkx as nx

from app.classifier import TREE as CLASSIFIER_TREE
from app.corpus_loader import load_corpus


def _regime_node(regime: str) -> str:
    return f"regime:{regime}"


def _jurisdiction_node(jurisdiction: str) -> str:
    return f"jurisdiction:{jurisdiction}"


def _category_node(leaf_id: str) -> str:
    return f"category:{leaf_id}"


class GraphStore:
    def __init__(self):
        self.graph: Optional[nx.MultiDiGraph] = None

    # ---- build ----
    def build(self, corpus_dir: Path, graph_edges_path: Path, graph_dir: Path) -> nx.MultiDiGraph:
        docs = load_corpus(corpus_dir)
        with open(graph_edges_path, "r", encoding="utf-8") as f:
            edges_spec = json.load(f)

        g = nx.MultiDiGraph()

        # Document nodes
        for doc in docs:
            g.add_node(
                doc["id"],
                node_type="document",
                label=doc["title"],
                jurisdiction=doc["jurisdiction"],
                regime=doc["regime"],
                source_url=doc["source_url"],
            )

        # Concept nodes: regimes, jurisdictions (auto-derived from corpus)
        regime_labels = edges_spec.get("regime_labels", {})
        for doc in docs:
            regime_id = _regime_node(doc["regime"])
            if regime_id not in g:
                g.add_node(regime_id, node_type="regime", label=regime_labels.get(doc["regime"], doc["regime"]))
            g.add_edge(doc["id"], regime_id, relation="BELONGS_TO_REGIME")

            jur_id = _jurisdiction_node(doc["jurisdiction"])
            if jur_id not in g:
                g.add_node(jur_id, node_type="jurisdiction", label=doc["jurisdiction"])
            g.add_edge(doc["id"], jur_id, relation="IN_JURISDICTION")

        # Concept nodes: formulation categories (auto-derived from classifier.TREE leaves)
        category_labels = edges_spec.get("category_labels", {})
        doc_ids = {doc["id"] for doc in docs}
        for node_id, node in CLASSIFIER_TREE.items():
            if node["type"] != "result":
                continue
            cat_id = _category_node(node_id)
            g.add_node(cat_id, node_type="category", label=category_labels.get(node_id, node["category"]))
            for corpus_id in node["relevant_corpus_ids"]:
                if corpus_id in doc_ids:
                    g.add_edge(corpus_id, cat_id, relation="RELEVANT_TO_CATEGORY")

        # Concept nodes: institutions (hand-authored)
        for inst in edges_spec.get("institution_nodes", []):
            g.add_node(inst["id"], node_type="institution", label=inst["label"])
        for edge in edges_spec.get("doc_institution", []):
            if edge["source"] in doc_ids:
                g.add_edge(edge["source"], edge["target"], relation="ADMINISTERED_BY")

        # Hand-authored document-to-document relations
        skipped = []
        for edge in edges_spec.get("doc_relations", []):
            if edge["source"] in doc_ids and edge["target"] in doc_ids:
                g.add_edge(edge["source"], edge["target"], relation=edge["relation"])
            else:
                skipped.append(edge)
        if skipped:
            raise ValueError(f"graph_edges.json references unknown corpus id(s): {skipped}")

        self.graph = g

        graph_dir.mkdir(parents=True, exist_ok=True)
        data = nx.node_link_data(g)
        with open(graph_dir / "graph.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return g

    # ---- load ----
    def load(self, graph_dir: Path) -> None:
        with open(graph_dir / "graph.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        self.graph = nx.node_link_graph(data, multigraph=True, directed=True)

    @property
    def is_ready(self) -> bool:
        return self.graph is not None

    # ---- queries ----
    def node(self, node_id: str) -> Optional[Dict]:
        if node_id not in self.graph:
            return None
        return {"id": node_id, **self.graph.nodes[node_id]}

    def related(self, node_id: str, hops: int = 1, relation_filter: Optional[List[str]] = None) -> List[Dict]:
        """Nodes reachable from node_id within `hops` steps (either direction), with the
        connecting relation and hop distance. Used both by the API and by rag.py's
        graph-expansion step."""
        if node_id not in self.graph:
            return []
        undirected = self.graph.to_undirected(as_view=True)
        distances = nx.single_source_shortest_path_length(undirected, node_id, cutoff=hops)
        results = []
        for other_id, dist in distances.items():
            if other_id == node_id:
                continue
            edge_data = None
            if self.graph.has_edge(node_id, other_id):
                edge_data = list(self.graph.get_edge_data(node_id, other_id).values())[0]
            elif self.graph.has_edge(other_id, node_id):
                edge_data = list(self.graph.get_edge_data(other_id, node_id).values())[0]
            relation = edge_data["relation"] if edge_data else None
            if relation_filter and relation not in relation_filter:
                continue
            results.append({"id": other_id, "hops": dist, "relation": relation, **self.graph.nodes[other_id]})
        results.sort(key=lambda r: r["hops"])
        return results

    def path(self, source: str, target: str) -> Optional[List[Dict]]:
        if source not in self.graph or target not in self.graph:
            return None
        undirected = self.graph.to_undirected(as_view=True)
        try:
            node_path = nx.shortest_path(undirected, source, target)
        except nx.NetworkXNoPath:
            return None
        return [{"id": n, **self.graph.nodes[n]} for n in node_path]

    def export(self) -> Dict:
        """Full node-link export for the frontend force-graph visualisation."""
        nodes = [{"id": n, **data} for n, data in self.graph.nodes(data=True)]
        edges = [
            {"source": u, "target": v, "relation": data.get("relation")}
            for u, v, data in self.graph.edges(data=True)
        ]
        return {"nodes": nodes, "edges": edges}


_store: Optional[GraphStore] = None


def get_graph_store(corpus_dir: Path, graph_edges_path: Path, graph_dir: Path) -> GraphStore:
    global _store
    if _store is not None and _store.is_ready:
        return _store
    _store = GraphStore()
    try:
        _store.load(graph_dir)
    except FileNotFoundError:
        _store.build(corpus_dir, graph_edges_path, graph_dir)
    return _store
