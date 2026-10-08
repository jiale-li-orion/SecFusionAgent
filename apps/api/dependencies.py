from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.authentication import verify_authentication_origin
from apps.application.authentication import resolve_authenticated_account
from apps.application.errors import ApplicationError


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


SessionDep = Annotated[AsyncSession, Depends(database_session)]


class AuthenticationRequiredError(ApplicationError):
    code = "authentication_required"


async def request_context(request: Request, session: SessionDep) -> RequestContext:
    account = await resolve_authenticated_account(request, session)
    if account is None:
        raise AuthenticationRequiredError("sign in to access your workspace")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        verify_authentication_origin(request)
    started_at = getattr(request.state, "request_started_at", datetime.now(UTC))
    request_id = getattr(request.state, "request_id", request.headers.get("X-Request-ID", ""))
    return RequestContext(
        request_id=request_id,
        trace_id=request.headers.get("X-Trace-ID"),
        principal=account.principal,
        client_id=request.headers.get("X-Client-ID"),
        idempotency_key=request.headers.get("Idempotency-Key"),
        request_started_at=started_at,
    )


RequestContextDep = Annotated[RequestContext, Depends(request_context)]
