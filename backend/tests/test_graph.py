"""Tests for the NetworkX-backed knowledge graph (app/knowledge/graph.py).

Covers: every corpus document gets a node; regime/jurisdiction/category concept nodes and
edges are correctly auto-derived (so they can't silently drift out of sync with the corpus
or the classifier tree); hand-authored institution and doc-to-doc edges from
corpus/graph_edges.json round-trip through related()/path()/export(); and referential
integrity of graph_edges.json itself, since those ids are hand-maintained and typos there
would otherwise fail silently.
"""

import json

import pytest

from app.domain.classifier import TREE as CLASSIFIER_TREE
from app.knowledge.graph import GraphStore, _category_node, _jurisdiction_node, _regime_node
from tests.conftest import GRAPH_EDGES


@pytest.fixture(scope="module")
def graph_edges_spec():
    return json.loads(GRAPH_EDGES.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def graph_store(docs):
    return GraphStore.build(docs, GRAPH_EDGES)


def test_graph_edges_json_only_references_real_corpus_ids(graph_edges_spec, docs):
    """A hand-maintained-relations integrity check independent of GraphStore.build()'s own
    (fail-fast) validation, so a bad id in graph_edges.json shows up here with a clear
    assertion message rather than only as a build-time crash."""
    doc_ids = {d["id"] for d in docs}
    bad = [
        e
        for e in graph_edges_spec["doc_relations"]
        if e["source"] not in doc_ids or e["target"] not in doc_ids
    ]
    assert not bad, f"doc_relations reference unknown corpus id(s): {bad}"

    bad_inst_sources = [e for e in graph_edges_spec["doc_institution"] if e["source"] not in doc_ids]
    assert not bad_inst_sources, f"doc_institution reference unknown corpus id(s): {bad_inst_sources}"

    institution_ids = {n["id"] for n in graph_edges_spec["institution_nodes"]}
    bad_inst_targets = [e for e in graph_edges_spec["doc_institution"] if e["target"] not in institution_ids]
    assert not bad_inst_targets, f"doc_institution reference undeclared institution id(s): {bad_inst_targets}"


def test_every_corpus_document_has_a_graph_node(graph_store, docs):
    for doc in docs:
        node = graph_store.node(doc["id"])
        assert node is not None, f"missing graph node for corpus doc {doc['id']}"
        assert node["node_type"] == "document"
        assert node["label"] == doc["title"]


def test_regime_and_jurisdiction_nodes_are_auto_derived(graph_store, docs):
    sample = docs[0]
    regime_node = graph_store.node(_regime_node(sample["regime"]))
    jur_node = graph_store.node(_jurisdiction_node(sample["jurisdiction"]))
    assert regime_node is not None and regime_node["node_type"] == "regime"
    assert jur_node is not None and jur_node["node_type"] == "jurisdiction"

    related = graph_store.related(sample["id"], hops=1)
    related_ids = {r["id"] for r in related}
    assert _regime_node(sample["regime"]) in related_ids
    assert _jurisdiction_node(sample["jurisdiction"]) in related_ids


def test_category_nodes_cover_every_classifier_leaf(graph_store):
    for node_id, node in CLASSIFIER_TREE.items():
        if node["type"] != "result":
            continue
        cat_node = graph_store.node(_category_node(node_id))
        assert cat_node is not None, f"missing category node for classifier leaf {node_id}"
        assert cat_node["node_type"] == "category"


def test_institution_node_connects_to_its_documents(graph_store, graph_edges_spec):
    nba_related = graph_store.related("institution:NBA", hops=1)
    doc_neighbors = {r["id"] for r in nba_related if r["node_type"] == "document"}
    expected = {e["source"] for e in graph_edges_spec["doc_institution"] if e["target"] == "institution:NBA"}
    assert expected  # sanity: the fixture data actually has NBA-linked docs
    assert expected.issubset(doc_neighbors)
    for r in nba_related:
        if r["id"] in expected:
            assert r["relation"] == "ADMINISTERED_BY"


def test_related_surfaces_hand_authored_doc_to_doc_relation(graph_store):
    # in-tkdl --SUPPORTS--> in-patents-3p is a hand-authored edge in graph_edges.json.
    related = graph_store.related("in-tkdl", hops=1)
    match = next((r for r in related if r["id"] == "in-patents-3p"), None)
    assert match is not None
    assert match["relation"] == "SUPPORTS"
    assert match["hops"] == 1


def test_related_respects_relation_filter(graph_store):
    all_related = graph_store.related("in-tkdl", hops=1)
    filtered = graph_store.related("in-tkdl", hops=1, relation_filter=["SUPPORTS"])
    assert filtered
    assert all(r["relation"] == "SUPPORTS" for r in filtered)
    assert len(filtered) <= len(all_related)


def test_related_on_unknown_node_returns_empty_list(graph_store):
    assert graph_store.related("no-such-node-id") == []


def test_node_on_unknown_id_returns_none(graph_store):
    assert graph_store.node("no-such-node-id") is None


def test_path_between_two_documents_in_the_same_jurisdiction(graph_store, docs):
    india_doc_ids = [d["id"] for d in docs if d["jurisdiction"] == "India"]
    source, target = india_doc_ids[0], india_doc_ids[-1]
    path = graph_store.path(source, target)
    # Every India document connects to jurisdiction:India, so a path always exists (even if
    # only via that shared concept node).
    assert path is not None
    assert path[0]["id"] == source
    assert path[-1]["id"] == target


def test_path_to_unknown_node_returns_none(graph_store):
    assert graph_store.path("in-tkdl", "no-such-node-id") is None


def test_export_returns_well_formed_nodes_and_edges(graph_store, docs):
    exported = graph_store.export()
    assert len(exported["nodes"]) >= len(docs)
    node_ids = {n["id"] for n in exported["nodes"]}
    for doc in docs:
        assert doc["id"] in node_ids
    for edge in exported["edges"]:
        assert edge["source"] in node_ids
        assert edge["target"] in node_ids


def test_build_raises_on_unknown_doc_relation_id(tmp_path, docs):
    """GraphStore.build()'s own fail-fast check (belt-and-braces alongside the integrity
    test above): a bad id in a graph_edges.json should never be silently swallowed."""
    bad_edges_path = tmp_path / "graph_edges.json"
    bad_edges_path.write_text(
        json.dumps(
            {
                "regime_labels": {},
                "category_labels": {},
                "institution_nodes": [],
                "doc_institution": [],
                "doc_relations": [
                    {"source": "in-tkdl", "target": "not-a-real-doc-id", "relation": "SUPPORTS"}
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        GraphStore.build(docs, bad_edges_path)
