from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base


class ProcessingRunModel(Base):
    __tablename__ = "processing_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    processor_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    processor_name: Mapped[str] = mapped_column(String(128), nullable=False)
    processor_version: Mapped[str] = mapped_column(String(64), nullable=False)
    input_revision_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    model: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[str | None] = mapped_column(String(128))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(128))
