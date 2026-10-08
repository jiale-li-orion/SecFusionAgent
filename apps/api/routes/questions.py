from __future__ import annotations

import asyncio
import json

import httpx
from fastapi import APIRouter, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

from apps.api.dependencies import RequestContextDep, SessionDep
from apps.api.errors import ProblemDetail
from apps.application.commands.ask_question import AskQuestionCommand, AskQuestionUseCase
from apps.application.errors import ApplicationError
from apps.application.question_sessions import (
    AccountConversationPage,
    QuestionSessionHistoryPage,
    QuestionSessionStore,
)
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


class StreamQuestionRequest(AskQuestionRequest):
    include_reasoning: bool = False


def _command(payload: AskQuestionRequest, context: RequestContextDep) -> AskQuestionCommand:
    return AskQuestionCommand(
        principal=context.principal,
        request_id=context.request_id,
        trace_id=context.trace_id,
        idempotency_key=context.idempotency_key,
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
    command = _command(payload, context)
    session_factory = getattr(request.app.state, "session_factory", None)
    model_enabled = (
        payload.task_kind in {TaskKind.LOOKUP, TaskKind.RETRIEVE}
        and bool(settings.model_base_url)
        and bool(settings.model_name)
        and session_factory is not None
    )
    if model_enabled:
        assert session_factory is not None
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


def _sse(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/stream")
async def stream_question(
    payload: StreamQuestionRequest,
    request: Request,
    context: RequestContextDep,
) -> StreamingResponse:
    """Stream one real model call; the final Decision remains the only durable answer."""
    settings = get_settings()
    command = _command(payload, context)
    factory = request.app.state.session_factory

    async def events():
        queue: asyncio.Queue[tuple[str, dict[str, object]] | None] = asyncio.Queue()

        async def on_delta(kind: str, fragment: str) -> None:
            if kind != "reasoning" or payload.include_reasoning:
                await queue.put(("model_delta", {"kind": kind, "text": fragment}))

        async def execute() -> None:
            try:
                async with factory() as session:
                    model_enabled = (
                        payload.task_kind in {TaskKind.LOOKUP, TaskKind.RETRIEVE}
                        and bool(settings.model_base_url)
                        and bool(settings.model_name)
                    )
                    if model_enabled:
                        async with httpx.AsyncClient(
                            timeout=min(
                                settings.model_timeout_seconds, payload.interactive_timeout_seconds
                            )
                        ) as client:
                            runtime_artifacts = await create_runtime_artifact_service(settings)
                            provider = create_recorded_model_provider(
                                settings,
                                factory,
                                client,
                                artifact_service=runtime_artifacts,
                                on_delta=on_delta,
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
                await queue.put(("result", result.model_dump(mode="json")))
            except ApplicationError as exc:
                await queue.put(("error", {"code": exc.code, "message": str(exc)}))
            except Exception:
                await queue.put(
                    ("error", {"code": "question_failed", "message": "Question execution failed"})
                )
            finally:
                await queue.put(None)

        worker = asyncio.create_task(execute())
        yield _sse("status", {"phase": "accepted", "request_id": context.request_id})
        while (item := await queue.get()) is not None:
            yield _sse(item[0], item[1])
        await worker

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.get("/sessions", response_model=AccountConversationPage)
async def account_conversations(
    session: SessionDep,
    context: RequestContextDep,
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = None,
) -> AccountConversationPage:
    return await QuestionSessionStore().list_owned(
        session, principal=context.principal, limit=limit, cursor=cursor
    )


@router.get(
    "/sessions/{session_id}",
    response_model=QuestionSessionHistoryPage,
    responses={403: {"model": ProblemDetail}, 404: {"model": ProblemDetail}},
)
async def question_session_history(
    session_id: str,
    session: SessionDep,
    context: RequestContextDep,
    limit: int = Query(default=50, ge=1, le=50),
    before_turn: int | None = Query(default=None, ge=1),
) -> QuestionSessionHistoryPage:
    return await QuestionSessionStore().read_history_page(
        session, session_id=session_id, principal=context.principal,
        limit=limit, before_turn=before_turn,
    )
