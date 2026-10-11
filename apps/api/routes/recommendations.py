from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from apps.api.dependencies import RequestContextDep, SessionDep
from apps.application.intelligence_preferences import (
    put_intelligence_preferences,
    put_recommendation_feedback,
    read_intelligence_preferences,
)
from apps.application.queries.intelligence_feed import read_intelligence_feed, resolve_follow
from apps.application.queries.recommendations import read_intelligence_recommendations
from apps.application.views.recommendations import (
    FollowResolutionView,
    IntelligenceFeedView,
    IntelligencePreferencesInput,
    IntelligencePreferencesView,
    IntelligenceRecommendationsView,
    RecommendationFeedbackInput,
    RecommendationFeedbackView,
)
from packages.intelligence.feed import put_activity_feedback

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


@router.get("/follow-resolution", response_model=FollowResolutionView)
async def follow_resolution(
    session: SessionDep, context: RequestContextDep, q: str = Query(min_length=1, max_length=128)
) -> FollowResolutionView:
    _principal(context)
    if not q.strip():
        raise HTTPException(status_code=422, detail="query must not be blank")
    return await resolve_follow(session, q)


@router.get("/feed", response_model=IntelligenceFeedView)
async def intelligence_feed(
    session: SessionDep,
    context: RequestContextDep,
    mode: Literal["following", "recommended"] = "recommended",
    window: Literal["30d", "all"] = "30d",
    limit: int = Query(default=12, ge=1, le=50),
    cursor: str | None = Query(default=None, max_length=2048),
) -> IntelligenceFeedView:
    try:
        return await read_intelligence_feed(
            session, _principal(context), mode=mode, window=window, limit=limit, cursor=cursor
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid feed cursor") from exc


@router.put("/feed/{activity_id}/feedback")
async def activity_feedback(
    activity_id: str,
    body: RecommendationFeedbackInput,
    session: SessionDep,
    context: RequestContextDep,
) -> dict[str, object]:
    if not re.fullmatch(r"activity-[0-9a-f]{40}", activity_id):
        raise HTTPException(status_code=422, detail="invalid activity identifier")
    principal = _principal(context)
    now = await put_activity_feedback(session, principal, activity_id, body.feedback)
    return {"activity_id": activity_id, "feedback": body.feedback, "updated_at": now}
