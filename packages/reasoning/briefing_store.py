"""Publication records reference immutable M6 reports and pinned material versions."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base


class IntelligenceBriefModel(Base):
    __tablename__ = "intelligence_briefs"

    brief_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    input_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    topic: Mapped[str] = mapped_column(String(180), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    decision_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("decision_results.decision_id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    material_manifest: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    review_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    policy_revision: Mapped[str] = mapped_column(Text, nullable=False)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
