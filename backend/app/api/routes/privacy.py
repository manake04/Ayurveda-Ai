"""Sources, paid-source consent, escalation to a human, and the user's own data (DPDP)."""

import logging

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.api.deps import ContainerDep, SessionDep
from app.domain.sources import FREE_SOURCES, PAID_CONNECTOR_IDS, PAID_CONNECTORS

log = logging.getLogger(__name__)
router = APIRouter(tags=["privacy"])


class ConsentRequest(BaseModel):
    connector: str
    granted: bool


class EscalationRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    jurisdiction: str = Field("india", pattern=r"^(india|international|both)$")
    contact: str | None = Field(
        None, max_length=200, description="Optional email or phone to be contacted on"
    )
    consent: bool = Field(..., description="User agrees to share the question with a human facilitator")


@router.get("/sources")
def sources():
    return {"free": FREE_SOURCES}


@router.get("/connectors")
async def connectors(c: ContainerDep, session_id: SessionDep):
    consents = await run_in_threadpool(c.store.consents, session_id)
    return [
        {**conn, "connected": False, "consent": consents.get(conn["id"], False)} for conn in PAID_CONNECTORS
    ]


@router.post("/consents")
async def set_consent(body: ConsentRequest, c: ContainerDep, session_id: SessionDep):
    if body.connector not in PAID_CONNECTOR_IDS:
        raise HTTPException(status_code=404, detail=f"Unknown connector: {body.connector}")
    return await run_in_threadpool(c.store.set_consent, session_id, body.connector, body.granted)


@router.post("/escalations", status_code=201)
async def escalate(body: EscalationRequest, c: ContainerDep, session_id: SessionDep):
    if not body.consent:
        raise HTTPException(
            status_code=400, detail="Consent is required to share your question with a person."
        )
    contact = body.contact.strip() if body.contact else None
    ticket = await run_in_threadpool(
        c.store.create_escalation, session_id, body.question.strip(), body.jurisdiction, contact
    )
    url = c.settings.escalation_webhook_url
    if url:
        try:
            await c.http.post(url, json={k: v for k, v in ticket.items() if k != "session_id"}, timeout=10)
        except httpx.HTTPError as exc:
            log.warning("Escalation webhook failed for %s: %s", ticket["id"], exc)
    return {"id": ticket["id"], "status": ticket["status"], "created_at": ticket["ts"]}


@router.get("/privacy/activity")
async def activity(c: ContainerDep, session_id: SessionDep):
    return {"session_id": session_id, "items": await run_in_threadpool(c.store.activity, session_id)}


@router.delete("/privacy/activity")
async def erase(c: ContainerDep, session_id: SessionDep):
    if session_id == "anonymous":
        raise HTTPException(status_code=400, detail="No session id was sent, so there is nothing to delete.")
    return {"deleted": await run_in_threadpool(c.store.erase, session_id)}
