from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from apps.api.dependencies import SessionDep
from apps.application.queries.library import list_material_library
from apps.application.queries.library_subjects import CATEGORY_LABELS, SUBJECT_BY_KEY
from apps.application.views.library import MaterialLibraryView

router = APIRouter(prefix="/api/v1/intelligence", tags=["knowledge"])


@router.get("/library", response_model=MaterialLibraryView)
async def material_library(
    session: SessionDep,
    limit: int = Query(48, ge=1, le=100),
    offset: int = Query(0, ge=0, le=1_000_000),
    as_of: datetime | None = None,
    category: str | None = None,
    source: str | None = Query(None, max_length=128),
    subject: str | None = None,
    q: str | None = Query(None, max_length=200),
) -> MaterialLibraryView:
    if category and category not in CATEGORY_LABELS:
        raise HTTPException(422, "Unknown library category")
    if subject and subject not in SUBJECT_BY_KEY and subject != "other":
        raise HTTPException(422, "Unknown library subject")
    if as_of is not None and as_of.tzinfo is None:
        raise HTTPException(422, "as_of must include a time zone")
    return await list_material_library(
        session,
        limit=limit,
        offset=offset,
        as_of=as_of,
        category=category,
        source=source,
        subject=subject,
        q=q,
    )
