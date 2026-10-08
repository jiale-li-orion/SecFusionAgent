from typing import Annotated

from fastapi import APIRouter, Header, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field

from apps.api.dependencies import RequestContextDep, SessionDep
from apps.api.errors import ProblemDetail
from apps.application.commands.start_enrichment import (
    StartEnrichmentCommand,
    StartEnrichmentUseCase,
    list_product_enrichment_runs,
)
from apps.application.views.enrichment import ProductEnrichmentRunPage, ProductEnrichmentRunView
from packages.intelligence.knowledge.vocabulary import EnrichmentDimension
from packages.shared.config import get_settings

router = APIRouter(prefix="/api/v1/intelligence/objects", tags=["knowledge"])


class StartEnrichmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dimensions: list[EnrichmentDimension] = Field(min_length=1, max_length=12)
    expected_world_revision: int | None = Field(default=None, ge=0)


@router.post(
    "/{object_id}/enrichment/runs",
    status_code=202,
    response_model=ProductEnrichmentRunView,
    responses={code: {"model": ProblemDetail} for code in (403, 404, 409, 422)},
)
async def start_enrichment(
    object_id: str,
    payload: StartEnrichmentRequest,
    response: Response,
    session: SessionDep,
    context: RequestContextDep,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=128)],
) -> ProductEnrichmentRunView:
    settings = get_settings()
    try:
        result = await StartEnrichmentUseCase(
            policy_path=settings.runtime_policy_path,
            task_event_stream_name=settings.task_event_stream_name,
        ).execute(
            session,
            StartEnrichmentCommand(
                principal=context.principal,
                request_id=context.request_id,
                trace_id=context.trace_id,
                object_id=object_id,
                idempotency_key=idempotency_key,
                dimensions=payload.dimensions,
                expected_world_revision=payload.expected_world_revision,
            ),
        )
    except ValueError as exc:
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("path", "object_id"),
                    "msg": str(exc),
                    "input": object_id,
                }
            ]
        ) from exc
    response.headers["Location"] = result.task_url
    return result


@router.get("/{object_id}/enrichment/runs", response_model=ProductEnrichmentRunPage)
async def enrichment_runs(
    object_id: str,
    session: SessionDep,
    context: RequestContextDep,
) -> ProductEnrichmentRunPage:
    return await list_product_enrichment_runs(session, object_id, principal=context.principal)
