from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base


class SourceStateModel(Base):
    __tablename__ = "source_state"

    source_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("sources.source_id", ondelete="CASCADE"), primary_key=True
    )
    cursor: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_change_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    backoff_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    rate_limit_state: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class AcquisitionRunModel(Base):
    __tablename__ = "acquisition_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("sources.source_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    parent_run_id: Mapped[str | None] = mapped_column(String(36), index=True)
    query_spec: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    cursor_in: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    cursor_out: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(128))
    error_detail: Mapped[str | None] = mapped_column(Text)


class HotAdmissionReceiptModel(Base):
    """First recorded cache admission of a source object version, not Evidence."""

    __tablename__ = "hot_admission_receipts"
    __table_args__ = (
        Index("ix_hot_admission_source_publication", "source_id", "published_at", "available_at"),
        Index("ix_hot_admission_source_update", "source_id", "updated_at", "available_at"),
    )

    receipt_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("sources.source_id", ondelete="RESTRICT"), nullable=False
    )
    external_object_id: Mapped[str] = mapped_column(Text, nullable=False)
    external_revision: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acquisition_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("acquisition_runs.run_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    source_definition_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_backfill_pending: Mapped[bool] = mapped_column(Boolean, nullable=False)
    output_backfill_pending: Mapped[bool] = mapped_column(Boolean, nullable=False)
