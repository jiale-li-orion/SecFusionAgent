"""Item feedback is independent of followed object identities and legacy feedback."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base


class ActivityFeedbackModel(Base):
    __tablename__ = "intelligence_activity_feedback"
    __table_args__ = (
        CheckConstraint(
            "feedback IN ('interested','ignored','neutral')", name="ck_activity_feedback_value"
        ),
    )
    principal: Mapped[str] = mapped_column(String(256), primary_key=True)
    activity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    feedback: Mapped[str] = mapped_column(String(16), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
