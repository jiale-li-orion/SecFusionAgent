from fastapi import APIRouter, HTTPException, status

from apps.api.dependencies import SessionDep
from packages.intelligence.knowledge.read import KnowledgeObjectView, get_vulnerability_by_cve

router = APIRouter(prefix="/api/v1", tags=["knowledge"])


@router.get("/vulnerabilities/{cve_id}", response_model=KnowledgeObjectView)
async def vulnerability_by_cve(
    cve_id: str,
    session: SessionDep,
) -> KnowledgeObjectView:
    result = await get_vulnerability_by_cve(session, cve_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="vulnerability not found")
    return result
