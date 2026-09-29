from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import JSON, DateTime, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from packages.reasoning.decision import DecisionResult
from packages.shared.db import Base


class DecisionResultModel(Base):
    __tablename__ = "decision_results"

    decision_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    case_revision: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    decision_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class StoredDecisionResult(DecisionResult):
    created_at: datetime


class DecisionResultStore:
    """Immutable M6 result store keyed by the DecisionResult identity.

    M4 remains the owner of which decision is current for a durable Case. This
    store only gives validated DecisionResult values a stable read identity,
    including synchronous DIRECT/RETRIEVE decisions that intentionally have no
    durable Investigation Case.
    """

    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(UTC))

    async def persist(
        self,
        session: AsyncSession,
        decision: DecisionResult,
    ) -> StoredDecisionResult:
        payload = decision.model_dump(mode="json")
        digest = _digest(payload)
        existing = await session.get(DecisionResultModel, decision.decision_id)
        if existing is not None:
            if existing.content_hash != digest or existing.decision_json != payload:
                raise ValueError("DecisionResult identity is immutable")
            return _view(existing)
        model = DecisionResultModel(
            decision_id=decision.decision_id,
            case_id=decision.case_id,
            case_revision=decision.case_revision,
            decision_json=payload,
            content_hash=digest,
            created_at=self._now(),
        )
        session.add(model)
        await session.flush()
        return _view(model)

    async def get(self, session: AsyncSession, decision_id: str) -> StoredDecisionResult:
        model = await session.get(DecisionResultModel, decision_id)
        if model is None:
            raise LookupError(f"decision result not found: {decision_id}")
        return _view(model)

    async def get_optional(
        self,
        session: AsyncSession,
        decision_id: str,
    ) -> StoredDecisionResult | None:
        model = await session.scalar(
            select(DecisionResultModel).where(DecisionResultModel.decision_id == decision_id)
        )
        return _view(model) if model is not None else None


def _digest(payload: dict[str, object]) -> str:
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _view(model: DecisionResultModel) -> StoredDecisionResult:
    created_at = model.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    else:
        created_at = created_at.astimezone(UTC)
    return StoredDecisionResult(
        **DecisionResult.model_validate(model.decision_json).model_dump(),
        created_at=created_at,
    )
