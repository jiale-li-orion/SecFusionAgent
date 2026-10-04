from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from apps.api.dependencies import SessionDep
from apps.application.queries.evidence import get_evidence_by_ref
from apps.application.views.evidence import EvidenceView

router = APIRouter(prefix="/api/v1/evidence", tags=["evidence"])


@router.get("/{evidence_ref}", response_model=EvidenceView)
async def evidence_by_ref(evidence_ref: str, session: SessionDep) -> EvidenceView:
    result = await get_evidence_by_ref(session, evidence_ref)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evidence not found")
    return result
