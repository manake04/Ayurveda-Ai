import json

import httpx
import pytest

from app.core.container import Container
from app.main import create_app
from app.store import Store
from tests.conftest import FakeLLM


@pytest.fixture
async def client(settings, docs, graph, retriever, make_pipeline):
    llm = FakeLLM()
    container = Container(
        settings, httpx.AsyncClient(), docs, graph, retriever, [llm], make_pipeline(llm), Store(":memory:")
    )
    app = create_app(settings, container)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


SESSION = {"X-Session-Id": "test-session-1234"}


async def test_health(client):
    body = (await client.get("/api/health")).json()
    assert body["status"] == "ok" and body["documents"] == 45


async def test_ask_returns_cited_answer(client):
    r = await client.post(
        "/api/ask", json={"query": "section 3(p) traditional knowledge patent", "jurisdiction": "india"}
    )
    assert r.status_code == 200
    answer = r.json()["answers"][0]
    assert answer["citations"] and answer["answer"]


async def test_ask_rejects_too_short_query(client):
    assert (await client.post("/api/ask", json={"query": "hi"})).status_code == 422


async def test_ask_stream_emits_sse_events(client):
    r = await client.post(
        "/api/ask/stream", json={"query": "patent traditional knowledge", "jurisdiction": "both"}
    )
    assert r.headers["content-type"].startswith("text/event-stream")
    events = [json.loads(line[5:]) for line in r.text.splitlines() if line.startswith("data:")]
    assert [e["type"] for e in events].count("done") == 2
    assert events[-1]["type"] == "end"


async def test_graph_endpoints(client):
    graph = (await client.get("/api/graph")).json()
    assert len(graph["nodes"]) > 45
    assert (await client.get("/api/graph/nodes/in-tkdl/related")).status_code == 200
    assert (await client.get("/api/graph/nodes/nope/related")).status_code == 404


async def test_tools(client):
    assert (await client.post("/api/classify", json={"answers": ["yes"]})).json()["done"] is True
    abs_body = {
        "uses_biological_material": True,
        "sourced_from_india": True,
        "ip_or_commercialisation_sought": True,
    }
    assert (await client.post("/api/abs-checklist", json=abs_body)).json()["checklist"][0]["applies"] is True
    tkdl = (await client.get("/api/tkdl-pointer", params={"query": "turmeric"})).json()
    assert len(tkdl["search_links"]) == 4


async def test_config_exposes_languages_and_escalation(client):
    body = (await client.get("/api/config")).json()
    assert [lang["code"] for lang in body["languages"]] == ["auto", "en", "hi"]  # no Bhashini configured
    assert body["escalation"]["url"].startswith("https://")
    assert body["agentic"] is True


async def test_questions_are_audited_without_their_text(client):
    q = "section 3(p) traditional knowledge patent"
    await client.post("/api/ask/stream", json={"query": q}, headers=SESSION)
    items = (await client.get("/api/privacy/activity", headers=SESSION)).json()["items"]
    assert items[0]["type"] == "question"
    assert "query" not in items[0]["detail"] and items[0]["detail"]["query_chars"] == len(q)
    assert items[0]["detail"]["generated_by"]["india"] == "fake:llm"


async def test_consent_escalation_and_erasure(client):
    connectors = (await client.get("/api/connectors", headers=SESSION)).json()
    assert all(not c["connected"] and not c["consent"] for c in connectors)
    r = await client.post("/api/consents", json={"connector": "manupatra", "granted": True}, headers=SESSION)
    assert r.json()["granted"] is True
    assert (
        await client.post("/api/consents", json={"connector": "nope", "granted": True})
    ).status_code == 404

    body = {"question": "Can I patent this?", "jurisdiction": "india", "consent": False}
    assert (await client.post("/api/escalations", json=body, headers=SESSION)).status_code == 400
    ticket = (await client.post("/api/escalations", json={**body, "consent": True}, headers=SESSION)).json()
    assert ticket["id"].startswith("ESC-")

    types = {i["type"] for i in (await client.get("/api/privacy/activity", headers=SESSION)).json()["items"]}
    assert {"consent", "escalation"} <= types
    assert (await client.delete("/api/privacy/activity", headers=SESSION)).json()["deleted"] >= 2
    assert (await client.get("/api/privacy/activity", headers=SESSION)).json()["items"] == []


async def test_sessions_are_isolated_and_anonymous_cannot_erase(client):
    await client.post("/api/consents", json={"connector": "scc-online", "granted": True}, headers=SESSION)
    other = {"X-Session-Id": "another-session-99"}
    assert (await client.get("/api/privacy/activity", headers=other)).json()["items"] == []
    assert (await client.delete("/api/privacy/activity")).status_code == 400
