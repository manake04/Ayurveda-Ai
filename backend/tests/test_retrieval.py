from app.retrieval.corpus import corpus_fingerprint, document_text
from app.retrieval.vector_store import VectorStore, load_or_build
from tests.conftest import FakeEmbedder


async def test_retrieve_finds_the_relevant_document(retriever):
    result = (await retriever.retrieve("traditional knowledge bar on patentability section 3(p)", ["india"]))[
        "india"
    ]
    assert result.hits[0][0]["id"] == "in-patents-3p"
    assert not result.abstained


async def test_jurisdictions_are_kept_separate(retriever):
    results = await retriever.retrieve("patent filing", ["india", "international"])
    assert all(d["jurisdiction"] == "India" for d, _ in results["india"].hits)
    assert all(d["jurisdiction"] == "International" for d, _ in results["international"].hits)


async def test_off_topic_question_abstains(retriever):
    result = (await retriever.retrieve("zzqx blorf wibble", ["india"]))["india"]
    assert result.abstained and result.confidence == "low"


async def test_hits_are_capped_at_top_k(retriever, settings):
    result = (await retriever.retrieve("patent trademark design copyright", ["india"]))["india"]
    assert len(result.hits) == settings.top_k


async def test_reranker_reorders_hits(settings, store, embedder):
    from app.retrieval.retriever import Retriever

    class ReverseAlphabetical:
        def score(self, query, texts):
            return [float(-i) for i, _ in enumerate(sorted(texts, reverse=True))]

    r = Retriever(settings, store, embedder, ReverseAlphabetical())
    result = (await r.retrieve("patent", ["india"]))["india"]
    scores = [s for _, s in result.hits]
    assert scores == sorted(scores, reverse=True)


async def test_index_round_trips_and_detects_staleness(tmp_path, docs):
    embedder = FakeEmbedder()
    built = await load_or_build(tmp_path, docs, embedder)
    loaded = VectorStore.load(tmp_path, docs, embedder.name)
    assert loaded is not None and [d["id"] for d in loaded.docs] == [d["id"] for d in built.docs]

    assert VectorStore.load(tmp_path, docs, "other:model") is None
    changed = [dict(docs[0], summary="edited"), *docs[1:]]
    assert corpus_fingerprint(changed) != corpus_fingerprint(docs)
    assert VectorStore.load(tmp_path, changed, embedder.name) is None


def test_document_text_includes_citation_and_tags(docs):
    text = document_text(docs[0])
    assert docs[0]["citation"] in text and docs[0]["tags"][0] in text
