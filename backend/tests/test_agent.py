from app.rag import agent
from app.schemas.ask import AskRequest
from tests.conftest import FakeLLM

COMPOUND = "Can I patent a traditional knowledge formulation and register its trade mark brand name?"
PLAN = {
    "steps": [
        {"question": "Is traditional knowledge patentable under section 3(p)?", "jurisdictions": ["india"]},
        {"question": "How do I register a trade mark brand name?", "jurisdictions": ["india", "nowhere"]},
    ]
}


async def test_plan_keeps_only_allowed_jurisdictions():
    steps = await agent.plan([FakeLLM(plan=PLAN)], COMPOUND, ["india"], max_steps=3)
    assert [s.jurisdictions for s in steps] == [["india"], ["india"]]


async def test_plan_returns_empty_when_llm_fails():
    assert await agent.plan([FakeLLM(fail=True)], COMPOUND, ["india"], 3) == []


async def test_agentic_answer_merges_sources_from_each_sub_question(make_pipeline):
    llm = FakeLLM(plan=PLAN)
    pipeline = make_pipeline(llm)
    events = [e async for e in pipeline.stream(AskRequest(query=COMPOUND, mode="agentic"))]
    types = [e["type"] for e in events]
    assert types[0] == "plan" and types.count("step") == 2
    assert types.index("step") < types.index("sources")

    sources = next(e for e in events if e["type"] == "sources")
    ids = {c["id"] for c in sources["citations"]}
    assert "in-patents-3p" in ids and "in-trademarks-act-1999" in ids

    system, prompt = llm.prompts[-1]
    assert "Parts of the question" in prompt and "Relevant to part(s)" in prompt
    assert "several parts" in system


async def test_single_step_plan_falls_back_to_standard(make_pipeline):
    plan = {"steps": [{"question": "Is traditional knowledge patentable?", "jurisdictions": ["india"]}]}
    resp = await make_pipeline(FakeLLM(plan=plan)).answer(AskRequest(query=COMPOUND, mode="agentic"))
    assert resp.plan is None and resp.answers[0].citations


async def test_agentic_plan_is_replayed_from_cache(make_pipeline):
    llm = FakeLLM(plan=PLAN)
    pipeline = make_pipeline(llm)
    first = await pipeline.answer(AskRequest(query=COMPOUND, mode="agentic"))
    second = await pipeline.answer(AskRequest(query=COMPOUND, mode="agentic"))
    assert second.plan == first.plan and len(first.plan) == 2
    assert llm.calls == 1


async def test_each_jurisdiction_only_answers_its_own_sub_questions(make_pipeline):
    plan = {
        "steps": [
            {
                "question": "Is traditional knowledge patentable under section 3(p)?",
                "jurisdictions": ["india"],
            },
            {"question": "How do I register a trade mark brand name?", "jurisdictions": ["india"]},
            {
                "question": "How does the Madrid system register a trademark abroad?",
                "jurisdictions": ["international"],
            },
        ]
    }
    llm = FakeLLM(plan=plan)
    await make_pipeline(llm).answer(AskRequest(query=COMPOUND, jurisdiction="both", mode="agentic"))
    prompts = {("India" in p and "Jurisdiction to cover: India" in p): p for _, p in llm.prompts}
    india, international = prompts[True], prompts[False]
    assert "Madrid" not in india.split("Sources:")[0] and "Parts of the question" in india
    # One relevant sub-question -> an ordinary single-part prompt
    assert "Parts of the question" not in international
