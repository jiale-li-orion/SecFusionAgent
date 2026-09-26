from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.investigation.storage.models import (
    ExperienceCandidateModel,
    ExperienceModel,
    ExperienceSupportModel,
    ExperienceVersionModel,
    InvestigationTrajectoryModel,
)

EXPERIENCE_STATUSES = frozenset({"candidate", "validated", "active", "deprecated"})
EVALUATION_OUTCOMES = frozenset({"success", "failure", "partial"})


class ExperienceDraft(BaseModel):
    name: str
    task_signature: str
    scope: dict[str, object] = Field(default_factory=dict)
    trigger_signals: list[str] = Field(default_factory=list)
    applicable_conditions: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    evidence_expectation: list[str] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)
    fallback_actions: list[str] = Field(default_factory=list)


class ExperienceCandidate(BaseModel):
    candidate_id: str
    source_trajectory_id: str
    extraction_kind: str
    draft: ExperienceDraft
    rationale: str
    status: str
    created_at: datetime


class ExperienceVersion(BaseModel):
    experience_id: str
    experience_version_id: str
    version: int
    name: str
    task_signature: str
    status: str
    scope: dict[str, object] = Field(default_factory=dict)
    trigger_signals: list[str] = Field(default_factory=list)
    applicable_conditions: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    evidence_expectation: list[str] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)
    fallback_actions: list[str] = Field(default_factory=list)
    validation_summary: dict[str, object] = Field(default_factory=dict)
    success_count: int
    failure_count: int
    partial_count: int
    last_validated_at: datetime | None = None
    supersedes_version_id: str | None = None


class ExperienceStore:
    """Versioned policy memory. It never grants evidence authority."""

    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(UTC))

    async def create_candidate(
        self,
        session: AsyncSession,
        *,
        source_trajectory_id: str,
        extraction_kind: str,
        draft: ExperienceDraft,
        rationale: str,
    ) -> ExperienceCandidate:
        trajectory = await session.get(InvestigationTrajectoryModel, source_trajectory_id)
        if trajectory is None:
            raise LookupError(f"trajectory not found: {source_trajectory_id}")
        if trajectory.status != "completed":
            raise ValueError("experience extraction requires a completed trajectory")
        if extraction_kind not in {
            "procedure",
            "failure_pattern",
            "stop_condition",
            "fallback",
        }:
            raise ValueError(f"unsupported experience extraction kind: {extraction_kind}")
        now = self._now()
        model = ExperienceCandidateModel(
            candidate_id=str(uuid4()),
            source_trajectory_id=source_trajectory_id,
            extraction_kind=extraction_kind,
            draft=draft.model_dump(mode="json"),
            rationale=rationale,
            status="pending",
            created_at=now,
        )
        session.add(model)
        await session.flush()
        return _candidate_view(model)

    async def reject_candidate(
        self,
        session: AsyncSession,
        candidate_id: str,
    ) -> None:
        candidate = await session.get(ExperienceCandidateModel, candidate_id)
        if candidate is None:
            raise LookupError(f"experience candidate not found: {candidate_id}")
        if candidate.status == "accepted":
            raise ValueError("accepted experience candidate cannot be rejected")
        candidate.status = "rejected"
        candidate.decided_at = self._now()

    async def materialize_candidate(
        self,
        session: AsyncSession,
        candidate_id: str,
        *,
        experience_id: str | None = None,
    ) -> ExperienceVersion:
        candidate = await session.scalar(
            select(ExperienceCandidateModel)
            .where(ExperienceCandidateModel.candidate_id == candidate_id)
            .with_for_update()
        )
        if candidate is None:
            raise LookupError(f"experience candidate not found: {candidate_id}")
        if candidate.status == "rejected":
            raise ValueError("rejected experience candidate cannot be materialized")
        existing_version = await session.scalar(
            select(ExperienceVersionModel).where(
                ExperienceVersionModel.source_candidate_id == candidate_id
            )
        )
        if existing_version is not None:
            experience = await session.get(ExperienceModel, existing_version.experience_id)
            if experience is None:
                raise RuntimeError("experience version exists without experience")
            return _version_view(experience, existing_version)

        draft = ExperienceDraft.model_validate(candidate.draft)
        now = self._now()
        if experience_id is None:
            experience = ExperienceModel(
                experience_id=str(uuid4()),
                name=draft.name,
                task_signature=draft.task_signature,
                current_version_id=None,
                created_at=now,
                updated_at=now,
            )
            session.add(experience)
            version_number = 1
            supersedes = None
        else:
            experience = await session.scalar(
                select(ExperienceModel)
                .where(ExperienceModel.experience_id == experience_id)
                .with_for_update()
            )
            if experience is None:
                raise LookupError(f"experience not found: {experience_id}")
            if experience.task_signature != draft.task_signature:
                raise ValueError("experience revision cannot change task_signature")
            max_version = await session.scalar(
                select(func.max(ExperienceVersionModel.version)).where(
                    ExperienceVersionModel.experience_id == experience_id
                )
            )
            version_number = int(max_version or 0) + 1
            supersedes = experience.current_version_id
            experience.name = draft.name
            experience.updated_at = now

        version = ExperienceVersionModel(
            experience_version_id=str(uuid4()),
            experience_id=experience.experience_id,
            version=version_number,
            status="candidate",
            scope=draft.scope,
            trigger_signals=draft.trigger_signals,
            applicable_conditions=draft.applicable_conditions,
            recommended_actions=draft.recommended_actions,
            evidence_expectation=draft.evidence_expectation,
            failure_modes=draft.failure_modes,
            stop_conditions=draft.stop_conditions,
            fallback_actions=draft.fallback_actions,
            validation_summary={},
            success_count=0,
            failure_count=0,
            partial_count=0,
            supersedes_version_id=supersedes,
            source_candidate_id=candidate.candidate_id,
            created_at=now,
        )
        session.add(version)
        candidate.status = "accepted"
        candidate.decided_at = now
        await session.flush()
        return _version_view(experience, version)

    async def record_evaluation(
        self,
        session: AsyncSession,
        *,
        experience_version_id: str,
        trajectory_id: str,
        outcome: str,
        evaluation: dict[str, object],
        evaluator: str,
    ) -> ExperienceVersion:
        if outcome not in EVALUATION_OUTCOMES:
            raise ValueError(f"unsupported evaluation outcome: {outcome}")
        version = await session.scalar(
            select(ExperienceVersionModel)
            .where(ExperienceVersionModel.experience_version_id == experience_version_id)
            .with_for_update()
        )
        if version is None:
            raise LookupError(f"experience version not found: {experience_version_id}")
        trajectory = await session.get(InvestigationTrajectoryModel, trajectory_id)
        if trajectory is None or trajectory.status != "completed":
            raise ValueError("experience evaluation requires a completed trajectory")
        existing = await session.scalar(
            select(ExperienceSupportModel).where(
                ExperienceSupportModel.experience_version_id == experience_version_id,
                ExperienceSupportModel.trajectory_id == trajectory_id,
            )
        )
        now = self._now()
        if existing is None:
            session.add(
                ExperienceSupportModel(
                    support_id=str(uuid4()),
                    experience_version_id=experience_version_id,
                    trajectory_id=trajectory_id,
                    outcome=outcome,
                    evaluation=evaluation,
                    evaluator=evaluator,
                    created_at=now,
                )
            )
        else:
            existing.outcome = outcome
            existing.evaluation = evaluation
            existing.evaluator = evaluator
            existing.created_at = now
        await session.flush()
        await self._recompute_validation(session, version, now=now)
        experience = await session.get(ExperienceModel, version.experience_id)
        if experience is None:
            raise RuntimeError("experience version exists without experience")
        return _version_view(experience, version)

    async def mark_validated(
        self,
        session: AsyncSession,
        experience_version_id: str,
        *,
        validation_summary: dict[str, object],
    ) -> ExperienceVersion:
        version, experience = await _locked_version_and_experience(session, experience_version_id)
        if version.status not in {"candidate", "validated"}:
            raise ValueError(f"experience cannot be validated from status={version.status}")
        support_count = await session.scalar(
            select(func.count())
            .select_from(ExperienceSupportModel)
            .where(ExperienceSupportModel.experience_version_id == experience_version_id)
        )
        if int(support_count or 0) == 0:
            raise ValueError("validation requires replay or online evaluation evidence")
        version.status = "validated"
        version.validation_summary = validation_summary
        version.last_validated_at = self._now()
        experience.updated_at = self._now()
        await session.flush()
        return _version_view(experience, version)

    async def activate(
        self,
        session: AsyncSession,
        experience_version_id: str,
    ) -> ExperienceVersion:
        version, experience = await _locked_version_and_experience(session, experience_version_id)
        if version.status != "validated":
            raise ValueError("only validated experience versions can become active")
        now = self._now()
        active_siblings = list(
            await session.scalars(
                select(ExperienceVersionModel).where(
                    ExperienceVersionModel.experience_id == experience.experience_id,
                    ExperienceVersionModel.status == "active",
                    ExperienceVersionModel.experience_version_id != experience_version_id,
                )
            )
        )
        for sibling in active_siblings:
            sibling.status = "deprecated"
            sibling.deprecated_at = now
        version.status = "active"
        version.activated_at = now
        version.deprecated_at = None
        experience.current_version_id = experience_version_id
        experience.updated_at = now
        await session.flush()
        return _version_view(experience, version)

    async def deprecate(
        self,
        session: AsyncSession,
        experience_version_id: str,
    ) -> ExperienceVersion:
        version, experience = await _locked_version_and_experience(session, experience_version_id)
        if version.status == "deprecated":
            return _version_view(experience, version)
        version.status = "deprecated"
        version.deprecated_at = self._now()
        if experience.current_version_id == experience_version_id:
            experience.current_version_id = None
        experience.updated_at = self._now()
        await session.flush()
        return _version_view(experience, version)

    async def retrieve(
        self,
        session: AsyncSession,
        *,
        task_signature: str,
        scope_filter: dict[str, object] | None = None,
        limit: int = 10,
    ) -> list[ExperienceVersion]:
        rows = list(
            await session.execute(
                select(ExperienceModel, ExperienceVersionModel)
                .join(
                    ExperienceVersionModel,
                    ExperienceVersionModel.experience_id == ExperienceModel.experience_id,
                )
                .where(
                    ExperienceModel.task_signature == task_signature,
                    ExperienceVersionModel.status == "active",
                )
                .order_by(
                    ExperienceVersionModel.success_count.desc(),
                    ExperienceVersionModel.failure_count.asc(),
                    ExperienceVersionModel.version.desc(),
                )
            )
        )
        result: list[ExperienceVersion] = []
        for experience, version in rows:
            if scope_filter and not _scope_matches(version.scope, scope_filter):
                continue
            result.append(_version_view(experience, version))
            if len(result) >= limit:
                break
        return result

    async def _recompute_validation(
        self,
        session: AsyncSession,
        version: ExperienceVersionModel,
        *,
        now: datetime,
    ) -> None:
        supports = list(
            await session.scalars(
                select(ExperienceSupportModel).where(
                    ExperienceSupportModel.experience_version_id == version.experience_version_id
                )
            )
        )
        version.success_count = sum(item.outcome == "success" for item in supports)
        version.failure_count = sum(item.outcome == "failure" for item in supports)
        version.partial_count = sum(item.outcome == "partial" for item in supports)
        version.last_validated_at = now
        version.validation_summary = {
            **version.validation_summary,
            "evaluation_count": len(supports),
            "evaluators": sorted({item.evaluator for item in supports}),
        }


async def _locked_version_and_experience(
    session: AsyncSession,
    experience_version_id: str,
) -> tuple[ExperienceVersionModel, ExperienceModel]:
    version = await session.scalar(
        select(ExperienceVersionModel)
        .where(ExperienceVersionModel.experience_version_id == experience_version_id)
        .with_for_update()
    )
    if version is None:
        raise LookupError(f"experience version not found: {experience_version_id}")
    experience = await session.scalar(
        select(ExperienceModel)
        .where(ExperienceModel.experience_id == version.experience_id)
        .with_for_update()
    )
    if experience is None:
        raise RuntimeError("experience version exists without experience")
    return version, experience


def _candidate_view(model: ExperienceCandidateModel) -> ExperienceCandidate:
    return ExperienceCandidate(
        candidate_id=model.candidate_id,
        source_trajectory_id=model.source_trajectory_id,
        extraction_kind=model.extraction_kind,
        draft=ExperienceDraft.model_validate(model.draft),
        rationale=model.rationale,
        status=model.status,
        created_at=model.created_at,
    )


def _version_view(
    experience: ExperienceModel,
    version: ExperienceVersionModel,
) -> ExperienceVersion:
    return ExperienceVersion(
        experience_id=experience.experience_id,
        experience_version_id=version.experience_version_id,
        version=version.version,
        name=experience.name,
        task_signature=experience.task_signature,
        status=version.status,
        scope=dict(version.scope),
        trigger_signals=list(version.trigger_signals),
        applicable_conditions=list(version.applicable_conditions),
        recommended_actions=list(version.recommended_actions),
        evidence_expectation=list(version.evidence_expectation),
        failure_modes=list(version.failure_modes),
        stop_conditions=list(version.stop_conditions),
        fallback_actions=list(version.fallback_actions),
        validation_summary=dict(version.validation_summary),
        success_count=version.success_count,
        failure_count=version.failure_count,
        partial_count=version.partial_count,
        last_validated_at=version.last_validated_at,
        supersedes_version_id=version.supersedes_version_id,
    )


def _scope_matches(scope: dict[str, object], requested: dict[str, object]) -> bool:
    for key, requested_value in requested.items():
        actual = scope.get(key)
        if isinstance(requested_value, list):
            if not isinstance(actual, list):
                return False
            if not set(requested_value).issubset(set(actual)):
                return False
        elif actual != requested_value:
            return False
    return True
