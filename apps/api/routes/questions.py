from __future__ import annotations

import httpx
from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel, Field, model_validator

from apps.api.dependencies import RequestContextDep, SessionDep
from apps.api.errors import ProblemDetail
from apps.application.commands.ask_question import AskQuestionCommand, AskQuestionUseCase
from apps.application.question_sessions import QuestionSessionStore, QuestionSessionTurn
from apps.application.views.questions import QuestionResultView
from apps.model_runtime import create_recorded_model_provider
from apps.runtime_artifacts import create_runtime_artifact_service
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
    allow_wait: bool = True
    investigation_timeout_seconds: int = Field(default=300, ge=30, le=3600)
    agent_turns: int = Field(default=8, ge=1, le=64)
    tool_calls: int = Field(default=12, ge=0, le=128)

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
    command = AskQuestionCommand(
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
        allow_wait=payload.allow_wait,
        investigation_timeout_seconds=payload.investigation_timeout_seconds,
        agent_turns=payload.agent_turns,
        tool_calls=payload.tool_calls,
    )
    session_factory = getattr(request.app.state, "session_factory", None)
    model_enabled = (
        payload.task_kind in {TaskKind.LOOKUP, TaskKind.RETRIEVE}
        and bool(settings.model_base_url)
        and bool(settings.model_name)
        and session_factory is not None
    )
    if model_enabled:
        async with httpx.AsyncClient(
            timeout=min(settings.model_timeout_seconds, payload.interactive_timeout_seconds)
        ) as client:
            runtime_artifacts = await create_runtime_artifact_service(settings)
            provider = create_recorded_model_provider(
                settings,
                session_factory,
                client,
                artifact_service=runtime_artifacts,
            )
            result = await AskQuestionUseCase(
                policy_path=settings.runtime_policy_path,
                task_event_stream_name=settings.task_event_stream_name,
                model_provider=provider,
            ).execute(session, command)
    else:
        result = await AskQuestionUseCase(
            policy_path=settings.runtime_policy_path,
            task_event_stream_name=settings.task_event_stream_name,
            model_provider=None,
        ).execute(session, command)
    if result.mode == "accepted":
        response.status_code = status.HTTP_202_ACCEPTED
        assert result.investigation is not None
        response.headers["Location"] = f"/api/v1/investigations/{result.investigation.case_id}"
    return result


class QuestionSessionHistoryView(BaseModel):
    session_id: str
    turns: list[QuestionSessionTurn]


@router.get(
    "/sessions/{session_id}",
    response_model=QuestionSessionHistoryView,
    responses={403: {"model": ProblemDetail}, 404: {"model": ProblemDetail}},
)
async def question_session_history(
    session_id: str,
    session: SessionDep,
    context: RequestContextDep,
) -> QuestionSessionHistoryView:
    history = await QuestionSessionStore(history_limit=50).resolve(
        session, session_id=session_id, principal=context.principal
    )
    return QuestionSessionHistoryView(session_id=history.session_id, turns=history.turns)
