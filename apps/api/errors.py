from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, JsonValue

from apps.application.errors import ApplicationError


class ProblemDetail(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    code: str
    instance: str | None = None
    request_id: str
    retryable: bool = False
    context: dict[str, JsonValue] = Field(default_factory=dict)


_STATUS_BY_CODE = {
    "resource_not_found": 404,
    "revision_conflict": 409,
    "lifecycle_conflict": 409,
    "permission_denied": 403,
    "dependency_unavailable": 503,
    "provider_unavailable": 503,
    "capability_unavailable": 503,
    "budget_exhausted": 409,
    "deadline_exceeded": 409,
    "rate_limited": 429,
    "idempotency_conflict": 409,
}

_TITLE_BY_STATUS = {
    403: "Permission denied",
    404: "Resource not found",
    409: "Request conflict",
    429: "Rate limited",
    500: "Internal server error",
    503: "Dependency unavailable",
}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApplicationError)
    async def application_error_handler(request: Request, exc: ApplicationError) -> JSONResponse:
        status_code = _STATUS_BY_CODE.get(exc.code, 500)
        return _problem_response(
            request,
            status_code=status_code,
            code=exc.code,
            detail=exc.detail,
            retryable=exc.retryable,
            context=exc.context,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        if not _is_product_path(request.url.path):
            return await request_validation_exception_handler(request, exc)
        return _problem_response(
            request,
            status_code=422,
            code="validation_error",
            detail="request validation failed",
            retryable=False,
            context={"errors": _json_safe(exc.errors())},
        )


def _problem_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    detail: str,
    retryable: bool,
    context: dict[str, Any] | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", request.headers.get("X-Request-ID", ""))
    body = ProblemDetail(
        type=f"urn:secfusion:problem:{code}",
        title=_TITLE_BY_STATUS.get(status_code, "Request failed"),
        status=status_code,
        detail=detail,
        code=code,
        instance=request.url.path,
        request_id=request_id,
        retryable=retryable,
        context=_json_safe(context or {}),
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        media_type="application/problem+json",
    )


def _is_product_path(path: str) -> bool:
    return path.startswith(
        (
            "/api/v1/investigations",
            "/api/v1/questions",
            "/api/v1/decisions",
            "/api/v1/intelligence",
            "/api/v1/evidence",
            "/api/v1/incidents",
            "/api/v1/sources",
            "/api/v1/system",
        )
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
