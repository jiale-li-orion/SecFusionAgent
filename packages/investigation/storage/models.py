from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base


class InvestigationCaseModel(Base):
    __tablename__ = "investigation_cases"

    case_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_signature: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    target_object_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    initial_knowledge_revision: Mapped[int | None] = mapped_column(Integer)
    constraints: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    rubric: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InvestigationTrajectoryModel(Base):
    __tablename__ = "investigation_trajectories"

    trajectory_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("investigation_cases.case_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    outcome: Mapped[str | None] = mapped_column(String(32), index=True)
    retrieved_experience_versions: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    used_experience_versions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost: Mapped[float | None] = mapped_column(Float)
    outcome_summary: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class TrajectoryEventModel(Base):
    __tablename__ = "trajectory_events"
    __table_args__ = (
        UniqueConstraint(
            "trajectory_id",
            "ordinal",
            name="uq_trajectory_event_ordinal",
        ),
    )

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    trajectory_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("investigation_trajectories.trajectory_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    experience_version_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    artifact_uri: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class ExperienceCandidateModel(Base):
    __tablename__ = "experience_candidates"

    candidate_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_trajectory_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("investigation_trajectories.trajectory_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    extraction_kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    draft: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExperienceModel(Base):
    __tablename__ = "experiences"

    experience_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    task_signature: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    current_version_id: Mapped[str | None] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ExperienceVersionModel(Base):
    __tablename__ = "experience_versions"
    __table_args__ = (
        UniqueConstraint(
            "experience_id",
            "version",
            name="uq_experience_version_number",
        ),
    )

    experience_version_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    experience_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("experiences.experience_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scope: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    trigger_signals: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    applicable_conditions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    recommended_actions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    evidence_expectation: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    failure_modes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    stop_conditions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    fallback_actions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    validation_summary: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    partial_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supersedes_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("experience_versions.experience_version_id", ondelete="SET NULL"),
        index=True,
    )
    source_candidate_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("experience_candidates.candidate_id", ondelete="SET NULL"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExperienceSupportModel(Base):
    __tablename__ = "experience_support"
    __table_args__ = (
        UniqueConstraint(
            "experience_version_id",
            "trajectory_id",
            name="uq_experience_support_trajectory",
        ),
    )

    support_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    experience_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("experience_versions.experience_version_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trajectory_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("investigation_trajectories.trajectory_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    outcome: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    evaluation: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    evaluator: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
