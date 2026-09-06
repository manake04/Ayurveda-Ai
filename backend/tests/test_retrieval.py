import pytest

from app import config
from app.vectorstore import VectorStore


@pytest.fixture(scope="module")
def store():
    s = VectorStore()
    s.build(config.CORPUS_DIR, config.INDEX_DIR)
    return s


def test_index_builds_full_corpus(store):
    assert len(store.docs) >= 25


def test_section_3p_query_retrieves_section_3p(store):
    hits = store.search("Can a classical Ayurvedic formulation be patented in India?", top_k=3, jurisdiction="india")
    ids = [doc["id"] for doc, _ in hits]
    assert "in-patents-3p" in ids


def test_jurisdiction_filter_india_excludes_international(store):
    hits = store.search("traditional knowledge disclosure requirement", top_k=10, jurisdiction="india")
    for doc, _ in hits:
        assert doc["jurisdiction"] == "India"


def test_jurisdiction_filter_international_excludes_india(store):
    hits = store.search("traditional knowledge disclosure requirement", top_k=10, jurisdiction="international")
    for doc, _ in hits:
        assert doc["jurisdiction"] == "International"


def test_wipo_gratk_query_retrieves_correct_doc(store):
    hits = store.search("WIPO treaty genetic resources disclosure 2024", top_k=3, jurisdiction="international")
    ids = [doc["id"] for doc, _ in hits]
    assert "intl-wipo-gratk-treaty-2024" in ids


def test_nonsense_query_gets_low_scores(store):
    hits = store.search("best pizza toppings for a birthday party", top_k=3, jurisdiction="both")
    assert hits[0][1] < config.CONFIDENCE_MEDIUM_THRESHOLD
