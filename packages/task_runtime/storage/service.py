from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid4, uuid5

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.task_runtime.contracts.conformance import validate_child_contract
from packages.task_runtime.contracts.models import (
    TERMINAL_TASK_RUN_STATUSES,
    ContextManifest,
    RoleProfile,
    TaskContract,
    TaskEvent,
    TaskEventType,
    TaskRun,
    TaskRunStatus,
    can_transition_task_run,
)
from packages.task_runtime.storage.models import (
    ContextManifestVersionModel,
    TaskContractVersionModel,
    TaskEventDeliveryModel,
    TaskEventModel,
    TaskRunModel,
)


class PersistResult(BaseModel):
    ref: str
    replay: bool


class TaskEventAppendResult(BaseModel):
    event: TaskEvent
    replay: bool


def task_contract_ref(contract: TaskContract) -> str:
    return f"{contract.task_contract_id}@{contract.contract_revision}"


def context_manifest_ref(manifest: ContextManifest) -> str:
    return f"{manifest.context_id}@{manifest.context_revision}"


async def persist_task_contract(
    session: AsyncSession,
    contract: TaskContract,
    *,
    now: datetime | None = None,
) -> PersistResult:
    payload = contract.model_dump(mode="json")
    digest = _digest(payload)
    existing = await session.scalar(
        select(TaskContractVersionModel).where(
            TaskContractVersionModel.task_contract_id == contract.task_contract_id,
            TaskContractVersionModel.contract_revision == contract.contract_revision,
        )
    )
    ref = task_contract_ref(contract)
    if existing is not None:
        if existing.content_hash != digest:
            raise ValueError("task contract revision is immutable")
        return PersistResult(ref=ref, replay=True)

    session.add(
        TaskContractVersionModel(
            task_contract_version_id=_stable_id(f"task-contract:{ref}"),
            task_contract_id=contract.task_contract_id,
            contract_revision=contract.contract_revision,
            principal=contract.principal,
            on_behalf_of=contract.on_behalf_of,
            task_kind=contract.task_kind.value,
            effect_ceiling=contract.effect_ceiling.value,
            policy_revision=contract.policy_revision,
            contract_json=payload,
            content_hash=digest,
            created_at=now or datetime.now(UTC),
        )
    )
    await session.flush()
    return PersistResult(ref=ref, replay=False)


async def persist_context_manifest(
    session: AsyncSession,
    manifest: ContextManifest,
    *,
    now: datetime | None = None,
) -> PersistResult:
    contract = await _contract_from_ref(session, manifest.task_contract_ref)
    payload = manifest.model_dump(mode="json")
    digest = _digest(payload)
    existing = await session.scalar(
        select(ContextManifestVersionModel).where(
            ContextManifestVersionModel.context_id == manifest.context_id,
            ContextManifestVersionModel.context_revision == manifest.context_revision,
        )
    )
    ref = context_manifest_ref(manifest)
    if existing is not None:
        if existing.content_hash != digest:
            raise ValueError("context manifest revision is immutable")
        return PersistResult(ref=ref, replay=True)

    session.add(
        ContextManifestVersionModel(
            context_manifest_version_id=_stable_id(f"context-manifest:{ref}"),
            context_id=manifest.context_id,
            context_revision=manifest.context_revision,
            parent_context_id=manifest.parent_context_id,
            task_contract_version_id=contract.task_contract_version_id,
            role_ref=manifest.role_ref,
            case_ref=manifest.case_ref,
            knowledge_revision=manifest.knowledge_revision,
            manifest_json=payload,
            content_hash=digest,
            created_at=now or datetime.now(UTC),
        )
    )
    await session.flush()
    return PersistResult(ref=ref, replay=False)


async def create_task_run(
    session: AsyncSession,
    *,
    contract: TaskContract,
    manifest: ContextManifest,
    role: RoleProfile,
    execution_envelope_ref: str,
    stream_name: str,
    case_id: str | None = None,
    parent_run_id: str | None = None,
    run_id: str | None = None,
    producer: str = "task-runtime",
    now: datetime | None = None,
) -> TaskRun:
    if not role.accepts(contract.task_kind):
        raise ValueError(
            f"role {role.role_id} does not accept task kind {contract.task_kind.value}"
        )
    if manifest.task_contract_ref != task_contract_ref(contract):
        raise ValueError("ContextManifest task_contract_ref does not match TaskContract")
    if manifest.role_ref != f"{role.role_id}@{role.version}":
        raise ValueError("ContextManifest role_ref does not match RoleProfile")

    if parent_run_id is not None:
        parent = await session.scalar(
            select(TaskRunModel).where(TaskRunModel.run_id == parent_run_id).with_for_update()
        )
        if parent is None:
            raise LookupError(f"parent task run not found: {parent_run_id}")
        if TaskRunStatus(parent.status) is not TaskRunStatus.RUNNING:
            raise ValueError("child task can only be created from a running parent")
        parent_contract_model = await session.get(
            TaskContractVersionModel, parent.task_contract_version_id
        )
        if parent_contract_model is None:
            raise RuntimeError("parent task run references missing task contract version")
        parent_contract = TaskContract.model_validate(parent_contract_model.contract_json)
        delegation = validate_child_contract(parent_contract, contract)
        if not delegation.allowed:
            raise ValueError(delegation.reason or "delegation_denied")

    await persist_task_contract(session, contract, now=now)
    await persist_context_manifest(session, manifest, now=now)
    contract_model = await _contract_from_ref(session, task_contract_ref(contract))
    context_model = await _context_from_ref(session, context_manifest_ref(manifest))

    instant = now or datetime.now(UTC)
    resolved_run_id = run_id or str(uuid4())
    if await session.get(TaskRunModel, resolved_run_id) is not None:
        raise ValueError(f"task run already exists: {resolved_run_id}")
    model = TaskRunModel(
        run_id=resolved_run_id,
        task_contract_version_id=contract_model.task_contract_version_id,
        task_contract_id=contract.task_contract_id,
        task_contract_revision=contract.contract_revision,
        context_manifest_version_id=context_model.context_manifest_version_id,
        context_id=manifest.context_id,
        context_revision=manifest.context_revision,
        case_id=case_id,
        parent_run_id=parent_run_id,
        role_id=role.role_id,
        role_version=role.version,
        status=TaskRunStatus.SUBMITTED.value,
        base_context_revision=manifest.context_revision,
        execution_envelope_ref=execution_envelope_ref,
        created_at=instant,
        updated_at=instant,
    )
    session.add(model)
    await session.flush()
    await append_task_event(
        session,
        task_run_id=resolved_run_id,
        event_type=TaskEventType.TASK_CREATED,
        producer=producer,
        base_context_revision=manifest.context_revision,
        payload_ref=f"task-run:{resolved_run_id}",
        idempotency_key=f"task-created:{resolved_run_id}",
        stream_name=stream_name,
        now=instant,
    )
    return _task_run_view(model)


async def claim_queued_task_run(
    session: AsyncSession,
    *,
    run_id: str,
    stream_name: str,
    producer: str = "task-runtime-executor",
    now: datetime | None = None,
) -> TaskRun | None:
    """Atomically claim a queued TaskRun for exactly one Role executor.

    A caller that loses the row-lock race observes the post-claim status and returns
    `None` rather than entering the Role handler. Role implementations may accept an
    already-running run for recovery, but normal worker dispatch must pass through this
    claim boundary to prevent concurrent duplicate execution.
    """

    model = await session.scalar(
        select(TaskRunModel).where(TaskRunModel.run_id == run_id).with_for_update()
    )
    if model is None:
        raise LookupError(f"task run not found: {run_id}")
    if TaskRunStatus(model.status) is not TaskRunStatus.QUEUED:
        return None

    instant = now or datetime.now(UTC)
    model.status = TaskRunStatus.RUNNING.value
    model.updated_at = instant
    await append_task_event(
        session,
        task_run_id=run_id,
        event_type=TaskEventType.TASK_STARTED,
        producer=producer,
        base_context_revision=model.context_revision,
        payload_ref=f"role-claim:{model.role_id}@{model.role_version}",
        idempotency_key=f"role-claim:{run_id}:{model.context_revision}",
        stream_name=stream_name,
        now=instant,
    )
    await session.flush()
    return _task_run_view(model)


async def get_context_manifest(session: AsyncSession, ref: str) -> ContextManifest:
    model = await _context_from_ref(session, ref)
    return ContextManifest.model_validate(model.manifest_json)


async def get_task_context(session: AsyncSession, run_id: str) -> ContextManifest:
    run = await session.get(TaskRunModel, run_id)
    if run is None:
        raise LookupError(f"task run not found: {run_id}")
    model = await session.get(ContextManifestVersionModel, run.context_manifest_version_id)
    if model is None:
        raise RuntimeError("task run references missing context manifest version")
    return ContextManifest.model_validate(model.manifest_json)


async def update_task_context(
    session: AsyncSession,
    *,
    run_id: str,
    manifest: ContextManifest,
    stream_name: str,
    producer: str = "task-runtime",
    now: datetime | None = None,
) -> TaskRun:
    model = await session.scalar(
        select(TaskRunModel).where(TaskRunModel.run_id == run_id).with_for_update()
    )
    if model is None:
        raise LookupError(f"task run not found: {run_id}")
    current_status = TaskRunStatus(model.status)
    if current_status in TERMINAL_TASK_RUN_STATUSES:
        raise ValueError(f"terminal task run is immutable: {current_status.value}")
    expected_contract_ref = f"{model.task_contract_id}@{model.task_contract_revision}"
    if manifest.task_contract_ref != expected_contract_ref:
        raise ValueError("updated context must reference the same task contract revision")
    if manifest.role_ref != f"{model.role_id}@{model.role_version}":
        raise ValueError("updated context must preserve the TaskRun role revision")
    if manifest.context_id == model.context_id:
        if manifest.context_revision <= model.context_revision:
            raise ValueError("updated context revision must advance monotonically")
    elif manifest.parent_context_id != model.context_id:
        raise ValueError("forked context must name the current context as parent_context_id")

    await persist_context_manifest(session, manifest, now=now)
    context_model = await _context_from_ref(session, context_manifest_ref(manifest))
    model.context_manifest_version_id = context_model.context_manifest_version_id
    model.context_id = manifest.context_id
    model.context_revision = manifest.context_revision
    model.base_context_revision = manifest.context_revision
    model.updated_at = now or datetime.now(UTC)
    await append_task_event(
        session,
        task_run_id=run_id,
        event_type=TaskEventType.CONTEXT_UPDATED,
        producer=producer,
        base_context_revision=manifest.context_revision,
        payload_ref=f"context:{context_manifest_ref(manifest)}",
        idempotency_key=f"context-updated:{context_manifest_ref(manifest)}",
        stream_name=stream_name,
        now=now,
    )
    await session.flush()
    return _task_run_view(model)


async def transition_task_run(
    session: AsyncSession,
    *,
    run_id: str,
    target: TaskRunStatus,
    payload_ref: str,
    idempotency_key: str,
    stream_name: str,
    producer: str = "task-runtime",
    result_ref: str | None = None,
    stop_reason: str | None = None,
    now: datetime | None = None,
) -> TaskRun:
    if stop_reason is not None and len(stop_reason) > 128:
        raise ValueError("task stop_reason exceeds storage contract (128 characters)")
    model = await session.scalar(
        select(TaskRunModel).where(TaskRunModel.run_id == run_id).with_for_update()
    )
    if model is None:
        raise LookupError(f"task run not found: {run_id}")
    current = TaskRunStatus(model.status)
    if current in TERMINAL_TASK_RUN_STATUSES:
        raise ValueError(f"terminal task run is immutable: {current.value}")
    if not can_transition_task_run(current, target):
        raise ValueError(f"invalid task run transition: {current.value}->{target.value}")

    instant = now or datetime.now(UTC)
    model.status = target.value
    model.updated_at = instant
    model.result_ref = result_ref
    model.stop_reason = stop_reason
    if target in TERMINAL_TASK_RUN_STATUSES:
        model.finished_at = instant
    await append_task_event(
        session,
        task_run_id=run_id,
        event_type=_event_for_transition(target),
        producer=producer,
        base_context_revision=model.context_revision,
        payload_ref=payload_ref,
        idempotency_key=idempotency_key,
        stream_name=stream_name,
        now=instant,
    )
    await session.flush()
    return _task_run_view(model)


async def append_task_event(
    session: AsyncSession,
    *,
    task_run_id: str,
    event_type: TaskEventType,
    producer: str,
    base_context_revision: int,
    payload_ref: str,
    idempotency_key: str,
    stream_name: str,
    now: datetime | None = None,
) -> TaskEventAppendResult:
    run = await session.scalar(
        select(TaskRunModel).where(TaskRunModel.run_id == task_run_id).with_for_update()
    )
    if run is None:
        raise LookupError(f"task run not found: {task_run_id}")
    existing = await session.scalar(
        select(TaskEventModel).where(
            TaskEventModel.task_run_id == task_run_id,
            TaskEventModel.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return TaskEventAppendResult(event=_task_event_view(existing), replay=True)
    last_seq = await session.scalar(
        select(func.max(TaskEventModel.seq)).where(TaskEventModel.task_run_id == task_run_id)
    )
    seq = int(last_seq or 0) + 1
    instant = now or datetime.now(UTC)
    event = TaskEventModel(
        event_id=str(uuid4()),
        task_run_id=task_run_id,
        parent_run_id=run.parent_run_id,
        seq=seq,
        event_type=event_type.value,
        producer=producer,
        base_context_revision=base_context_revision,
        payload_ref=payload_ref,
        idempotency_key=idempotency_key,
        emitted_at=instant,
    )
    session.add(event)
    await session.flush()
    session.add(
        TaskEventDeliveryModel(
            event_id=event.event_id,
            stream_name=stream_name,
            status="pending",
            attempts=0,
            available_at=instant,
        )
    )
    await session.flush()
    return TaskEventAppendResult(event=_task_event_view(event), replay=False)


async def list_task_events(session: AsyncSession, task_run_id: str) -> list[TaskEvent]:
    models = list(
        await session.scalars(
            select(TaskEventModel)
            .where(TaskEventModel.task_run_id == task_run_id)
            .order_by(TaskEventModel.seq)
        )
    )
    return [_task_event_view(model) for model in models]


async def get_task_event(session: AsyncSession, event_id: str) -> TaskEvent:
    model = await session.get(TaskEventModel, event_id)
    if model is None:
        raise LookupError(f"task event not found: {event_id}")
    return _task_event_view(model)


async def get_task_run(session: AsyncSession, run_id: str) -> TaskRun:
    model = await session.get(TaskRunModel, run_id)
    if model is None:
        raise LookupError(f"task run not found: {run_id}")
    return _task_run_view(model)


async def get_task_contract_for_run(session: AsyncSession, run_id: str) -> TaskContract:
    run = await session.get(TaskRunModel, run_id)
    if run is None:
        raise LookupError(f"task run not found: {run_id}")
    contract = await session.get(TaskContractVersionModel, run.task_contract_version_id)
    if contract is None:
        raise RuntimeError("task run references missing task contract version")
    return TaskContract.model_validate(contract.contract_json)


async def _contract_from_ref(session: AsyncSession, ref: str) -> TaskContractVersionModel:
    task_id, revision = _split_ref(ref)
    model = await session.scalar(
        select(TaskContractVersionModel).where(
            TaskContractVersionModel.task_contract_id == task_id,
            TaskContractVersionModel.contract_revision == revision,
        )
    )
    if model is None:
        raise LookupError(f"task contract not found: {ref}")
    return model


async def _context_from_ref(session: AsyncSession, ref: str) -> ContextManifestVersionModel:
    context_id, revision = _split_ref(ref)
    model = await session.scalar(
        select(ContextManifestVersionModel).where(
            ContextManifestVersionModel.context_id == context_id,
            ContextManifestVersionModel.context_revision == revision,
        )
    )
    if model is None:
        raise LookupError(f"context manifest not found: {ref}")
    return model


def _split_ref(ref: str) -> tuple[str, int]:
    identity, separator, revision_text = ref.rpartition("@")
    if not separator or not identity or not revision_text.isdigit():
        raise ValueError(f"invalid versioned reference: {ref!r}")
    return identity, int(revision_text)


def _event_for_transition(target: TaskRunStatus) -> TaskEventType:
    if target is TaskRunStatus.RUNNING:
        return TaskEventType.TASK_STARTED
    if target is TaskRunStatus.WAITING_INPUT:
        return TaskEventType.NEED_INPUT
    if target is TaskRunStatus.WAITING_DEPENDENCY:
        return TaskEventType.NEED_CONTEXT
    if target is TaskRunStatus.BLOCKED:
        return TaskEventType.TASK_BLOCKED
    if target is TaskRunStatus.COMPLETED:
        return TaskEventType.TASK_COMPLETED
    if target in {TaskRunStatus.FAILED, TaskRunStatus.TIMED_OUT}:
        return TaskEventType.TASK_FAILED
    if target is TaskRunStatus.CANCELLED:
        return TaskEventType.TASK_CANCELED
    return TaskEventType.TASK_PATCHED


def _task_run_view(model: TaskRunModel) -> TaskRun:
    return TaskRun(
        run_id=model.run_id,
        task_contract_id=model.task_contract_id,
        case_id=model.case_id,
        parent_run_id=model.parent_run_id,
        role_id=model.role_id,
        role_version=model.role_version,
        context_manifest_ref=f"{model.context_id}@{model.context_revision}",
        status=TaskRunStatus(model.status),
        base_context_revision=model.base_context_revision,
        execution_envelope_ref=model.execution_envelope_ref,
        result_ref=model.result_ref,
        stop_reason=model.stop_reason,
    )


def _task_event_view(model: TaskEventModel) -> TaskEvent:
    return TaskEvent(
        event_id=model.event_id,
        task_run_id=model.task_run_id,
        parent_run_id=model.parent_run_id,
        seq=model.seq,
        event_type=TaskEventType(model.event_type),
        producer=model.producer,
        base_context_revision=model.base_context_revision,
        payload_ref=model.payload_ref,
        idempotency_key=model.idempotency_key,
        emitted_at=model.emitted_at,
    )


def _digest(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(canonical.encode()).hexdigest()


def _stable_id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"secfusion:{value}"))
