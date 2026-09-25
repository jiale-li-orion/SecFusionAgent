from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base


class CurrentProjectionModel(Base):
    __tablename__ = "current_projections"
    __table_args__ = (
        UniqueConstraint(
            "projection_type",
            "subject_id",
            name="uq_current_projection_type_subject",
        ),
    )

    projection_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    projection_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    projection_key: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    data: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    upstream_revision: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
