"""Tests for the rule-based agentic planner (app/agent.py).

These pin down the two decomposition rules described in agent.py's module docstring
(jurisdiction-probing and regime-diversity splitting) against real corpus data, plus the
end-to-end shape of run_agentic()'s output -- without needing an LLM key, since the whole
point of this module is that it works without one.
"""
import pytest

from app import config
from app.agent import _plan_jurisdictions, _plan_regimes_for, build_plan, run_agentic
from app.graph import GraphStore
from app.vectorstore import VectorStore

COMPOUND_QUERY = (
    "I want to patent a new Ayurvedic formulation and also register its brand name, in both India and abroad"
)


@pytest.fixture(scope="module")
def store():
    s = VectorStore()
    s.build(config.CORPUS_DIR, config.INDEX_DIR)
    return s


@pytest.fixture(scope="module")
def graph_store(tmp_path_factory):
    g = GraphStore()
    graph_dir = tmp_path_factory.mktemp("agent_test_graph")
    g.build(config.CORPUS_DIR, config.GRAPH_EDGES_PATH, graph_dir)
    return g


def test_plan_jurisdictions_both_always_splits_regardless_of_query(store):
    # requested_jurisdiction == "both" is an explicit user choice -- always honoured, even
    # for a query that (per the other tests here) wouldn't trigger auto-detection on its own.
    assert _plan_jurisdictions(store, "totally unrelated filler text", "both") == ["india", "international"]


def test_plan_jurisdictions_stays_single_for_a_narrow_procedural_query(store):
    # A specific India procedural-timeline query shouldn't also pull in an International step.
    jurisdictions = _plan_jurisdictions(
        store,
        "What changed in the Patents Amendment Rules 2024 for request for examination timelines?",
        "india",
    )
    assert jurisdictions == ["india"]


def test_plan_jurisdictions_auto_detects_a_confidently_cross_jurisdiction_query(store):
    # A single-topic trademark query that happens to score confidently in both corpora should
    # surface both jurisdictions even though the caller only asked for one -- this is the
    # "probe the other jurisdiction" rule in action, not just the requested_jurisdiction=="both" case.
    jurisdictions = _plan_jurisdictions(
        store, "How can I register my Ayurvedic brand name in many countries at once?", "international"
    )
    assert "international" in jurisdictions
    assert "india" in jurisdictions


def test_plan_regimes_for_matches_vectorstore_top_regimes(store):
    regimes = _plan_regimes_for(store, COMPOUND_QUERY, "india")
    top = store.top_regimes(COMPOUND_QUERY, "india", limit=8)
    assert regimes == (top if len(top) >= 2 else [None])


def test_compound_query_decomposes_by_jurisdiction_and_regime(store):
    steps = build_plan(store, COMPOUND_QUERY, "both")
    assert len(steps) >= 3
    assert {s.jurisdiction for s in steps} == {"india", "international"}
    india_regimes = {s.regime for s in steps if s.jurisdiction == "india"}
    assert "trademark" in india_regimes and "patent" in india_regimes
    # step_index should be a contiguous 0..n-1 sequence
    assert [s.step_index for s in steps] == list(range(len(steps)))


def test_simple_single_topic_query_does_not_over_decompose(store):
    steps = build_plan(
        store, "What changed in the Patents Amendment Rules 2024 for request for examination timelines?", "india"
    )
    assert len(steps) == 1
    assert steps[0].jurisdiction == "india"
    assert steps[0].regime is None


def test_run_agentic_returns_one_section_per_step(store, graph_store):
    result = run_agentic(store, graph_store, COMPOUND_QUERY, "both", config.TOP_K)
    assert len(result.sections) == len(result.steps)
    assert result.plan_summary and isinstance(result.plan_summary, str)
    for section in result.sections:
        if not section.abstained:
            assert len(section.citations) > 0


def test_run_agentic_labels_regime_split_sections(store, graph_store):
    result = run_agentic(store, graph_store, COMPOUND_QUERY, "both", config.TOP_K)
    regime_steps = [s for s in result.steps if s.regime is not None]
    assert regime_steps
    labelled = [sec for sec in result.sections if sec.label]
    assert len(labelled) == len(regime_steps)
    for sec in labelled:
        assert sec.jurisdiction in sec.label


def test_run_agentic_works_without_a_graph_store(store):
    # The graph layer is an enhancement, not a hard dependency -- agentic mode must still
    # answer (just without graph_related items) when graph_store is None.
    result = run_agentic(store, None, "How can I register my Ayurvedic brand name in many countries at once?", "international", config.TOP_K)
    assert len(result.sections) == len(result.steps)
    for section in result.sections:
        assert section.graph_related == []


def test_run_agentic_never_cites_a_document_not_returned_by_search(store, graph_store):
    result = run_agentic(store, graph_store, COMPOUND_QUERY, "both", config.TOP_K)
    valid_ids = {d["id"] for d in store.docs}
    for section in result.sections:
        for c in section.citations:
            assert c.id in valid_ids
        for c in section.graph_related:
            assert c.id in valid_ids
