from fastapi import APIRouter, HTTPException, Query, status

from apps.api.dependencies import SessionDep
from apps.application.queries.incidents import (
    get_product_incident,
    list_product_incidents,
)
from apps.application.views.incidents import IncidentDetailView, IncidentListView

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])


@router.get("", response_model=IncidentListView)
async def incidents(
    session: SessionDep,
    limit: int = Query(default=40, ge=1, le=100),
) -> IncidentListView:
    return await list_product_incidents(session, limit=limit)


@router.get("/{incident_id}", response_model=IncidentDetailView)
async def incident_detail(
    incident_id: str,
    session: SessionDep,
) -> IncidentDetailView:
    result = await get_product_incident(session, incident_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="incident not found",
        )
    return result
