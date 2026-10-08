from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.application.errors import ResourceNotFoundError
from apps.application.queries.investigations import decision_view
from apps.application.queries.ownership import investigation_owner, public_system_case
from apps.application.question_sessions import QuestionSessionModel, QuestionSessionTurnModel
from apps.application.views.investigations import DecisionView
from packages.investigation.state.contracts import CaseStateEventType
from packages.investigation.storage.models import CaseStateEventModel
from packages.reasoning.decision import DecisionResult
from packages.reasoning.storage import DecisionResultStore


class DecisionQueries:
    def __init__(self, store: DecisionResultStore | None = None) -> None:
        self._store = store or DecisionResultStore()

    async def get(
        self, session: AsyncSession, decision_id: str, *, principal: str | None = None
    ) -> DecisionView:
        stored = await self._store.get_optional(session, decision_id)
        if stored is not None:
            await self._require_access(session, decision_id, stored.case_id, principal)
            view = decision_view(
                stored.model_dump(mode="json", exclude={"created_at"}),
                stored.created_at,
            )
            assert view is not None
            return view

        # Compatibility read for M4 decisions committed before the immutable M6
        # result store existed. DecisionCommit already uses decision_id as patch_id.
        event = await session.scalar(
            select(CaseStateEventModel).where(
                CaseStateEventModel.patch_id == decision_id,
                CaseStateEventModel.event_type == CaseStateEventType.DECISION_CHANGED.value,
                CaseStateEventModel.operation_index == 0,
            )
        )
        if event is not None:
            await self._require_access(session, decision_id, event.case_id, principal)
            payload = event.payload.get("decision")
            if isinstance(payload, dict):
                decision = DecisionResult.model_validate(payload)
                view = decision_view(decision.model_dump(mode="json"), event.created_at)
                if view is not None:
                    return view
        raise ResourceNotFoundError(
            "decision not found",
            context={"decision_id": decision_id},
        )

    async def _require_access(
        self, session: AsyncSession, decision_id: str, case_id: str, principal: str | None
    ) -> None:
        if principal is None:
            return
        session_owned = await session.scalar(
            select(QuestionSessionTurnModel.turn_id)
            .join(
                QuestionSessionModel,
                QuestionSessionModel.session_id == QuestionSessionTurnModel.session_id,
            )
            .where(
                QuestionSessionTurnModel.decision_ref == decision_id,
                QuestionSessionModel.principal == principal,
            )
            .limit(1)
        )
        if (
            session_owned is not None
            or await session.scalar(select(investigation_owner(case_id))) == principal
            or await session.scalar(select(public_system_case(case_id))) is True
        ):
            return
        raise ResourceNotFoundError("decision not found", context={"decision_id": decision_id})
