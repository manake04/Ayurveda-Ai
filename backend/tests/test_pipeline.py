from app.schemas.ask import AskRequest
from tests.conftest import FakeLLM

PATENT_Q = "Can I patent traditional knowledge from a classical formulation under section 3(p)?"


async def collect(pipeline, req):
    return [e async for e in pipeline.stream(req)]


async def test_sources_arrive_before_any_text(make_pipeline):
    events = await collect(make_pipeline(FakeLLM()), AskRequest(query=PATENT_Q))
    types = [e["type"] for e in events]
    assert types[0] == "sources"
    assert types.index("sources") < types.index("delta") < types.index("done")
    assert types[-1] == "end"


async def test_unknown_citation_numbers_are_removed(make_pipeline):
    resp = await make_pipeline(FakeLLM()).answer(AskRequest(query=PATENT_Q))
    answer = resp.answers[0]
    assert "[1]" in answer.answer
    assert "[9]" not in answer.answer  # only 5 sources were given to the model
    assert answer.generated_by == "fake:llm"


async def test_citations_are_only_retrieved_documents(make_pipeline, docs):
    resp = await make_pipeline(FakeLLM()).answer(AskRequest(query=PATENT_Q))
    ids = {d["id"] for d in docs}
    for c in resp.answers[0].citations:
        assert c.id in ids
    assert [c.ref for c in resp.answers[0].citations] == list(range(1, len(resp.answers[0].citations) + 1))


async def test_both_jurisdictions_answered_separately(make_pipeline):
    resp = await make_pipeline(FakeLLM()).answer(
        AskRequest(query="patent application filing", jurisdiction="both")
    )
    assert {a.jurisdiction for a in resp.answers} == {"india", "international"}
    for a in resp.answers:
        label = "India" if a.jurisdiction == "india" else "International"
        assert all(c.jurisdiction == label for c in a.citations)


async def test_abstains_without_calling_the_llm(make_pipeline):
    llm = FakeLLM()
    resp = await make_pipeline(llm).answer(AskRequest(query="zzqx blorf wibble"))
    assert resp.answers[0].abstained and resp.answers[0].citations == []
    assert llm.calls == 0


async def test_llm_failure_falls_back_to_extractive(make_pipeline):
    resp = await make_pipeline(FakeLLM(fail=True)).answer(AskRequest(query=PATENT_Q))
    answer = resp.answers[0]
    assert answer.generated_by == "extractive (fallback)"
    assert answer.citations[0].title in answer.answer


async def test_no_llm_gives_extractive_answer(make_pipeline):
    resp = await make_pipeline(None).answer(AskRequest(query=PATENT_Q))
    assert resp.answers[0].generated_by == "extractive"


async def test_repeat_question_is_served_from_cache(make_pipeline):
    llm = FakeLLM()
    pipeline = make_pipeline(llm)
    first = await pipeline.answer(AskRequest(query=PATENT_Q))
    second = await pipeline.answer(AskRequest(query="  " + PATENT_Q.upper()))
    assert llm.calls == 1
    assert second.answers[0].answer == first.answers[0].answer


async def test_related_sources_come_from_the_graph(make_pipeline):
    resp = await make_pipeline(None).answer(AskRequest(query=PATENT_Q))
    answer = resp.answers[0]
    cited = {c.id for c in answer.citations}
    for r in answer.related:
        assert r.id not in cited
