from fastapi import APIRouter, HTTPException, Query, status

from apps.api.dependencies import SessionDep
from apps.application.queries.intelligence import (
    get_product_document,
    get_product_enrichment_state,
    get_product_intelligence_graph,
    search_product_intelligence,
)
from apps.application.views.intelligence import (
    IntelligenceGraphView,
    IntelligenceSearchView,
    ProductDocumentView,
    ProductEnrichmentStateView,
)
from packages.intelligence.knowledge.read import (
    KnowledgeObjectView,
    get_object_by_id,
    get_vulnerability_by_cve,
)

router = APIRouter(prefix="/api/v1", tags=["knowledge"])


@router.get("/intelligence/search", response_model=IntelligenceSearchView)
async def intelligence_search(
    session: SessionDep,
    q: str = Query(min_length=2, max_length=256),
    limit: int = Query(default=12, ge=1, le=40),
) -> IntelligenceSearchView:
    return await search_product_intelligence(session, q, limit=limit)


@router.get("/documents/by-object/{object_id}", response_model=ProductDocumentView)
async def document_by_object(
    object_id: str,
    session: SessionDep,
) -> ProductDocumentView:
    result = await get_product_document(session, object_id=object_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )
    return result


@router.get(
    "/intelligence/objects/{object_id}/enrichment",
    response_model=ProductEnrichmentStateView,
)
async def intelligence_object_enrichment(
    object_id: str,
    session: SessionDep,
) -> ProductEnrichmentStateView:
    try:
        result = await get_product_enrichment_state(session, object_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="knowledge object not found",
        )
    return result


@router.get("/intelligence/objects/{object_id}", response_model=KnowledgeObjectView)
async def intelligence_object_by_id(
    object_id: str,
    session: SessionDep,
) -> KnowledgeObjectView:
    result = await get_object_by_id(session, object_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="knowledge object not found",
        )
    return result


@router.get(
    "/intelligence/objects/{object_id}/graph",
    response_model=IntelligenceGraphView,
)
async def intelligence_object_graph(
    object_id: str,
    session: SessionDep,
    limit: int = Query(default=24, ge=1, le=64),
) -> IntelligenceGraphView:
    result = await get_product_intelligence_graph(
        session,
        object_id,
        limit=limit,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="knowledge object not found",
        )
    return result


@router.get("/documents/{document_id}", response_model=ProductDocumentView)
async def document_by_id(
    document_id: str,
    session: SessionDep,
) -> ProductDocumentView:
    result = await get_product_document(session, document_id=document_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )
    return result


@router.get("/vulnerabilities/{cve_id}", response_model=KnowledgeObjectView)
async def vulnerability_by_cve(
    cve_id: str,
    session: SessionDep,
) -> KnowledgeObjectView:
    result = await get_vulnerability_by_cve(session, cve_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="vulnerability not found")
    return result


@router.get("/objects/{object_id}", response_model=KnowledgeObjectView)
async def knowledge_object_by_id(
    object_id: str,
    session: SessionDep,
) -> KnowledgeObjectView:
    result = await get_object_by_id(session, object_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="knowledge object not found",
        )
    return result
