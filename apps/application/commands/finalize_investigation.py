from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.application.queries.decision_sources import decision_citation_sources
from apps.decision_runtime import (
    DecisionExecutionCoordinate,
    DecisionRuntime,
    finish_case_decision_execution,
    open_case_decision_execution,
)
from packages.investigation.cases.service import CaseService
from packages.investigation.state.service import InvestigationStateService
from packages.reasoning.model import ModelDecisionPlanner
from packages.runtime.execution.service import ExecutionRunService
from packages.shared.config import Settings
from packages.shared.model_provider import ModelProvider
from packages.task_runtime.contracts.models import TERMINAL_TASK_RUN_STATUSES, TaskRunStatus
from packages.task_runtime.storage.service import (
    get_task_contract_for_run,
    get_task_run,
)


class FinalizationBusyError(RuntimeError):
    """The existing finalization lease must expire before crash redelivery can resume."""


class FinalizeInvestigationUseCase:
    """Complete Product M5 -> M6 through the existing M4 DecisionCommit gate."""

    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        provider: ModelProvider,
        *,
        lease: Callable[[str], AbstractAsyncContextManager[bool]] | None = None,
    ) -> None:
        self._factory, self._settings, self._provider = factory, settings, provider
        self._lease = lease or (lambda run: _decision_lease(settings, run))

    async def execute(self, parent_run_id: str) -> str | None:
        async with self._lease(parent_run_id) as acquired:
            if not acquired:
                raise FinalizationBusyError(parent_run_id)
            return await self._execute_exclusively(parent_run_id)

    async def _execute_exclusively(self, parent_run_id: str) -> str | None:
        service = InvestigationStateService()
        decision_run_id = str(uuid5(NAMESPACE_URL, f"secfusion:case-decision:{parent_run_id}"))
        async with self._factory() as session, session.begin():
            parent = await get_task_run(session, parent_run_id)
            if parent.status is not TaskRunStatus.COMPLETED or parent.case_id is None:
                return None
            contract = await get_task_contract_for_run(session, parent_run_id)
            if not contract.principal.startswith("user:"):
                return None
            state = await service.get_state(session, parent.case_id)
            try:
                previous = await get_task_run(session, decision_run_id)
            except LookupError:
                previous = None
            if previous is not None and previous.status in TERMINAL_TASK_RUN_STATUSES:
                return previous.result_ref
            if state.current_decision is not None:
                return str(state.current_decision["decision_id"])
            if previous is None:
                coordinate = await open_case_decision_execution(
                    session,
                    settings=self._settings,
                    state=state,
                    principal=contract.principal,
                    request_id=parent_run_id,
                    surface="product-investigation-finalize",
                    run_id=decision_run_id,
                    predecessor_run_id=parent.run_id,
                )
            else:
                coordinate = DecisionExecutionCoordinate(
                    task_run_id=decision_run_id,
                    execution_id=previous.execution_envelope_ref,
                    budget_ref=f"budget:{decision_run_id}",
                )
            citations = await decision_citation_sources(session, state)
            envelope = await ExecutionRunService().get(session, coordinate.execution_id)

        # Provider recording uses its own short transactions; no DB lock spans the model call.
        try:
            remaining = (envelope.deadline_at - datetime.now(UTC)).total_seconds()
            if remaining <= 0:
                raise TimeoutError("Decision execution deadline exhausted")
            proposal = await ModelDecisionPlanner(self._provider).plan(
                state,
                citation_sources=citations,
                include_report=True,
                runtime_metadata={
                    "execution_id": coordinate.execution_id,
                    "task_run_id": coordinate.task_run_id,
                    "budget_ref": coordinate.budget_ref,
                    "model_wall_seconds": remaining,
                },
            )
            async with self._factory() as session, session.begin():
                current_run = await get_task_run(session, decision_run_id)
                if current_run.status in TERMINAL_TASK_RUN_STATUSES:
                    return current_run.result_ref
                outcome = await DecisionRuntime().commit_proposal(
                    session,
                    state=state,
                    proposal=proposal,
                    citation_sources=citations,
                )
                if outcome.decision is not None:
                    result_ref = outcome.decision.decision_id
                    stop_reason = outcome.decision.stop_reason
                    await CaseService().resolve(session, state.case_id)
                else:
                    assert outcome.continuation is not None
                    result_ref = f"evidence-need:{outcome.continuation.need.need_id}"
                    stop_reason = "decision_requires_continuation"
                    await CaseService().wait(session, state.case_id)
                await finish_case_decision_execution(
                    session,
                    settings=self._settings,
                    coordinate=coordinate,
                    result_ref=result_ref,
                    stop_reason=stop_reason,
                    surface="product-investigation-finalize",
                )
                return result_ref
        except Exception as exc:
            async with self._factory() as session, session.begin():
                current_run = await get_task_run(session, decision_run_id)
                if current_run.status not in TERMINAL_TASK_RUN_STATUSES:
                    await finish_case_decision_execution(
                        session,
                        settings=self._settings,
                        coordinate=coordinate,
                        result_ref=f"decision-error:{type(exc).__name__}",
                        stop_reason=f"decision_runtime_error:{type(exc).__name__}",
                        status=TaskRunStatus.FAILED,
                        surface="product-investigation-finalize",
                    )
            raise


@asynccontextmanager
async def _decision_lease(settings: Settings, parent_run_id: str) -> AsyncIterator[bool]:
    # Redis coordinates duplicate deliveries; M4/PostgreSQL still owns the durable outcome.
    redis = Redis.from_url(settings.redis_broker_url)
    lock = redis.lock(
        f"secfusion:decision-finalize:{parent_run_id}",
        timeout=settings.model_timeout_seconds + 30,
    )
    acquired = False
    try:
        acquired = await lock.acquire(blocking=False)
        yield acquired
    finally:
        try:
            if acquired:
                await lock.release()
        finally:
            await redis.aclose()
