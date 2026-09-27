from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.task_runtime.context.contracts import (
    ChildContextSpec,
    ContextCompatibility,
    ContextDependencySet,
    ContextResultProvenance,
)
from packages.task_runtime.context.service import ContextRevisionGate, derive_child_context
from packages.task_runtime.contracts.models import (
    TERMINAL_TASK_RUN_STATUSES,
    RoleProfile,
    TaskContract,
    TaskRun,
    TaskRunStatus,
    effect_within_ceiling,
)
from packages.task_runtime.storage.models import TaskRunModel
from packages.task_runtime.storage.service import (
    create_task_run,
    get_context_manifest,
    get_task_context,
    get_task_contract_for_run,
)


class TaskResultEnvelope(BaseModel):
    result_id: str
    sender: str
    task_run_id: str
    parent_run_id: str | None = None
    status: TaskRunStatus
    based_on_context_id: str
    based_on_context_revision: int = Field(ge=1)
    payload_ref: str
    evidence_refs: list[str] = Field(default_factory=list)
    state_refs: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    dependencies: ContextDependencySet = Field(default_factory=ContextDependencySet)

    @property
    def context_provenance(self) -> ContextResultProvenance:
        return ContextResultProvenance(
            based_on_context_id=self.based_on_context_id,
            based_on_context_revision=self.based_on_context_revision,
            dependencies=self.dependencies,
        )


async def create_child_task_run(
    session: AsyncSession,
    *,
    parent_run_id: str,
    child_contract: TaskContract,
    child_role: RoleProfile,
    context_spec: ChildContextSpec,
    execution_envelope_ref: str,
    stream_name: str,
    run_id: str | None = None,
    producer: str = "task-runtime",
) -> TaskRun:
    parent = await session.scalar(
        select(TaskRunModel).where(TaskRunModel.run_id == parent_run_id).with_for_update()
    )
    if parent is None:
        raise LookupError(f"parent task run not found: {parent_run_id}")
    if TaskRunStatus(parent.status) is not TaskRunStatus.RUNNING:
        raise ValueError("child task can only be created from a running parent")
    parent_contract = await get_task_contract_for_run(session, parent_run_id)
    _validate_child_delegation(parent_contract, child_contract)
    depth = await _delegation_depth(session, parent_run_id)
    if depth + 1 > parent_contract.delegation_ceiling.max_depth:
        raise ValueError("child task exceeds parent delegation depth ceiling")
    parent_manifest = await get_task_context(session, parent_run_id)
    child_manifest = derive_child_context(
        parent_manifest,
        child_contract=child_contract,
        child_role=child_role,
        spec=context_spec,
    )
    return await create_task_run(
        session,
        contract=child_contract,
        manifest=child_manifest,
        role=child_role,
        execution_envelope_ref=execution_envelope_ref,
        stream_name=stream_name,
        case_id=child_manifest.case_ref,
        parent_run_id=parent_run_id,
        run_id=run_id,
        producer=producer,
    )


async def build_task_result_envelope(
    session: AsyncSession,
    *,
    run_id: str,
    result_id: str,
    dependencies: ContextDependencySet,
    payload_ref: str | None = None,
    evidence_refs: list[str] | None = None,
    state_refs: list[str] | None = None,
    artifact_refs: list[str] | None = None,
) -> TaskResultEnvelope:
    run = await session.get(TaskRunModel, run_id)
    if run is None:
        raise LookupError(f"task run not found: {run_id}")
    status = TaskRunStatus(run.status)
    if status not in TERMINAL_TASK_RUN_STATUSES:
        raise ValueError("TaskResultEnvelope can only be built for a terminal TaskRun")
    manifest = await get_task_context(session, run_id)
    resolved_payload = payload_ref or run.result_ref
    if not resolved_payload:
        raise ValueError("TaskResultEnvelope requires payload_ref or TaskRun.result_ref")
    return TaskResultEnvelope(
        result_id=result_id,
        sender=f"{run.role_id}@{run.role_version}",
        task_run_id=run.run_id,
        parent_run_id=run.parent_run_id,
        status=status,
        based_on_context_id=manifest.context_id,
        based_on_context_revision=manifest.context_revision,
        payload_ref=resolved_payload,
        evidence_refs=sorted(set(evidence_refs or [])),
        state_refs=sorted(set(state_refs or [])),
        artifact_refs=sorted(set(artifact_refs or [])),
        dependencies=dependencies,
    )


async def evaluate_task_result_context(
    session: AsyncSession,
    *,
    result: TaskResultEnvelope,
    current_context_ref: str | None = None,
) -> ContextCompatibility:
    base_ref = f"{result.based_on_context_id}@{result.based_on_context_revision}"
    base = await get_context_manifest(session, base_ref)
    current = (
        await get_context_manifest(session, current_context_ref)
        if current_context_ref is not None
        else await get_task_context(session, result.task_run_id)
    )
    return ContextRevisionGate().evaluate(
        base=base,
        current=current,
        result=result.context_provenance,
    )


def _validate_child_delegation(parent: TaskContract, child: TaskContract) -> None:
    ceiling = parent.delegation_ceiling
    if not ceiling.allowed:
        raise ValueError("parent task contract does not allow delegation")
    if child.task_kind not in set(ceiling.allowed_task_kinds):
        raise ValueError("child task kind exceeds parent delegation ceiling")
    if not effect_within_ceiling(child.effect_ceiling, ceiling.child_effect_ceiling):
        raise ValueError("child task effect exceeds parent delegation ceiling")


async def _delegation_depth(session: AsyncSession, run_id: str) -> int:
    depth = 0
    current = run_id
    seen: set[str] = set()
    while True:
        if current in seen:
            raise RuntimeError("task parent chain contains a cycle")
        seen.add(current)
        run = await session.get(TaskRunModel, current)
        if run is None:
            raise LookupError(f"task run not found while computing delegation depth: {current}")
        if run.parent_run_id is None:
            return depth
        depth += 1
        current = run.parent_run_id
