"""Paid-source connector consent stub.

The problem statement asks for access to the user's OWN paid subscriptions (e.g. a paid
case-law or journal database) "only with explicit, logged permission". This MVP does not
integrate any real paid database (that's a later staged connector), but it implements the
consent-and-audit *pattern* end-to-end: a consent grant is explicit, timestamped, logged
to the audit trail, and revocable -- so the architecture is provably right even before a
real connector is plugged in behind it.
"""
from datetime import datetime, timezone
from typing import Dict

from app import audit
from app.models import ConnectorConsentRequest, ConnectorConsentResponse

# In-memory for the MVP; swap for a real per-user persistent store in production.
_CONSENTS: Dict[str, bool] = {}


def set_consent(req: ConnectorConsentRequest) -> ConnectorConsentResponse:
    _CONSENTS[req.connector_name] = req.granted
    now = datetime.now(timezone.utc).isoformat()

    audit.log_event(
        endpoint="/connectors/consent",
        summary=f"connector={req.connector_name} granted={req.granted} note={req.user_note or ''}",
    )

    if req.granted:
        message = (
            f"Permission recorded: '{req.connector_name}' may be used for your future queries. "
            "You can revoke this at any time from the same panel."
        )
    else:
        message = f"'{req.connector_name}' will not be used. No credentials or content from it are accessed."

    return ConnectorConsentResponse(
        connector_name=req.connector_name,
        granted=req.granted,
        logged_at=now,
        message=message,
    )


def get_consents() -> Dict[str, bool]:
    return dict(_CONSENTS)
