from __future__ import annotations

from fastapi import APIRouter

from apps.api.dependencies import RequestContextDep, SessionDep
from apps.api.errors import ProblemDetail
from apps.application.queries.decisions import DecisionQueries
from apps.application.views.investigations import DecisionView

router = APIRouter(prefix="/api/v1/decisions", tags=["questions"])


@router.get(
    "/{decision_id}",
    response_model=DecisionView,
    responses={404: {"model": ProblemDetail}},
)
async def get_decision(
    decision_id: str, session: SessionDep, context: RequestContextDep
) -> DecisionView:
    return await DecisionQueries().get(session, decision_id, principal=context.principal)
