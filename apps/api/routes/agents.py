from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from apps.api.dependencies import SessionDep
from apps.application.queries.agents import (
    get_agent_controlled_proof,
    get_agent_learning_overview,
    get_agent_runtime_overview,
    get_agent_task_detail,
    list_agent_tasks,
)
from apps.application.views.agents import (
    AgentControlledProofView,
    AgentLearningOverviewView,
    AgentRuntimeOverviewView,
    AgentTaskDetailView,
    AgentTaskPageView,
)

router = APIRouter(prefix="/api/v1", tags=["agents"])


@router.get("/agents/proof", response_model=AgentControlledProofView)
async def agent_controlled_proof() -> AgentControlledProofView:
    return get_agent_controlled_proof()


@router.get("/agents/runtime", response_model=AgentRuntimeOverviewView)
async def agent_runtime(
    session: SessionDep,
    task_limit: int = Query(default=72, ge=1, le=200),
    model_request_limit: int = Query(default=64, ge=1, le=200),
) -> AgentRuntimeOverviewView:
    return await get_agent_runtime_overview(
        session,
        task_limit=task_limit,
        model_request_limit=model_request_limit,
    )


@router.get("/agents/learning", response_model=AgentLearningOverviewView)
async def agent_learning(session: SessionDep) -> AgentLearningOverviewView:
    return await get_agent_learning_overview(session)


@router.get("/tasks", response_model=AgentTaskPageView)
async def tasks(
    session: SessionDep,
    role_id: str | None = Query(default=None, max_length=64),
    status_filter: str | None = Query(default=None, alias="status", max_length=32),
    case_id: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=72, ge=1, le=200),
) -> AgentTaskPageView:
    return await list_agent_tasks(
        session,
        role_id=role_id,
        status=status_filter,
        case_id=case_id,
        limit=limit,
    )


@router.get("/tasks/{run_id}", response_model=AgentTaskDetailView)
async def task_detail(run_id: str, session: SessionDep) -> AgentTaskDetailView:
    result = await get_agent_task_detail(session, run_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task run not found")
    return result
