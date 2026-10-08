"""Principal-scoped Product interests; Knowledge remains the intelligence authority."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from apps.application.errors import ResourceNotFoundError
from apps.application.views.recommendations import (
    FollowedObjectView,
    IntelligencePreferencesInput,
    IntelligencePreferencesView,
    RecommendationFeedbackInput,
    RecommendationFeedbackView,
)
from packages.intelligence.storage.knowledge_models import ObjectModel
from packages.shared.db import Base


class IntelligencePreferenceModel(Base):
    __tablename__ = "intelligence_preferences"

    principal: Mapped[str] = mapped_column(String(256), primary_key=True)
    keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    target_object_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RecommendationFeedbackModel(Base):
    __tablename__ = "intelligence_recommendation_feedback"
    __table_args__ = (
        CheckConstraint(
            "feedback IN ('interested','ignored','neutral')",
            name="ck_intelligence_recommendation_feedback_value",
        ),
    )

    principal: Mapped[str] = mapped_column(String(256), primary_key=True)
    object_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("objects.object_id", ondelete="CASCADE"), primary_key=True
    )
    feedback: Mapped[str] = mapped_column(String(16), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def object_label(obj: ObjectModel) -> str:
    for key in ("display_name", "title", "name", "summary"):
        value = obj.properties.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return obj.canonical_key


async def read_intelligence_preferences(
    session: AsyncSession,
    principal: str,
) -> IntelligencePreferencesView:
    row = await session.get(IntelligencePreferenceModel, principal)
    if row is None:
        return IntelligencePreferencesView()
    targets = (
        list(
            await session.scalars(
                select(ObjectModel).where(ObjectModel.object_id.in_(row.target_object_ids))
            )
        )
        if row.target_object_ids
        else []
    )
    by_id = {obj.object_id: obj for obj in targets}
    return IntelligencePreferencesView(
        keywords=row.keywords,
        target_object_ids=row.target_object_ids,
        updated_at=row.updated_at,
        target_objects=[
            FollowedObjectView(
                object_id=obj.object_id,
                object_type=obj.object_type,
                canonical_key=obj.canonical_key,
                label=object_label(obj),
            )
            for object_id in row.target_object_ids
            if (obj := by_id.get(object_id)) is not None
        ],
    )


async def put_intelligence_preferences(
    session: AsyncSession,
    principal: str,
    preferences: IntelligencePreferencesInput,
) -> IntelligencePreferencesView:
    if preferences.target_object_ids:
        found = set(
            await session.scalars(
                select(ObjectModel.object_id).where(
                    ObjectModel.object_id.in_(preferences.target_object_ids),
                    ObjectModel.superseded_revision.is_(None),
                )
            )
        )
        missing = set(preferences.target_object_ids) - found
        if missing:
            raise ResourceNotFoundError(
                "followed Knowledge object not found", context={"object_ids": sorted(missing)}
            )
    values = dict(
        principal=principal,
        keywords=preferences.keywords,
        target_object_ids=preferences.target_object_ids,
        updated_at=datetime.now(UTC),
    )
    insert = postgresql_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
    statement = insert(IntelligencePreferenceModel).values(**values)
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=["principal"],
            set_={key: value for key, value in values.items() if key != "principal"},
        )
    )
    await session.commit()
    session.expire_all()
    return await read_intelligence_preferences(session, principal)


async def put_recommendation_feedback(
    session: AsyncSession,
    principal: str,
    object_id: str,
    feedback: RecommendationFeedbackInput,
) -> RecommendationFeedbackView:
    obj = await session.get(ObjectModel, object_id)
    if obj is None or obj.superseded_revision is not None:
        raise ResourceNotFoundError("Knowledge object not found")
    now = datetime.now(UTC)
    values = dict(
        principal=principal, object_id=object_id, feedback=feedback.feedback, updated_at=now
    )
    insert = postgresql_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
    statement = insert(RecommendationFeedbackModel).values(**values)
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=["principal", "object_id"],
            set_={"feedback": feedback.feedback, "updated_at": now},
        )
    )
    await session.commit()
    session.expire_all()
    return RecommendationFeedbackView(
        object_id=object_id, feedback=feedback.feedback, updated_at=now
    )
