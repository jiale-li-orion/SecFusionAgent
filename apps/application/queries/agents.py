from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.application.views.agents import (
    AgentCapabilityActivityView,
    AgentRoleRuntimeView,
    AgentRuntimeOverviewView,
    AgentTaskDetailView,
    AgentTaskEventView,
    AgentTaskSummaryView,
)
from packages.runtime.storage.models import CapabilityInvocationModel
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
    )


async def get_agent_learning_overview(session: AsyncSession):
    from sqlalchemy import func

    from apps.application.views.agents import (
        AgentLearningOverviewView,
        ProductExperienceView,
        ProductSkillView,
    )
    from packages.investigation.skills.storage import SkillVersionModel
    from packages.investigation.storage.models import (
        ExperienceCandidateModel,
        ExperienceModel,
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
                supporting_experience_pattern_refs=list(provenance.get("supporting_experience_pattern_refs", [])),
                validation_case_refs=list(provenance.get("validation_case_refs", [])),
                promotion_history=list(provenance.get("promotion_history", [])),
            )
        )

    experience_rows = (
        await session.execute(
            select(ExperienceVersionModel, ExperienceModel)
            .join(ExperienceModel, ExperienceModel.experience_id == ExperienceVersionModel.experience_id)
            .order_by(ExperienceModel.updated_at.desc(), ExperienceVersionModel.version.desc())
        )
    ).all()
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
