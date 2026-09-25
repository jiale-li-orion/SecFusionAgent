from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
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
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    cursor_in: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    cursor_out: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(128))
    error_detail: Mapped[str | None] = mapped_column(Text)
