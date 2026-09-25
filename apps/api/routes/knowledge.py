from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.knowledge.read import KnowledgeObjectView, get_vulnerability_by_cve

router = APIRouter(prefix="/api/v1", tags=["knowledge"])


async def database_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = request.app.state.session_factory
    async with factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(database_session)]


@router.get("/vulnerabilities/{cve_id}", response_model=KnowledgeObjectView)
async def vulnerability_by_cve(
    cve_id: str,
    session: SessionDep,
) -> KnowledgeObjectView:
    result = await get_vulnerability_by_cve(session, cve_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="vulnerability not found")
    return result
