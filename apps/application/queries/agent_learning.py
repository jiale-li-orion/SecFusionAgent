from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import Row, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import Select

from apps.application.queries.ownership import investigation_owner
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
from packages.task_runtime.storage.models import TaskContractVersionModel, TaskRunModel


async def list_product_skills(session: AsyncSession) -> list[ProductSkillView]:
    rows = list(
        await session.scalars(
            select(SkillVersionModel).order_by(
                SkillVersionModel.skill_id,
                SkillVersionModel.version.desc(),
            )
        )
    )
    latest: list[ProductSkillView] = []
    seen: set[str] = set()
    for row in rows:
        if not _public_skill(row):
            continue
        if row.skill_id in seen:
            continue
        seen.add(row.skill_id)
        latest.append(_skill_view(row))
    return latest


async def get_product_skill(
    session: AsyncSession,
    skill_ref: str,
) -> ProductSkillView | None:
    skill_id, version = _parse_skill_ref(skill_ref)
    statement = select(SkillVersionModel).where(SkillVersionModel.skill_id == skill_id)
    if version is not None:
        statement = statement.where(SkillVersionModel.version == version)
    row = await session.scalar(statement.order_by(SkillVersionModel.version.desc()).limit(1))
    return _skill_view(row) if row is not None and _public_skill(row) else None


async def list_product_experiences(session: AsyncSession) -> list[ProductExperienceView]:
    rows = (
        await session.execute(
            select(ExperienceVersionModel, ExperienceModel)
            .join(
                ExperienceModel,
                ExperienceModel.experience_id == ExperienceVersionModel.experience_id,
            )
            .order_by(ExperienceModel.updated_at.desc(), ExperienceVersionModel.version.desc())
        )
    ).all()
    return await _experience_views(session, rows)


async def get_product_experience(
    session: AsyncSession,
    experience_ref: str,
) -> ProductExperienceView | None:
    statement = (
        select(ExperienceVersionModel, ExperienceModel)
        .join(
            ExperienceModel,
            ExperienceModel.experience_id == ExperienceVersionModel.experience_id,
        )
        .where(
            (ExperienceVersionModel.experience_version_id == experience_ref)
            | (ExperienceModel.experience_id == experience_ref)
        )
        .order_by(ExperienceVersionModel.version.desc())
        .limit(1)
    )
    row = (await session.execute(statement)).first()
    if row is None:
        return None
    views = await _experience_views(session, [row])
    return views[0] if views else None


async def get_agent_learning_overview(session: AsyncSession) -> AgentLearningOverviewView:
    skills = await list_product_skills(session)
    experiences = await list_product_experiences(session)
    candidate_count = int(
        await session.scalar(
            select(func.count())
            .select_from(ExperienceCandidateModel)
            .where(ExperienceCandidateModel.source_trajectory_id.in_(_public_trajectory_ids()))
        )
        or 0
    )
    trajectory_count = int(
        await session.scalar(
            select(func.count())
            .select_from(InvestigationTrajectoryModel)
            .where(InvestigationTrajectoryModel.trajectory_id.in_(_public_trajectory_ids()))
        )
        or 0
    )
    completed_count = int(
        await session.scalar(
            select(func.count())
            .select_from(InvestigationTrajectoryModel)
            .where(InvestigationTrajectoryModel.status == "completed")
            .where(InvestigationTrajectoryModel.trajectory_id.in_(_public_trajectory_ids()))
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


def _public_trajectory_ids() -> Select[str]:
    private_run = (
        select(TaskRunModel.run_id)
        .join(
            TaskContractVersionModel,
            TaskContractVersionModel.task_contract_version_id
            == TaskRunModel.task_contract_version_id,
        )
        .where(
            TaskRunModel.case_id == InvestigationTrajectoryModel.case_id,
            or_(
                TaskContractVersionModel.principal.startswith("user:"),
                TaskContractVersionModel.on_behalf_of.startswith("user:"),
            ),
        )
        .exists()
    )
    return select(InvestigationTrajectoryModel.trajectory_id).where(
        investigation_owner(InvestigationTrajectoryModel.case_id).startswith("system:"),
        ~private_run,
    )


def _public_skill(row: SkillVersionModel) -> bool:
    # Only platform seeds have an explicit public publication boundary today.
    # Learned/imported content must not become public merely by entering the registry.
    return row.source_type in {"seed", "seeded"} and not any(
        row.provenance_json.get(key)
        for key in ("supporting_trajectory_refs", "supporting_experience_pattern_refs")
    )


def _json_object(source: dict[str, object]) -> dict[str, Any]:
    """Read a persisted JSON column as an untyped mapping.

    The SQLAlchemy column type cannot express the stored schema, so the stored
    payload reaches the view constructor as ``object``. ``ProductSkillView``
    validates each extracted field, which keeps this cast at the storage
    boundary instead of widening the column type for every consumer.
    """
    return cast("dict[str, Any]", source)


def _skill_view(row: SkillVersionModel) -> ProductSkillView:
    manifest = _json_object(row.manifest_json)
    procedure = _json_object(row.procedure_json)
    provenance = _json_object(row.provenance_json)
    return ProductSkillView(
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


async def _experience_views(
    session: AsyncSession,
    rows: Sequence[Row[ExperienceVersionModel, ExperienceModel]],
) -> list[ProductExperienceView]:
    version_ids = [version.experience_version_id for version, _ in rows]
    if not version_ids:
        return []
    support_rows = list(
        await session.scalars(
            select(ExperienceSupportModel)
            .where(ExperienceSupportModel.experience_version_id.in_(version_ids))
            .order_by(
                ExperienceSupportModel.created_at,
                ExperienceSupportModel.trajectory_id,
            )
        )
    )
    trajectory_ids = sorted({row.trajectory_id for row in support_rows})
    trajectories = (
        list(
            await session.scalars(
                select(InvestigationTrajectoryModel).where(
                    InvestigationTrajectoryModel.trajectory_id.in_(trajectory_ids)
                )
            )
        )
        if trajectory_ids
        else []
    )
    trajectory_by_id = {item.trajectory_id: item for item in trajectories}
    public_trajectories = set(await session.scalars(_public_trajectory_ids()))
    public_candidates = set(
        await session.scalars(
            select(ExperienceCandidateModel.candidate_id).where(
                ExperienceCandidateModel.source_trajectory_id.in_(public_trajectories)
            )
        )
    )
    supports_by_id: dict[str, list[ExperienceSupportModel]] = defaultdict(list)
    for support in support_rows:
        supports_by_id[support.experience_version_id].append(support)
    # A mixed version can contain private question-derived recommendations and counts.
    # Exclude the whole version, not just its private support links.
    public_rows = [
        (version, model)
        for version, model in rows
        if supports_by_id[version.experience_version_id]
        and (
            version.source_candidate_id is None or version.source_candidate_id in public_candidates
        )
        and all(
            support.trajectory_id in public_trajectories
            for support in supports_by_id[version.experience_version_id]
        )
    ]
    supports_by_version: dict[str, list[ProductExperienceSupportView]] = defaultdict(list)
    for row in support_rows:
        trajectory = trajectory_by_id.get(row.trajectory_id)
        if trajectory is None or row.trajectory_id not in public_trajectories:
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
    return [
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
        for version, model in public_rows
    ]


def _parse_skill_ref(value: str) -> tuple[str, int | None]:
    normalized = value.removeprefix("skill:")
    skill_id, separator, raw_version = normalized.rpartition("@")
    if separator and raw_version.isdigit():
        return skill_id, int(raw_version)
    return normalized, None
