from __future__ import annotations

import httpx
from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel, Field, model_validator

from apps.api.dependencies import RequestContextDep, SessionDep
from apps.api.errors import ProblemDetail
from apps.application.commands.ask_question import AskQuestionCommand, AskQuestionUseCase
from apps.application.views.questions import QuestionResultView
from apps.model_runtime import create_recorded_model_provider
from packages.shared.config import get_settings
from packages.task_runtime.contracts.models import TaskKind

router = APIRouter(prefix="/api/v1/questions", tags=["questions"])


class AskQuestionRequest(BaseModel):
    question: str = Field(min_length=1)
    session_id: str | None = None
    cve_id: str | None = None
    object_id: str | None = None
    task_kind: TaskKind = TaskKind.LOOKUP
    required_source_roles: list[str] = Field(default_factory=list)
    priority: int = Field(default=50, ge=0, le=100)
    interactive_timeout_seconds: int = Field(default=5, ge=1, le=30)
    retrieval_limit: int = Field(default=8, ge=1, le=20)

    @model_validator(mode="after")
    def validate_target(self) -> AskQuestionRequest:
        if self.cve_id and self.object_id:
            raise ValueError("cve_id and object_id are mutually exclusive")
        return self


@router.post(
    "",
    response_model=QuestionResultView,
    responses={
        202: {"model": QuestionResultView},
        403: {"model": ProblemDetail},
        404: {"model": ProblemDetail},
        422: {"model": ProblemDetail},
        503: {"model": ProblemDetail},
    },
)
async def ask_question(
    payload: AskQuestionRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    context: RequestContextDep,
) -> QuestionResultView:
    settings = get_settings()
    provider = None
    if payload.task_kind in {TaskKind.LOOKUP, TaskKind.RETRIEVE}:
        if settings.model_base_url and settings.model_name:
            async with httpx.AsyncClient(
                timeout=min(settings.model_timeout_seconds, payload.interactive_timeout_seconds)
            ) as client:
                provider = create_recorded_model_provider(
                    settings,
                    request.app.state.session_factory,
                    client,
                )
                result = await AskQuestionUseCase(
                    policy_path=settings.runtime_policy_path,
                    task_event_stream_name=settings.task_event_stream_name,
                    model_provider=provider,
                ).execute(
                    session,
                    AskQuestionCommand(
                        principal=context.principal,
                        request_id=context.request_id,
                        trace_id=context.trace_id,
                        session_id=payload.session_id,
                        question=payload.question,
                        cve_id=payload.cve_id,
                        object_id=payload.object_id,
                        task_kind=payload.task_kind,
                        required_source_roles=payload.required_source_roles,
                        priority=payload.priority,
                        interactive_timeout_seconds=payload.interactive_timeout_seconds,
                        retrieval_limit=payload.retrieval_limit,
                    ),
                )
        else:
            result = await AskQuestionUseCase(
                policy_path=settings.runtime_policy_path,
                task_event_stream_name=settings.task_event_stream_name,
                model_provider=None,
            ).execute(
                session,
                AskQuestionCommand(
                    principal=context.principal,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                    session_id=payload.session_id,
                    question=payload.question,
                    cve_id=payload.cve_id,
                    object_id=payload.object_id,
                    task_kind=payload.task_kind,
                    required_source_roles=payload.required_source_roles,
                    priority=payload.priority,
                    interactive_timeout_seconds=payload.interactive_timeout_seconds,
                    retrieval_limit=payload.retrieval_limit,
                ),
            )
    else:
        result = await AskQuestionUseCase(
            policy_path=settings.runtime_policy_path,
            task_event_stream_name=settings.task_event_stream_name,
            model_provider=None,
        ).execute(
            session,
            AskQuestionCommand(
                principal=context.principal,
                request_id=context.request_id,
                trace_id=context.trace_id,
                session_id=payload.session_id,
                question=payload.question,
                cve_id=payload.cve_id,
                object_id=payload.object_id,
                task_kind=payload.task_kind,
                required_source_roles=payload.required_source_roles,
                priority=payload.priority,
                interactive_timeout_seconds=payload.interactive_timeout_seconds,
                retrieval_limit=payload.retrieval_limit,
            ),
        )
    if result.mode == "accepted":
        response.status_code = status.HTTP_202_ACCEPTED
        assert result.investigation is not None
        response.headers["Location"] = f"/api/v1/investigations/{result.investigation.case_id}"
    return result
