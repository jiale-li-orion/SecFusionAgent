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
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
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


class PerceptionEventModel(Base):
    __tablename__ = "perception_events"
    __table_args__ = (
        UniqueConstraint(
            "task_run_id",
            "request_id",
            name="uq_perception_event_task_request",
        ),
    )

    perception_event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("investigation_cases.case_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("task_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    need_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("evidence_needs.need_id", ondelete="SET NULL"),
        index=True,
    )
    request_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    plan_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    percept_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    observation_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    cost: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    world_revision: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    failure_class: Mapped[str | None] = mapped_column(String(128), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class InvestigationSnapshotModel(Base):
    __tablename__ = "investigation_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("investigation_cases.case_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_revision: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    knowledge_revision: Mapped[int | None] = mapped_column(Integer, index=True)
    incident_revision: Mapped[str | None] = mapped_column(String(128))
    document_index_revision: Mapped[str | None] = mapped_column(String(128))
    experience_revision: Mapped[str | None] = mapped_column(String(128))
    policy_revision: Mapped[str] = mapped_column(String(128), nullable=False)
    capability_registry_revision: Mapped[str | None] = mapped_column(String(128))
    routing_query_planner_revision: Mapped[str | None] = mapped_column(String(128))
    model_revision: Mapped[str | None] = mapped_column(String(128))
    prompt_assembly_revision: Mapped[str | None] = mapped_column(String(128))
    source_availability_snapshot: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


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


class CaseStateEventModel(Base):
    __tablename__ = "case_state_events"
    __table_args__ = (
        UniqueConstraint("case_id", "case_revision", name="uq_case_state_revision"),
        UniqueConstraint(
            "case_id",
            "patch_id",
            "operation_index",
            name="uq_case_state_patch_operation",
        ),
    )

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("investigation_cases.case_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    base_case_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    patch_id: Mapped[str | None] = mapped_column(String(128), index=True)
    operation_index: Mapped[int | None] = mapped_column(Integer)
    proposition: Mapped[str | None] = mapped_column(Text)
    target_ref: Mapped[str | None] = mapped_column(String(512), index=True)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    writer: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    reason_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class EvidenceNeedModel(Base):
    __tablename__ = "evidence_needs"

    need_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("investigation_cases.case_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    derived_from_enrichment_requirement: Mapped[str | None] = mapped_column(String(256), index=True)
    proposition_or_question: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[str] = mapped_column(String(256), nullable=False)
    target_objects: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    evidence_contract: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    preferred_source_roles: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    rejected_evidence_patterns: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    freshness_requirement: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    completion_predicate: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    resolution_evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    opened_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class InvestigationStateCurrentModel(Base):
    __tablename__ = "investigation_state_current"

    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("investigation_cases.case_id", ondelete="CASCADE"),
        primary_key=True,
    )
    case_revision: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    targets: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    confirmed: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    tentative: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    conflicts: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    unknowns: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    hypotheses: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    open_questions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    decision_variables: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    evidence_need_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    active_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    normative_context_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    unresolved_applicability: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    current_decision: Mapped[dict[str, object] | None] = mapped_column(JSON)
    last_world_revision: Mapped[int | None] = mapped_column(Integer, index=True)
    last_perception_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
