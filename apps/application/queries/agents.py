from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

from pydantic import JsonValue
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.application.views.agents import (
    AgentBudgetSnapshotView,
    AgentCapabilityActivityView,
    AgentControlledProofCaseView,
    AgentControlledProofView,
    AgentControlRuntimeView,
    AgentModelRuntimeView,
    AgentPromptAssemblyView,
    AgentRoleRuntimeView,
    AgentRuntimeOverviewView,
    AgentTaskDetailView,
    AgentTaskEventView,
    AgentTaskPageView,
    AgentTaskSummaryView,
)
from packages.runtime.model.storage import (
    ModelAttemptModel,
    ModelRequestModel,
    PromptAssemblyRecordModel,
)
from packages.runtime.storage.models import (
    BudgetAccountModel,
    BudgetReservationModel,
    CapabilityInvocationModel,
    ExecutionRunModel,
)
from packages.task_runtime.contracts.models import TaskRunStatus
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.models import (
    TaskContractVersionModel,
    TaskEventModel,
    TaskRunModel,
)

_ACTIVE_STATUSES = {
    TaskRunStatus.SUBMITTED.value,
    TaskRunStatus.QUEUED.value,
    TaskRunStatus.RUNNING.value,
    TaskRunStatus.WAITING_INPUT.value,
    TaskRunStatus.WAITING_DEPENDENCY.value,
}
_AGENT_RUNTIME_PROOF = Path("benchmarks/agent-runtime/current.json")


def get_agent_controlled_proof() -> AgentControlledProofView:
    payload = json.loads(_AGENT_RUNTIME_PROOF.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases", {})
    cases: list[AgentControlledProofCaseView] = []
    if isinstance(raw_cases, dict):
        for case_id, raw_case in raw_cases.items():
            if not isinstance(case_id, str) or not isinstance(raw_case, dict):
                continue
            diagnostics_raw = raw_case.get("diagnostics", {})
            diagnostics = (
                cast(dict[str, JsonValue], diagnostics_raw)
                if isinstance(diagnostics_raw, dict)
                else {}
            )
            metrics_raw = raw_case.get("metrics", {})
            metrics = {
                str(name): float(value)
                for name, value in metrics_raw.items()
                if isinstance(name, str) and isinstance(value, int | float)
            } if isinstance(metrics_raw, dict) else {}
            cases.append(
                AgentControlledProofCaseView(
                    case_id=case_id,
                    subsystem=_optional_string(diagnostics.get("subsystem")),
                    metrics=metrics,
                    diagnostics=diagnostics,
                    task_run_ids=_diagnostic_refs(diagnostics, suffix="_run_id"),
                    evidence_refs=_diagnostic_list_refs(diagnostics, contains="evidence_ref"),
                    capability_invocation_ids=_diagnostic_list_refs(
                        diagnostics,
                        contains="capability_invocation_id",
                    ),
                )
            )
    return AgentControlledProofView(
        schema_version=str(payload.get("schema_version", "unknown")),
        benchmark_run_id=str(payload["benchmark_run_id"]),
        deployment_revision_id=str(payload["deployment_revision_id"]),
        suite_ref=str(payload["suite_ref"]),
        execution_mode=str(payload["execution_mode"]),
        scope=str(payload["scope"]),
        cases=cases,
    )


def _diagnostic_refs(values: dict[str, JsonValue], *, suffix: str) -> list[str]:
    refs = {
        value
        for key, value in values.items()
        if key.endswith(suffix) and isinstance(value, str) and value
    }
    return sorted(refs)


def _diagnostic_list_refs(values: dict[str, JsonValue], *, contains: str) -> list[str]:
    refs: set[str] = set()
    for key, value in values.items():
        if contains not in key:
            continue
        if isinstance(value, str) and value:
            refs.add(value)
        elif isinstance(value, list):
            refs.update(item for item in value if isinstance(item, str) and item)
    return sorted(refs)


async def get_agent_runtime_overview(
    session: AsyncSession,
    *,
    task_limit: int = 72,
    capability_limit: int = 48,
    model_request_limit: int = 64,
) -> AgentRuntimeOverviewView:
    runs = list(
        await session.scalars(
            select(TaskRunModel).order_by(TaskRunModel.updated_at.desc()).limit(task_limit)
        )
    )
    summaries = await _task_summaries(session, runs)
    status_rows = (
        await session.execute(
            select(TaskRunModel.role_id, TaskRunModel.status, func.count())
            .group_by(TaskRunModel.role_id, TaskRunModel.status)
        )
    ).all()
    updated_rows = (
        await session.execute(
            select(TaskRunModel.role_id, func.max(TaskRunModel.updated_at)).group_by(
                TaskRunModel.role_id
            )
        )
    ).all()
    status_by_role: dict[str, Counter[str]] = defaultdict(Counter)
    for role_id, status, count in status_rows:
        status_by_role[role_id][status] = int(count)
    updated_by_role = {role_id: updated_at for role_id, updated_at in updated_rows}

    roles: list[AgentRoleRuntimeView] = []
    for profile in canonical_roles().values():
        counts = status_by_role.get(profile.role_id, Counter())
        roles.append(
            AgentRoleRuntimeView(
                role_id=profile.role_id,
                version=profile.version,
                state_model=profile.state_model,
                planner_profile=profile.planner_profile,
                default_execution_profile=profile.default_execution_profile.value,
                accepted_task_kinds=[item.value for item in profile.accepts_task_kinds],
                skill_scope=list(profile.skill_scope),
                status_counts=dict(sorted(counts.items())),
                active_tasks=sum(counts.get(status, 0) for status in _ACTIVE_STATUSES),
                total_tasks=sum(counts.values()),
                last_updated_at=updated_by_role.get(profile.role_id),
            )
        )

    capabilities = list(
        await session.scalars(
            select(CapabilityInvocationModel)
            .order_by(CapabilityInvocationModel.started_at.desc())
            .limit(capability_limit)
        )
    )
    model_runtime = await _model_runtime_view(
        session,
        request_limit=model_request_limit,
    )
    control_runtime = await _control_runtime_view(
        session,
        runs,
    )
    return AgentRuntimeOverviewView(
        generated_at=datetime.now(UTC),
        roles=roles,
        recent_tasks=summaries,
        recent_capabilities=[_capability_view(item) for item in capabilities],
        model_runtime=model_runtime,
        control_runtime=control_runtime,
    )


async def list_agent_tasks(
    session: AsyncSession,
    *,
    role_id: str | None = None,
    status: str | None = None,
    case_id: str | None = None,
    limit: int = 72,
) -> AgentTaskPageView:
    statement = select(TaskRunModel)
    if role_id:
        statement = statement.where(TaskRunModel.role_id == role_id)
    if status:
        statement = statement.where(TaskRunModel.status == status)
    if case_id:
        statement = statement.where(TaskRunModel.case_id == case_id)
    runs = list(
        await session.scalars(
            statement.order_by(TaskRunModel.updated_at.desc()).limit(limit)
        )
    )
    return AgentTaskPageView(
        generated_at=datetime.now(UTC),
        items=await _task_summaries(session, runs),
    )


async def _model_runtime_view(
    session: AsyncSession,
    *,
    request_limit: int,
) -> AgentModelRuntimeView:
    requests = list(
        await session.scalars(
            select(ModelRequestModel)
            .order_by(ModelRequestModel.created_at.desc())
            .limit(request_limit)
        )
    )
    if not requests:
        return AgentModelRuntimeView(
            scope="latest_persisted_model_requests",
            request_limit=request_limit,
        )
    request_ids = [item.model_request_id for item in requests]
    attempts = list(
        await session.scalars(
            select(ModelAttemptModel)
            .where(ModelAttemptModel.model_request_id.in_(request_ids))
            .order_by(ModelAttemptModel.started_at)
        )
    )
    latencies = sorted(
        int(item.latency_ms)
        for item in attempts
        if item.latency_ms is not None
    )
    provider_counts = Counter(item.provider for item in attempts)
    model_counts = Counter(item.actual_model for item in attempts)
    latest_attempt = max(
        (item.started_at for item in attempts),
        default=None,
    )
    return AgentModelRuntimeView(
        scope="latest_persisted_model_requests",
        request_limit=request_limit,
        request_count=len(requests),
        attempt_count=len(attempts),
        retry_attempt_count=sum(1 for item in attempts if item.ordinal > 1),
        retry_scheduled_count=sum(
            1
            for item in attempts
            if item.response_metadata_json.get("retry_scheduled") is True
        ),
        failed_attempt_count=sum(1 for item in attempts if item.status == "failed"),
        unknown_after_dispatch_count=sum(
            1
            for item in attempts
            if item.status == "unknown_after_dispatch"
        ),
        p95_latency_ms=_nearest_rank_p95(latencies),
        provider_counts=dict(sorted(provider_counts.items())),
        model_counts=dict(sorted(model_counts.items())),
        latest_attempt_at=latest_attempt,
    )


async def _control_runtime_view(
    session: AsyncSession,
    runs: list[TaskRunModel],
) -> AgentControlRuntimeView:
    if not runs:
        return AgentControlRuntimeView(scope="recent_task_read_window")
    run_ids = [item.run_id for item in runs]
    events = list(
        await session.scalars(
            select(TaskEventModel).where(TaskEventModel.task_run_id.in_(run_ids))
        )
    )
    stop_reasons = Counter(
        item.stop_reason
        for item in runs
        if item.stop_reason
    )
    return AgentControlRuntimeView(
        scope="recent_task_read_window",
        sampled_task_count=len(runs),
        dependency_wake_count=sum(
            1
            for item in events
            if item.producer == "task-runtime-scheduler"
            and item.event_type == "TaskPatched"
        ),
        waiting_event_count=sum(
            1
            for item in events
            if item.event_type in {"NeedInput", "NeedContext"}
        ),
        stop_reason_counts=dict(sorted(stop_reasons.items())),
        wake_latency_ms=None,
        wake_latency_measurement="unavailable",
    )


def _nearest_rank_p95(values: list[int]) -> int | None:
    if not values:
        return None
    index = max(0, (95 * len(values) + 99) // 100 - 1)
    return values[min(index, len(values) - 1)]


async def get_agent_task_detail(
    session: AsyncSession,
    run_id: str,
) -> AgentTaskDetailView | None:
    run = await session.get(TaskRunModel, run_id)
    if run is None:
        return None
    summary = (await _task_summaries(session, [run]))[0]
    related_runs = list(
        await session.scalars(
            select(TaskRunModel)
            .where(
                (TaskRunModel.run_id == run.parent_run_id)
                | (TaskRunModel.run_id == summary.predecessor_run_id)
                | (TaskRunModel.parent_run_id == run_id)
            )
            .order_by(TaskRunModel.created_at)
        )
    )
    related_summaries = await _task_summaries(session, related_runs)
    parent = next(
        (item for item in related_summaries if item.run_id == run.parent_run_id),
        None,
    )
    children = [item for item in related_summaries if item.parent_run_id == run_id]
    events = list(
        await session.scalars(
            select(TaskEventModel)
            .where(TaskEventModel.task_run_id == run_id)
            .order_by(TaskEventModel.seq)
        )
    )
    capabilities = list(
        await session.scalars(
            select(CapabilityInvocationModel)
            .where(CapabilityInvocationModel.task_run_id == run_id)
            .order_by(CapabilityInvocationModel.started_at)
        )
    )
    prompt_assemblies = list(
        await session.scalars(
            select(PromptAssemblyRecordModel)
            .where(PromptAssemblyRecordModel.task_run_id == run_id)
            .order_by(PromptAssemblyRecordModel.created_at.desc())
        )
    )
    budget = await _budget_snapshot_view(session, run_id)
    return AgentTaskDetailView(
        task=summary,
        parent=parent,
        predecessor=next(
            (item for item in related_summaries if item.run_id == summary.predecessor_run_id),
            None,
        ),
        children=children,
        events=[
            AgentTaskEventView(
                event_id=item.event_id,
                seq=item.seq,
                event_type=item.event_type,
                producer=item.producer,
                emitted_at=item.emitted_at,
            )
            for item in events
        ],
        capabilities=[_capability_view(item) for item in capabilities],
        budget=budget,
        prompt_assemblies=[
            AgentPromptAssemblyView(
                assembly_id=item.assembly_id,
                execution_id=item.execution_id,
                context_manifest_ref=item.context_manifest_ref,
                role_revision=item.role_revision,
                execution_profile_revision=item.execution_profile_revision,
                materialized_skill_refs=list(item.materialized_skill_refs_json),
                materialized_capability_view_refs=list(
                    item.materialized_capability_view_refs_json
                ),
                percept_refs=list(item.percept_refs_json),
                materialized_ref_set_digest=item.materialized_ref_set_digest,
                created_at=item.created_at,
            )
            for item in prompt_assemblies
        ],
    )


async def _budget_snapshot_view(
    session: AsyncSession,
    run_id: str,
) -> AgentBudgetSnapshotView | None:
    account = await session.scalar(
        select(BudgetAccountModel).where(BudgetAccountModel.task_run_id == run_id)
    )
    if account is None:
        return None
    rows = list(
        await session.scalars(
            select(BudgetReservationModel).where(
                BudgetReservationModel.account_id == account.account_id
            )
        )
    )
    limits = {key: Decimal(value) for key, value in account.limits.items()}
    reserved: dict[str, Decimal] = {}
    committed: dict[str, Decimal] = {}
    for row in rows:
        if row.status == "reserved":
            reserved[row.resource_type] = reserved.get(
                row.resource_type, Decimal("0")
            ) + Decimal(row.amount_reserved)
        elif row.status == "committed":
            committed[row.resource_type] = committed.get(
                row.resource_type, Decimal("0")
            ) + Decimal(row.amount_committed)
    remaining = {
        resource: max(
            Decimal("0"),
            limit
            - reserved.get(resource, Decimal("0"))
            - committed.get(resource, Decimal("0")),
        )
        for resource, limit in limits.items()
    }
    return AgentBudgetSnapshotView(
        account_id=account.account_id,
        limits={key: float(value) for key, value in limits.items()},
        reserved={key: float(value) for key, value in reserved.items()},
        committed={key: float(value) for key, value in committed.items()},
        remaining={key: float(value) for key, value in remaining.items()},
    )


async def _task_summaries(
    session: AsyncSession,
    runs: list[TaskRunModel],
) -> list[AgentTaskSummaryView]:
    if not runs:
        return []
    contract_ids = {item.task_contract_version_id for item in runs}
    contract_models = list(
        await session.scalars(
            select(TaskContractVersionModel).where(
                TaskContractVersionModel.task_contract_version_id.in_(contract_ids)
            )
        )
    )
    task_kind_by_contract = {
        item.task_contract_version_id: item.task_kind for item in contract_models
    }
    run_ids = [item.run_id for item in runs]
    events = list(
        await session.scalars(
            select(TaskEventModel)
            .where(TaskEventModel.task_run_id.in_(run_ids))
            .order_by(TaskEventModel.task_run_id, TaskEventModel.seq)
        )
    )
    executions = list(await session.scalars(
        select(ExecutionRunModel).where(ExecutionRunModel.task_run_id.in_(run_ids))
    ))
    predecessor_by_run = {
        item.task_run_id: _execution_predecessor_run_id(item)
        for item in executions
    }
    events_by_run: dict[str, list[TaskEventModel]] = defaultdict(list)
    for event in events:
        events_by_run[event.task_run_id].append(event)

    return [
        _task_summary(
            run,
            task_kind=task_kind_by_contract.get(run.task_contract_version_id, "unknown"),
            events=events_by_run.get(run.run_id, []),
            predecessor_run_id=predecessor_by_run.get(run.run_id),
        )
        for run in runs
    ]


def _task_summary(
    run: TaskRunModel,
    *,
    task_kind: str,
    events: list[TaskEventModel],
    predecessor_run_id: str | None = None,
) -> AgentTaskSummaryView:
    latest = events[-1] if events else None
    return AgentTaskSummaryView(
        run_id=run.run_id,
        task_kind=task_kind,
        case_id=run.case_id,
        parent_run_id=run.parent_run_id,
        predecessor_run_id=predecessor_run_id,
        role_id=run.role_id,
        role_version=run.role_version,
        status=run.status,
        stop_reason=run.stop_reason,
        result_available=run.result_ref is not None,
        event_count=len(events),
        last_event_type=latest.event_type if latest else None,
        last_event_at=latest.emitted_at if latest else None,
        created_at=run.created_at,
        updated_at=run.updated_at,
        finished_at=run.finished_at,
    )


def _capability_view(item: CapabilityInvocationModel) -> AgentCapabilityActivityView:
    result = item.result_json or {}
    return AgentCapabilityActivityView(
        invocation_id=item.invocation_id,
        task_run_id=item.task_run_id,
        case_id=item.case_id,
        capability_id=item.capability_id,
        binding_id=item.binding_id,
        tool_impl_id=item.tool_impl_id,
        status=item.status,
        started_at=item.started_at,
        finished_at=item.finished_at,
        failure_code=item.failure_code,
        failure_detail=item.failure_detail,
        policy_decision_ref=item.policy_decision_ref,
        canonical_output_ref=_optional_string(result.get("canonical_output_ref")),
        raw_artifact_ref=_optional_string(result.get("raw_artifact_ref")),
        effect_receipt_ref=_optional_string(result.get("effect_receipt_ref")),
        observation_class=_optional_string(result.get("observation_class")),
    )


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _execution_predecessor_run_id(execution: ExecutionRunModel) -> str | None:
    trace = execution.envelope_json.get("trace_context", {})
    if not isinstance(trace, dict):
        return None
    explicit = _optional_string(trace.get("predecessor_run_id"))
    if explicit is not None:
        return explicit
    if trace.get("surface") == "product-investigation-finalize":
        return _optional_string(trace.get("request_id"))
    return None
