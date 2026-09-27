from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession


class RequestContext(BaseModel):
    request_id: str
    trace_id: str | None = None
    principal: str
    client_id: str | None = None
    idempotency_key: str | None = None
    request_started_at: datetime
    api_version: str = "v1"


async def database_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = request.app.state.session_factory
    async with factory() as session:
        yield session


def request_context(request: Request) -> RequestContext:
    started_at = getattr(request.state, "request_started_at", datetime.now(UTC))
    request_id = getattr(request.state, "request_id", request.headers.get("X-Request-ID", ""))
    principal = request.headers.get("X-Principal", "user:local")
    return RequestContext(
        request_id=request_id,
        trace_id=request.headers.get("X-Trace-ID"),
        principal=principal,
        client_id=request.headers.get("X-Client-ID"),
        idempotency_key=request.headers.get("Idempotency-Key"),
        request_started_at=started_at,
    )


SessionDep = Annotated[AsyncSession, Depends(database_session)]
RequestContextDep = Annotated[RequestContext, Depends(request_context)]
