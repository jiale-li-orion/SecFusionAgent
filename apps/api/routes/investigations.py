from __future__ import annotations

from fastapi import APIRouter, Query, Response, status
from pydantic import BaseModel, Field, model_validator

from apps.api.dependencies import RequestContextDep, SessionDep
from apps.api.errors import ProblemDetail
from apps.application.commands.start_investigation import (
    StartInvestigationCommand,
    StartInvestigationUseCase,
)
from apps.application.queries.investigations import InvestigationQueries
from apps.application.views.investigations import InvestigationPage, InvestigationView
from packages.shared.config import get_settings
from packages.task_runtime.contracts.models import TaskKind

router = APIRouter(prefix="/api/v1/investigations", tags=["investigations"])


class StartInvestigationRequest(BaseModel):
    cve_id: str | None = None
    object_id: str | None = None
    goal: str = Field(min_length=1)
    evidence_question: str = Field(min_length=1)
    purpose: str = "interactive_investigation"
    task_kind: TaskKind = TaskKind.INVESTIGATE_RELATION
    required_source_roles: list[str] = Field(default_factory=list)
    priority: int = Field(default=50, ge=0, le=100)
    allow_wait: bool = True
    timeout_seconds: int = Field(default=300, ge=30, le=3600)
    agent_turns: int = Field(default=8, ge=1, le=64)
    tool_calls: int = Field(default=12, ge=0, le=128)

    @model_validator(mode="after")
    def validate_target(self) -> StartInvestigationRequest:
        if bool(self.cve_id) == bool(self.object_id):
            raise ValueError("exactly one of cve_id or object_id is required")
        return self


@router.post(
    "",
    response_model=InvestigationView,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        403: {"model": ProblemDetail},
        404: {"model": ProblemDetail},
        422: {"model": ProblemDetail},
    },
)
async def start_investigation(
    payload: StartInvestigationRequest,
    response: Response,
    session: SessionDep,
    context: RequestContextDep,
) -> InvestigationView:
    settings = get_settings()
    use_case = StartInvestigationUseCase(
        policy_path=settings.runtime_policy_path,
        task_event_stream_name=settings.task_event_stream_name,
    )
    result = await use_case.execute(
        session,
        StartInvestigationCommand(
            principal=context.principal,
            request_id=context.request_id,
            trace_id=context.trace_id,
            cve_id=payload.cve_id,
            object_id=payload.object_id,
            goal=payload.goal,
            evidence_question=payload.evidence_question,
            purpose=payload.purpose,
            task_kind=payload.task_kind,
            required_source_roles=payload.required_source_roles,
            priority=payload.priority,
            allow_wait=payload.allow_wait,
            timeout_seconds=payload.timeout_seconds,
            agent_turns=payload.agent_turns,
            tool_calls=payload.tool_calls,
        ),
    )
    response.headers["Location"] = f"/api/v1/investigations/{result.investigation.case_id}"
    return result.investigation


@router.get("", response_model=InvestigationPage)
async def list_investigations(
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = None,
    investigation_status: str | None = Query(default=None, alias="status"),
) -> InvestigationPage:
    return await InvestigationQueries().list(
        session,
        limit=limit,
        cursor=cursor,
        status=investigation_status,
    )


@router.get(
    "/{case_id}",
    response_model=InvestigationView,
    responses={404: {"model": ProblemDetail}},
)
async def get_investigation(case_id: str, session: SessionDep) -> InvestigationView:
    return await InvestigationQueries().get(session, case_id)
