"""FastAPI dependencies."""

import re
from typing import Annotated

from fastapi import Depends, Header, Request

from app.core.container import Container

_SESSION_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_session_id(x_session_id: Annotated[str | None, Header()] = None) -> str:
    """Anonymous per-browser id used to scope audit, consent and erasure. Not an account."""
    return x_session_id if x_session_id and _SESSION_ID.match(x_session_id) else "anonymous"


ContainerDep = Annotated[Container, Depends(get_container)]
SessionDep = Annotated[str, Depends(get_session_id)]
