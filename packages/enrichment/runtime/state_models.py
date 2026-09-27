from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base
from packages.task_runtime.storage.models import TaskRunModel  # noqa: F401


class EnrichmentDimensionStateModel(Base):
    __tablename__ = "enrichment_dimension_states"
    __table_args__ = (
        UniqueConstraint(
            "target_object_id",
            "vocabulary_revision",
            "dimension",
            name="uq_enrichment_dimension_state",
        ),
    )

    state_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    target_object_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("objects.object_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vocabulary_revision: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    requirement_id: Mapped[str] = mapped_column(String(256), nullable=False)
    dimension: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    accepted_fact_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    conflict_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_prerequisites: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    attempted_operator_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    blocked_attempt_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    world_revision: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EnrichmentAttemptModel(Base):
    __tablename__ = "enrichment_attempts"

    attempt_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    target_object_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("objects.object_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requirement_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    dimension: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    operator_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    task_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("task_runs.run_id", ondelete="SET NULL"),
        index=True,
    )
    execution_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    semantic_outcome: Mapped[str | None] = mapped_column(String(32), index=True)
    blocked_reason: Mapped[str | None] = mapped_column(String(128), index=True)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    output_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    world_revision_before: Mapped[int] = mapped_column(Integer, nullable=False)
    world_revision_after: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
