from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from packages.task_runtime.a2a import A2AAdapter
from packages.task_runtime.storage.service import (
    get_task_context,
    get_task_contract_for_run,
    get_task_run,
)

router = APIRouter(prefix="/api/v1/a2a", tags=["a2a"])


async def database_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = request.app.state.session_factory
    async with factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(database_session)]
A2AVersionHeader = Annotated[str | None, Header(alias="A2A-Version")]


@router.get("/tasks/{task_id}")
async def get_a2a_task(
    task_id: str,
    session: SessionDep,
    a2a_version: A2AVersionHeader = None,
) -> Response:
    _validate_a2a_version(a2a_version)
    try:
        run = await get_task_run(session, task_id)
        contract = await get_task_contract_for_run(session, task_id)
        context = await get_task_context(session, task_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="task not found",
        ) from exc

    task = A2AAdapter().export_task(run, contract, context)
    return Response(
        content=task.model_dump_json(by_alias=True),
        media_type="application/a2a+json",
        headers={"A2A-Version": "1.0"},
    )


def _validate_a2a_version(value: str | None) -> None:
    if value is None:
        return
    if value == "1.0" or value.startswith("1.0."):
        return
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="unsupported A2A protocol version",
    )
