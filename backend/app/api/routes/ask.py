"""Question answering: a streaming endpoint for the UI and a plain JSON one."""

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import ContainerDep
from app.schemas.ask import AskRequest, AskResponse

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest, c: ContainerDep) -> AskResponse:
    return await c.pipeline.answer(req)


@router.post("/ask/stream")
async def ask_stream(req: AskRequest, c: ContainerDep) -> StreamingResponse:
    """Server-sent events. Event types, in order per jurisdiction:
    `sources` (citations + confidence, sent before generation starts), `delta` (answer
    text chunks), `done` (final, citation-checked answer), and a single closing `end`."""

    async def events():
        async for event in c.pipeline.stream(req):
            yield f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
