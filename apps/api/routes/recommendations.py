from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from apps.api.dependencies import RequestContextDep, SessionDep
from apps.application.intelligence_preferences import (
    put_intelligence_preferences,
    put_recommendation_feedback,
    read_intelligence_preferences,
)
from apps.application.queries.recommendations import read_intelligence_recommendations
from apps.application.views.recommendations import (
    IntelligencePreferencesInput,
    IntelligencePreferencesView,
    IntelligenceRecommendationsView,
    RecommendationFeedbackInput,
    RecommendationFeedbackView,
)

router = APIRouter(prefix="/api/v1/intelligence", tags=["knowledge"])


def _principal(context: RequestContextDep) -> str:
    if not context.principal.strip() or len(context.principal) > 256:
        raise HTTPException(status_code=422, detail="principal must contain 1-256 characters")
    return context.principal


@router.get("/preferences", response_model=IntelligencePreferencesView)
async def intelligence_preferences(
    session: SessionDep,
    context: RequestContextDep,
) -> IntelligencePreferencesView:
    return await read_intelligence_preferences(session, _principal(context))


@router.put("/preferences", response_model=IntelligencePreferencesView)
async def replace_intelligence_preferences(
    body: IntelligencePreferencesInput,
    session: SessionDep,
    context: RequestContextDep,
) -> IntelligencePreferencesView:
    return await put_intelligence_preferences(session, _principal(context), body)


@router.get("/recommendations", response_model=IntelligenceRecommendationsView)
async def intelligence_recommendations(
    session: SessionDep,
    context: RequestContextDep,
    limit: int = Query(default=6, ge=1, le=24),
) -> IntelligenceRecommendationsView:
    return await read_intelligence_recommendations(session, _principal(context), limit=limit)


@router.put("/recommendations/{object_id}/feedback", response_model=RecommendationFeedbackView)
async def intelligence_recommendation_feedback(
    object_id: str,
    body: RecommendationFeedbackInput,
    session: SessionDep,
    context: RequestContextDep,
) -> RecommendationFeedbackView:
    return await put_recommendation_feedback(session, _principal(context), object_id, body)
