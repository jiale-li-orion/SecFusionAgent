from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.application.views.agents import (
    AgentBudgetSnapshotView,
    AgentCapabilityActivityView,
    AgentPromptAssemblyView,
    AgentRoleRuntimeView,
    AgentRuntimeOverviewView,
    AgentTaskDetailView,
    AgentTaskEventView,
    AgentTaskSummaryView,
)
from packages.runtime.model.storage import PromptAssemblyRecordModel
from packages.runtime.storage.models import (
    BudgetAccountModel,
    BudgetReservationModel,
    CapabilityInvocationModel,
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


async def get_agent_runtime_overview(
    session: AsyncSession,
    *,
    task_limit: int = 72,
    capability_limit: int = 48,
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
    return AgentRuntimeOverviewView(
        generated_at=datetime.now(UTC),
        roles=roles,
        recent_tasks=summaries,
        recent_capabilities=[_capability_view(item) for item in capabilities],
    )


async def get_agent_task_detail(
    session: AsyncSession,
    run_id: str,
) -> AgentTaskDetailView | None:
    run = await session.get(TaskRunModel, run_id)
    if run is None:
        return None
    summary = (await _task_summaries(session, [run]))[0]
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
    events_by_run: dict[str, list[TaskEventModel]] = defaultdict(list)
    for event in events:
        events_by_run[event.task_run_id].append(event)

    return [
        _task_summary(
            run,
            task_kind=task_kind_by_contract.get(run.task_contract_version_id, "unknown"),
            events=events_by_run.get(run.run_id, []),
        )
        for run in runs
    ]


def _task_summary(
    run: TaskRunModel,
    *,
    task_kind: str,
    events: list[TaskEventModel],
) -> AgentTaskSummaryView:
    latest = events[-1] if events else None
    return AgentTaskSummaryView(
        run_id=run.run_id,
        task_kind=task_kind,
        case_id=run.case_id,
        parent_run_id=run.parent_run_id,
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


async def get_agent_learning_overview(session: AsyncSession):
    from sqlalchemy import func

    from apps.application.views.agents import (
        AgentLearningOverviewView,
        ProductExperienceSupportView,
        ProductExperienceView,
        ProductSkillView,
    )
    from packages.investigation.skills.storage import SkillVersionModel
    from packages.investigation.storage.models import (
        ExperienceCandidateModel,
        ExperienceModel,
        ExperienceSupportModel,
        ExperienceVersionModel,
        InvestigationTrajectoryModel,
    )

    skill_rows = list(
        await session.scalars(
            select(SkillVersionModel).order_by(
                SkillVersionModel.skill_id,
                SkillVersionModel.version.desc(),
            )
        )
    )
    skills: list[ProductSkillView] = []
    seen: set[str] = set()
    for row in skill_rows:
        if row.skill_id in seen:
            continue
        seen.add(row.skill_id)
        manifest = row.manifest_json
        procedure = row.procedure_json
        provenance = row.provenance_json
        skills.append(
            ProductSkillView(
                skill_ref=f"skill:{row.skill_id}@{row.version}",
                skill_id=row.skill_id,
                version=row.version,
                status=row.status,
                source_type=row.source_type,
                task_patterns=list(manifest.get("task_patterns", [])),
                evidence_need_patterns=list(manifest.get("evidence_need_patterns", [])),
                applicable_object_types=list(manifest.get("applicable_object_types", [])),
                applicability_conditions=list(manifest.get("applicability_conditions", [])),
                required_capability_classes=list(manifest.get("required_capability_classes", [])),
                optional_capability_classes=list(manifest.get("optional_capability_classes", [])),
                expected_outcomes=list(manifest.get("expected_outcomes", [])),
                risk_hint=manifest.get("risk_hint"),
                cost_hint=manifest.get("cost_hint"),
                validation_ref=row.validation_ref,
                supersedes=row.supersedes,
                steps=list(procedure.get("steps", [])),
                evidence_expectations=list(procedure.get("evidence_expectations", [])),
                failure_guards=list(procedure.get("failure_guards", [])),
                fallbacks=list(procedure.get("fallbacks", [])),
                stop_conditions=list(procedure.get("stop_conditions", [])),
                provenance_origin=str(provenance.get("origin", "unknown")),
                supporting_trajectory_refs=list(provenance.get("supporting_trajectory_refs", [])),
                supporting_experience_pattern_refs=list(
                    provenance.get("supporting_experience_pattern_refs", [])
                ),
                validation_case_refs=list(provenance.get("validation_case_refs", [])),
                promotion_history=list(provenance.get("promotion_history", [])),
            )
        )

    experience_rows = (
        await session.execute(
            select(ExperienceVersionModel, ExperienceModel)
            .join(
                ExperienceModel,
                ExperienceModel.experience_id == ExperienceVersionModel.experience_id,
            )
            .order_by(ExperienceModel.updated_at.desc(), ExperienceVersionModel.version.desc())
        )
    ).all()
    experience_version_ids = [version.experience_version_id for version, _ in experience_rows]
    support_rows = (
        list(
            await session.scalars(
                select(ExperienceSupportModel)
                .where(ExperienceSupportModel.experience_version_id.in_(experience_version_ids))
                .order_by(
                    ExperienceSupportModel.created_at,
                    ExperienceSupportModel.trajectory_id,
                )
            )
        )
        if experience_version_ids
        else []
    )
    support_trajectory_ids = sorted({row.trajectory_id for row in support_rows})
    support_trajectories = (
        list(
            await session.scalars(
                select(InvestigationTrajectoryModel).where(
                    InvestigationTrajectoryModel.trajectory_id.in_(support_trajectory_ids)
                )
            )
        )
        if support_trajectory_ids
        else []
    )
    support_trajectory_by_id = {item.trajectory_id: item for item in support_trajectories}
    supports_by_version: dict[str, list[ProductExperienceSupportView]] = defaultdict(list)
    for row in support_rows:
        trajectory = support_trajectory_by_id.get(row.trajectory_id)
        if trajectory is None:
            continue
        supports_by_version[row.experience_version_id].append(
            ProductExperienceSupportView(
                trajectory_id=row.trajectory_id,
                case_id=trajectory.case_id,
                trajectory_status=trajectory.status,
                trajectory_outcome=trajectory.outcome,
                latency_ms=trajectory.latency_ms,
                tool_calls=trajectory.tool_calls,
                started_at=trajectory.started_at,
                finished_at=trajectory.finished_at,
                outcome=row.outcome,
                evaluation=dict(row.evaluation),
                evaluator=row.evaluator,
                created_at=row.created_at,
            )
        )

    experiences = [
        ProductExperienceView(
            experience_id=model.experience_id,
            experience_version_id=version.experience_version_id,
            version=version.version,
            name=model.name,
            task_signature=model.task_signature,
            status=version.status,
            trigger_signals=list(version.trigger_signals),
            applicable_conditions=list(version.applicable_conditions),
            recommended_actions=list(version.recommended_actions),
            evidence_expectation=list(version.evidence_expectation),
            failure_modes=list(version.failure_modes),
            stop_conditions=list(version.stop_conditions),
            fallback_actions=list(version.fallback_actions),
            success_count=version.success_count,
            failure_count=version.failure_count,
            partial_count=version.partial_count,
            support_records=supports_by_version.get(version.experience_version_id, []),
        )
        for version, model in experience_rows
    ]
    candidate_count = int(
        await session.scalar(select(func.count()).select_from(ExperienceCandidateModel)) or 0
    )
    trajectory_count = int(
        await session.scalar(select(func.count()).select_from(InvestigationTrajectoryModel)) or 0
    )
    completed_count = int(
        await session.scalar(
            select(func.count())
            .select_from(InvestigationTrajectoryModel)
            .where(InvestigationTrajectoryModel.status == "completed")
        )
        or 0
    )
    return AgentLearningOverviewView(
        skills=skills,
        experiences=experiences,
        experience_candidate_count=candidate_count,
        trajectory_count=trajectory_count,
        completed_trajectory_count=completed_count,
    )
