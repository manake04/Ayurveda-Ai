"""Question answering: a streaming endpoint for the UI and a plain JSON one."""

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.api.deps import ContainerDep, SessionDep
from app.schemas.ask import AskRequest, AskResponse

router = APIRouter(tags=["ask"])


def _audit_detail(req: AskRequest, answers: list[dict], latency_ms: int | None) -> dict:
    return {
        "jurisdiction": req.jurisdiction,
        "mode": req.mode,
        "language": req.language,
        "confidence": {a["jurisdiction"]: a.get("confidence") for a in answers},
        "generated_by": {a["jurisdiction"]: a.get("generated_by") for a in answers},
        "latency_ms": latency_ms,
    }


@router.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest, c: ContainerDep, session_id: SessionDep) -> AskResponse:
    resp = await c.pipeline.answer(req)
    detail = _audit_detail(req, [a.model_dump() for a in resp.answers], resp.latency_ms)
    await run_in_threadpool(c.store.log_question, session_id, req.query, **detail)
    return resp


@router.post("/ask/stream")
async def ask_stream(req: AskRequest, c: ContainerDep, session_id: SessionDep) -> StreamingResponse:
    """Server-sent events, in order: `plan` and `step` (agentic mode only), then per
    jurisdiction `sources` (citations + confidence, before generation starts), `delta`
    (answer text chunks) and `done` (final, citation-checked answer), then one `end`."""

    async def events():
        answers: dict[str, dict] = {}
        async for event in c.pipeline.stream(req):
            if event["type"] == "sources":
                answers[event["jurisdiction"]] = {
                    "jurisdiction": event["jurisdiction"],
                    "confidence": event["confidence"],
                }
            elif event["type"] == "done":
                answers[event["jurisdiction"]]["generated_by"] = event["generated_by"]
            elif event["type"] == "end":
                detail = _audit_detail(req, list(answers.values()), event["latency_ms"])
                await run_in_threadpool(c.store.log_question, session_id, req.query, **detail)
            yield f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
