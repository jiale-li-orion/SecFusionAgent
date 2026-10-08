from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Response, status

from apps.api.dependencies import RequestContextDep, SessionDep
from apps.application.queries.ownership import visible_task_run_ids
from packages.task_runtime.a2a import A2AAdapter
from packages.task_runtime.storage.models import TaskRunModel
from packages.task_runtime.storage.service import (
    get_task_context,
    get_task_contract_for_run,
    get_task_run,
)

router = APIRouter(prefix="/api/v1/a2a", tags=["a2a"])


A2AVersionHeader = Annotated[str | None, Header(alias="A2A-Version")]


@router.get("/tasks/{task_id}")
async def get_a2a_task(
    task_id: str,
    session: SessionDep,
    identity: RequestContextDep,
    a2a_version: A2AVersionHeader = None,
) -> Response:
    _validate_a2a_version(a2a_version)
    try:
        run = await get_task_run(session, task_id)
        contract = await get_task_contract_for_run(session, task_id)
        visible = await session.scalar(
            visible_task_run_ids(identity.principal).where(TaskRunModel.run_id == task_id)
        )
        if visible is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
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
        headers={"A2A-Version": "1.0", "Cache-Control": "no-store"},
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
