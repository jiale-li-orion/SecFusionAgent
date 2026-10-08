from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.application.command_idempotency import claim_command, command_digest, complete_command
from apps.application.errors import (
    LifecycleConflictError,
    PermissionDeniedError,
    ResourceNotFoundError,
    RevisionConflictError,
)
from apps.application.queries.investigations import InvestigationQueries
from apps.application.views.investigations import InvestigationView
from packages.investigation.cases.service import CaseService
from packages.investigation.state.contracts import CaseLifecycle
from packages.investigation.storage.models import InvestigationCaseModel
from packages.task_runtime.contracts.models import (
    TERMINAL_TASK_RUN_STATUSES,
    CancellationSemantics,
    TaskRunStatus,
)
from packages.task_runtime.storage.models import TaskRunModel
from packages.task_runtime.storage.service import (
    get_task_contract_for_run,
    transition_task_run,
)


class CancelInvestigationCommand(BaseModel):
    principal: str
    request_id: str
    case_id: str
    reason: str = Field(default="product_cancelled", min_length=1, max_length=128)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)
    expected_revision: int | None = Field(default=None, ge=0)


class CancelInvestigationUseCase:
    def __init__(
        self,
        *,
        task_event_stream_name: str,
        case_service: CaseService | None = None,
        queries: InvestigationQueries | None = None,
    ) -> None:
        self._stream_name = task_event_stream_name
        self._cases = case_service or CaseService()
        self._queries = queries or InvestigationQueries()

    async def execute(
        self,
        session: AsyncSession,
        command: CancelInvestigationCommand,
    ) -> InvestigationView:
        record, replay = await claim_command(
            session,
            principal=command.principal,
            operation="cancel_investigation",
            key=command.idempotency_key,
            digest=command_digest(command.model_dump(
                mode="json", exclude={"principal", "request_id", "idempotency_key"}
            )),
        )
        if replay:
            assert record is not None and record.response_ref is not None
            return await self._queries.get(
                session, record.response_ref, principal=command.principal
            )
        case = await session.scalar(
            select(InvestigationCaseModel)
            .where(InvestigationCaseModel.case_id == command.case_id)
            .with_for_update()
        )
        if case is None:
            raise ResourceNotFoundError(
                "investigation not found",
                context={"case_id": command.case_id},
            )
        controller = await session.scalar(
            select(TaskRunModel)
            .where(
                TaskRunModel.case_id == command.case_id,
                TaskRunModel.role_id == "InvestigationRole",
            )
            .order_by(TaskRunModel.created_at.desc(), TaskRunModel.run_id.desc())
            .limit(1)
        )
        if controller is None:
            raise LifecycleConflictError(
                "investigation has no controller TaskRun",
                context={"case_id": command.case_id},
            )
        controller_contract = await get_task_contract_for_run(session, controller.run_id)
        if controller_contract.principal != command.principal:
            raise PermissionDeniedError(
                "investigation belongs to another principal",
                context={"case_id": command.case_id},
            )
        if (
            command.expected_revision is not None
            and case.current_revision != command.expected_revision
        ):
            raise RevisionConflictError(
                "investigation revision changed",
                context={
                    "case_id": command.case_id,
                    "expected_revision": command.expected_revision,
                    "current_revision": case.current_revision,
                },
            )
        if case.status == CaseLifecycle.CANCELLED.value:
            complete_command(record, command.case_id)
            if record is not None:
                await session.commit()
            return await self._queries.get(
                session,
                command.case_id,
                principal=command.principal,
            )
        if case.status in {CaseLifecycle.RESOLVED.value, CaseLifecycle.CLOSED.value}:
            raise LifecycleConflictError(
                "terminal investigation cannot be cancelled",
                context={"case_id": command.case_id, "status": case.status},
            )

        terminal = [item.value for item in TERMINAL_TASK_RUN_STATUSES]
        runs = list(
            await session.scalars(
                select(TaskRunModel)
                .where(
                    TaskRunModel.case_id == command.case_id,
                    TaskRunModel.status.notin_(terminal),
                )
                .order_by(TaskRunModel.created_at.desc())
                .with_for_update()
            )
        )

        for run in runs:
            contract = await get_task_contract_for_run(session, run.run_id)
            if contract.cancellation_semantics is not CancellationSemantics.CANCELLABLE:
                raise LifecycleConflictError(
                    "task contract does not permit direct cancellation",
                    context={
                        "case_id": command.case_id,
                        "task_run_id": run.run_id,
                        "cancellation_semantics": contract.cancellation_semantics.value,
                    },
                )

        for run in runs:
            await transition_task_run(
                session,
                run_id=run.run_id,
                target=TaskRunStatus.CANCELLED,
                payload_ref=f"product-cancel:{command.request_id}",
                idempotency_key=f"product-cancel:{command.request_id}:{run.run_id}",
                stream_name=self._stream_name,
                producer="product-application",
                stop_reason=command.reason,
            )

        await self._cases.cancel(session, command.case_id)
        complete_command(record, command.case_id)
        await session.commit()
        return await self._queries.get(
            session,
            command.case_id,
            principal=command.principal,
        )
