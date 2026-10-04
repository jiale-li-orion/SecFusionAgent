from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from apps.api.dependencies import SessionDep
from apps.application.queries.agents import get_agent_learning_overview, get_agent_runtime_overview, get_agent_task_detail
from apps.application.views.agents import AgentLearningOverviewView, AgentRuntimeOverviewView, AgentTaskDetailView

router = APIRouter(prefix="/api/v1", tags=["agents"])


@router.get("/agents/runtime", response_model=AgentRuntimeOverviewView)
async def agent_runtime(
    session: SessionDep,
    task_limit: int = Query(default=72, ge=1, le=200),
) -> AgentRuntimeOverviewView:
    return await get_agent_runtime_overview(session, task_limit=task_limit)


@router.get("/agents/learning", response_model=AgentLearningOverviewView)
async def agent_learning(session: SessionDep) -> AgentLearningOverviewView:
    return await get_agent_learning_overview(session)


@router.get("/tasks/{run_id}", response_model=AgentTaskDetailView)
async def task_detail(run_id: str, session: SessionDep) -> AgentTaskDetailView:
    result = await get_agent_task_detail(session, run_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task run not found")
    return result
