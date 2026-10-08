from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    and_,
    func,
    or_,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from apps.application.errors import PermissionDeniedError, ResourceNotFoundError
from packages.shared.db import Base


class QuestionSessionModel(Base):
    __tablename__ = "question_sessions"

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    principal: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    state_carry_policy: Mapped[str] = mapped_column(
        String(64), nullable=False, default="targets_and_outcomes_v1"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class QuestionSessionTurnModel(Base):
    __tablename__ = "question_session_turns"
    __table_args__ = (
        UniqueConstraint("session_id", "turn_index", name="uq_question_session_turn_index"),
        UniqueConstraint("session_id", "request_id", name="uq_question_session_request"),
    )

    turn_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("question_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    task_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    target_object_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    knowledge_revision: Mapped[int | None] = mapped_column(Integer, index=True)
    context_id: Mapped[str | None] = mapped_column(String(128), index=True)
    decision_ref: Mapped[str | None] = mapped_column(String(128), index=True)
    investigation_ref: Mapped[str | None] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QuestionSessionTurn(BaseModel):
    turn_index: int = Field(ge=1)
    request_id: str
    question: str
    task_kind: str
    target_object_ids: list[str] = Field(default_factory=list)
    knowledge_revision: int | None = None
    context_id: str | None = None
    decision_ref: str | None = None
    investigation_ref: str | None = None
    created_at: datetime


class QuestionSessionContext(BaseModel):
    session_id: str
    principal: str
    state_carry_policy: str = "targets_and_outcomes_v1"
    turns: list[QuestionSessionTurn] = Field(default_factory=list)

    @property
    def latest_turn(self) -> QuestionSessionTurn | None:
        return self.turns[-1] if self.turns else None


class AccountConversationView(BaseModel):
    session_id: str
    updated_at: datetime
    latest_turn: QuestionSessionTurn


class AccountConversationPage(BaseModel):
    items: list[AccountConversationView]
    has_more: bool
    next_cursor: str | None = None


class QuestionSessionHistoryPage(BaseModel):
    session_id: str
    turns: list[QuestionSessionTurn]
    has_more: bool
    next_before_turn: int | None = None


class QuestionSessionStore:
    def __init__(
        self,
        *,
        now: Callable[[], datetime] | None = None,
        history_limit: int = 4,
    ) -> None:
        self._now = now or (lambda: datetime.now(UTC))
        self._history_limit = history_limit

    async def list_owned(
        self, session: AsyncSession, *, principal: str, limit: int = 20,
        cursor: str | None = None,
    ) -> AccountConversationPage:
        bounded_limit = min(max(limit, 1), 50)
        cursor_model = await session.get(QuestionSessionModel, cursor) if cursor else None
        if cursor and cursor_model is None:
            raise ResourceNotFoundError("question session cursor not found")
        if cursor_model is not None:
            _require_principal(cursor_model, principal)
        latest = (
            select(
                QuestionSessionTurnModel.session_id,
                func.max(QuestionSessionTurnModel.turn_index).label("turn_index"),
            )
            .join(QuestionSessionModel)
            .where(QuestionSessionModel.principal == principal)
            .group_by(QuestionSessionTurnModel.session_id)
            .subquery()
        )
        statement = (
            select(QuestionSessionModel, QuestionSessionTurnModel)
            .join(latest, latest.c.session_id == QuestionSessionModel.session_id)
            .join(QuestionSessionTurnModel, (
                (QuestionSessionTurnModel.session_id == latest.c.session_id)
                & (QuestionSessionTurnModel.turn_index == latest.c.turn_index)
            ))
            .where(QuestionSessionModel.principal == principal)
            .order_by(QuestionSessionModel.updated_at.desc(), QuestionSessionModel.session_id)
            .limit(bounded_limit + 1)
        )
        if cursor_model is not None:
            statement = statement.where(or_(
                QuestionSessionModel.updated_at < cursor_model.updated_at,
                and_(
                    QuestionSessionModel.updated_at == cursor_model.updated_at,
                    QuestionSessionModel.session_id > cursor_model.session_id,
                ),
            ))
        rows = list(await session.execute(statement))
        page_rows = rows[:bounded_limit]
        return AccountConversationPage(
            items=[AccountConversationView(
                session_id=conversation.session_id,
                updated_at=conversation.updated_at,
                latest_turn=_turn_view(turn),
            ) for conversation, turn in page_rows],
            has_more=len(rows) > bounded_limit,
            next_cursor=page_rows[-1][0].session_id if len(rows) > bounded_limit else None,
        )

    async def read_history_page(
        self, session: AsyncSession, *, session_id: str, principal: str,
        limit: int = 50, before_turn: int | None = None,
    ) -> QuestionSessionHistoryPage:
        model = await session.get(QuestionSessionModel, session_id)
        if model is None:
            raise ResourceNotFoundError(
                "question session not found", context={"session_id": session_id}
            )
        _require_principal(model, principal)
        bounded_limit = min(max(limit, 1), 50)
        statement = select(QuestionSessionTurnModel).where(
            QuestionSessionTurnModel.session_id == session_id
        )
        if before_turn is not None:
            statement = statement.where(QuestionSessionTurnModel.turn_index < before_turn)
        rows = list(await session.scalars(
            statement.order_by(QuestionSessionTurnModel.turn_index.desc())
            .limit(bounded_limit + 1)
        ))
        page = [_turn_view(item) for item in reversed(rows[:bounded_limit])]
        has_more = len(rows) > bounded_limit
        return QuestionSessionHistoryPage(
            session_id=session_id,
            turns=page,
            has_more=has_more,
            next_before_turn=page[0].turn_index if has_more else None,
        )

    async def resolve(
        self,
        session: AsyncSession,
        *,
        session_id: str | None,
        principal: str,
    ) -> QuestionSessionContext:
        if session_id is None:
            return QuestionSessionContext(session_id=str(uuid4()), principal=principal)
        model = await session.get(QuestionSessionModel, session_id)
        if model is None:
            raise ResourceNotFoundError(
                "question session not found",
                context={"session_id": session_id},
            )
        _require_principal(model, principal)
        rows = list(
            await session.scalars(
                select(QuestionSessionTurnModel)
                .where(QuestionSessionTurnModel.session_id == session_id)
                .order_by(QuestionSessionTurnModel.turn_index.desc())
                .limit(self._history_limit)
            )
        )
        rows.reverse()
        return QuestionSessionContext(
            session_id=model.session_id,
            principal=model.principal,
            state_carry_policy=model.state_carry_policy,
            turns=[_turn_view(item) for item in rows],
        )

    async def append_turn(
        self,
        session: AsyncSession,
        *,
        session_id: str,
        principal: str,
        request_id: str,
        question: str,
        task_kind: str,
        target_object_ids: list[str],
        knowledge_revision: int | None,
        context_id: str | None,
        decision_ref: str | None,
        investigation_ref: str | None,
    ) -> QuestionSessionTurn:
        if (decision_ref is None) == (investigation_ref is None):
            raise ValueError("question session turn requires exactly one outcome ref")
        now = self._now()
        model = await session.get(QuestionSessionModel, session_id, with_for_update=True)
        if model is None:
            model = QuestionSessionModel(
                session_id=session_id,
                principal=principal,
                state_carry_policy="targets_and_outcomes_v1",
                created_at=now,
                updated_at=now,
            )
            session.add(model)
            await session.flush()
        else:
            _require_principal(model, principal)

        existing = await session.scalar(
            select(QuestionSessionTurnModel).where(
                QuestionSessionTurnModel.session_id == session_id,
                QuestionSessionTurnModel.request_id == request_id,
            )
        )
        if existing is not None:
            return _turn_view(existing)

        latest = int(
            await session.scalar(
                select(func.max(QuestionSessionTurnModel.turn_index)).where(
                    QuestionSessionTurnModel.session_id == session_id
                )
            )
            or 0
        )
        turn = QuestionSessionTurnModel(
            turn_id=str(uuid4()),
            session_id=session_id,
            turn_index=latest + 1,
            request_id=request_id,
            question=question,
            task_kind=task_kind,
            target_object_ids=list(dict.fromkeys(target_object_ids)),
            knowledge_revision=knowledge_revision,
            context_id=context_id,
            decision_ref=decision_ref,
            investigation_ref=investigation_ref,
            created_at=now,
        )
        session.add(turn)
        model.updated_at = now
        await session.flush()
        return _turn_view(turn)

    async def latest_investigation_turn(
        self,
        session: AsyncSession,
        *,
        session_id: str | None,
        principal: str,
    ) -> QuestionSessionTurn | None:
        if session_id is None:
            return None
        model = await session.get(QuestionSessionModel, session_id)
        if model is None:
            raise ResourceNotFoundError(
                "question session not found",
                context={"session_id": session_id},
            )
        _require_principal(model, principal)
        row = await session.scalar(
            select(QuestionSessionTurnModel)
            .where(
                QuestionSessionTurnModel.session_id == session_id,
                QuestionSessionTurnModel.investigation_ref.is_not(None),
            )
            .order_by(QuestionSessionTurnModel.turn_index.desc())
            .limit(1)
        )
        return _turn_view(row) if row is not None else None

    async def latest_session_id_for_investigation(
        self,
        session: AsyncSession,
        *,
        investigation_ref: str,
        principal: str,
    ) -> str | None:
        return await session.scalar(
            select(QuestionSessionTurnModel.session_id)
            .join(
                QuestionSessionModel,
                QuestionSessionModel.session_id == QuestionSessionTurnModel.session_id,
            )
            .where(
                QuestionSessionTurnModel.investigation_ref == investigation_ref,
                QuestionSessionModel.principal == principal,
            )
            .order_by(
                QuestionSessionTurnModel.created_at.desc(),
                QuestionSessionTurnModel.turn_index.desc(),
            )
            .limit(1)
        )


def _require_principal(model: QuestionSessionModel, principal: str) -> None:
    if model.principal != principal:
        raise PermissionDeniedError(
            "question session belongs to another principal",
            context={"session_id": model.session_id},
        )


def _turn_view(model: QuestionSessionTurnModel) -> QuestionSessionTurn:
    created_at = model.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    else:
        created_at = created_at.astimezone(UTC)
    return QuestionSessionTurn(
        turn_index=model.turn_index,
        request_id=model.request_id,
        question=model.question,
        task_kind=model.task_kind,
        target_object_ids=list(model.target_object_ids),
        knowledge_revision=model.knowledge_revision,
        context_id=model.context_id,
        decision_ref=model.decision_ref,
        investigation_ref=model.investigation_ref,
        created_at=created_at,
    )
