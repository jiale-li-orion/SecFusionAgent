from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, JsonValue
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import SessionDep
from apps.api.dependencies import database_session as database_session
from apps.application.commands.start_investigation import InvestigationTaskLauncher
from apps.decision_runtime import DecisionRuntime
from apps.model_runtime import create_recorded_model_provider
from packages.evaluation.m1_m3 import SourceCoverageReport, source_coverage_report
from packages.intelligence.knowledge.read import get_vulnerability_by_cve
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import (
    EvidenceLinkModel,
    KnowledgeRevisionModel,
    ObjectModel,
)
from packages.investigation.cases.service import CaseService
from packages.investigation.state.contracts import EvidenceNeedContract, EvidenceNeedStatus
from packages.investigation.state.service import InvestigationStateService
from packages.investigation.storage.models import (
    InvestigationCaseModel,
    InvestigationSnapshotModel,
    InvestigationTrajectoryModel,
)
from packages.monitoring.storage.models import SourceStateModel
from packages.reasoning.citation import CitationSource
from packages.reasoning.model import ModelDecisionPlanner
from packages.shared.config import Settings, get_settings
from packages.sources.inventory import load_source_inventory
from packages.sources.storage.models import SourceModel
from packages.task_runtime.contracts.models import (
    TaskKind,
)
from packages.task_runtime.storage.models import TaskContractVersionModel, TaskRunModel
from packages.task_runtime.storage.service import (
    get_task_context,
    get_task_contract_for_run,
    get_task_run,
    list_task_events,
)

router = APIRouter(prefix="/api/v1/workbench", tags=["workbench"])


class WorkbenchOverview(BaseModel):
    environment: str
    workbench_enabled: bool
    model_configured: bool
    latest_knowledge_revision: int
    source_count: int
    source_failure_count: int
    object_count: int
    case_count: int
    active_case_count: int
    task_count: int
    running_task_count: int


class SourceStatusView(BaseModel):
    source_id: str
    source_class: str
    source_role: str
    retention_mode: str
    access_mode: str
    enabled: bool
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    last_change_at: datetime | None = None
    next_due_at: datetime | None = None
    consecutive_failures: int = 0
    backoff_until: datetime | None = None


class TaskSummary(BaseModel):
    run_id: str
    task_kind: str
    role_id: str
    status: str
    case_id: str | None = None
    parent_run_id: str | None = None
    context_revision: int
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None
    stop_reason: str | None = None


class CaseSummary(BaseModel):
    case_id: str
    task_signature: str
    target_object_ids: list[str]
    goal: str
    status: str
    current_revision: int
    initial_knowledge_revision: int | None = None
    created_at: datetime
    closed_at: datetime | None = None


class CaseCreateRequest(BaseModel):
    cve_id: str | None = None
    object_id: str | None = None
    goal: str = Field(min_length=1)
    evidence_question: str = Field(min_length=1)
    purpose: str = "interactive_investigation"
    task_signature: str = "workbench-investigation"
    required_source_roles: list[str] = Field(default_factory=list)
    priority: int = Field(default=50, ge=0, le=100)


class InvestigationRunRequest(BaseModel):
    task_kind: TaskKind = TaskKind.INVESTIGATE_RELATION
    required_need_ids: list[str] = Field(default_factory=list)
    allow_wait: bool = True
    timeout_seconds: int = Field(default=300, ge=30, le=3600)
    agent_turns: int = Field(default=8, ge=1, le=64)
    tool_calls: int = Field(default=12, ge=0, le=128)


class EnrichmentTriggerRequest(BaseModel):
    cve_id: str
    object_id: str | None = None


def _settings() -> Settings:
    return get_settings()


def _require_workbench_mutation(settings: Settings) -> None:
    if not settings.api_workbench_enabled or settings.environment not in {"dev", "test"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="workbench disabled")


router.dependencies.append(Depends(lambda: _require_workbench_mutation(_settings())))


@router.get("/overview", response_model=WorkbenchOverview)
async def overview(session: SessionDep) -> WorkbenchOverview:
    settings = _settings()
    latest_revision = int(
        await session.scalar(select(func.max(KnowledgeRevisionModel.revision))) or 0
    )
    source_count = int(await session.scalar(select(func.count()).select_from(SourceModel)) or 0)
    source_failure_count = int(
        await session.scalar(
            select(func.count())
            .select_from(SourceStateModel)
            .where(SourceStateModel.consecutive_failures > 0)
        )
        or 0
    )
    object_count = int(await session.scalar(select(func.count()).select_from(ObjectModel)) or 0)
    case_count = int(
        await session.scalar(select(func.count()).select_from(InvestigationCaseModel)) or 0
    )
    active_case_count = int(
        await session.scalar(
            select(func.count())
            .select_from(InvestigationCaseModel)
            .where(
                InvestigationCaseModel.status.in_(
                    ["created", "active", "waiting", "open", "running"]
                )
            )
        )
        or 0
    )
    task_count = int(await session.scalar(select(func.count()).select_from(TaskRunModel)) or 0)
    running_task_count = int(
        await session.scalar(
            select(func.count())
            .select_from(TaskRunModel)
            .where(
                TaskRunModel.status.in_(
                    ["submitted", "queued", "running", "waiting_input", "waiting_dependency"]
                )
            )
        )
        or 0
    )
    return WorkbenchOverview(
        environment=settings.environment,
        workbench_enabled=settings.api_workbench_enabled,
        model_configured=bool(settings.model_base_url and settings.model_name),
        latest_knowledge_revision=latest_revision,
        source_count=source_count,
        source_failure_count=source_failure_count,
        object_count=object_count,
        case_count=case_count,
        active_case_count=active_case_count,
        task_count=task_count,
        running_task_count=running_task_count,
    )


@router.get("/sources", response_model=list[SourceStatusView])
async def list_sources(session: SessionDep, limit: int = 200) -> list[SourceStatusView]:
    rows = (
        await session.execute(
            select(SourceModel, SourceStateModel)
            .outerjoin(SourceStateModel, SourceStateModel.source_id == SourceModel.source_id)
            .order_by(SourceModel.source_class, SourceModel.source_id)
            .limit(min(max(limit, 1), 500))
        )
    ).all()
    result: list[SourceStatusView] = []
    for source, state_row in rows:
        result.append(
            SourceStatusView(
                source_id=source.source_id,
                source_class=source.source_class,
                source_role=source.source_role,
                retention_mode=source.retention_mode,
                access_mode=source.access_mode,
                enabled=source.enabled,
                last_attempt_at=state_row.last_attempt_at if state_row else None,
                last_success_at=state_row.last_success_at if state_row else None,
                last_change_at=state_row.last_change_at if state_row else None,
                next_due_at=state_row.next_due_at if state_row else None,
                consecutive_failures=state_row.consecutive_failures if state_row else 0,
                backoff_until=state_row.backoff_until if state_row else None,
            )
        )
    return result


@router.get("/evaluation/source-coverage", response_model=SourceCoverageReport)
async def source_coverage() -> SourceCoverageReport:
    return source_coverage_report(load_source_inventory(Path("config/source-inventory.json")))


@router.get("/tasks", response_model=list[TaskSummary])
async def list_tasks(
    session: SessionDep,
    task_status: str | None = None,
    case_id: str | None = None,
    limit: int = 100,
) -> list[TaskSummary]:
    stmt = (
        select(TaskRunModel, TaskContractVersionModel)
        .join(
            TaskContractVersionModel,
            TaskContractVersionModel.task_contract_version_id
            == TaskRunModel.task_contract_version_id,
        )
        .order_by(TaskRunModel.created_at.desc())
        .limit(min(max(limit, 1), 500))
    )
    if task_status:
        stmt = stmt.where(TaskRunModel.status == task_status)
    if case_id:
        stmt = stmt.where(TaskRunModel.case_id == case_id)
    rows = (await session.execute(stmt)).all()
    return [
        TaskSummary(
            run_id=run.run_id,
            task_kind=contract.task_kind,
            role_id=run.role_id,
            status=run.status,
            case_id=run.case_id,
            parent_run_id=run.parent_run_id,
            context_revision=run.context_revision,
            created_at=run.created_at,
            updated_at=run.updated_at,
            finished_at=run.finished_at,
            stop_reason=run.stop_reason,
        )
        for run, contract in rows
    ]


@router.get("/tasks/{run_id}")
async def task_detail(run_id: str, session: SessionDep) -> dict[str, object]:
    try:
        run = await get_task_run(session, run_id)
        contract = await get_task_contract_for_run(session, run_id)
        context = await get_task_context(session, run_id)
        events = await list_task_events(session, run_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found") from exc
    return {
        "run": run.model_dump(mode="json"),
        "contract": contract.model_dump(mode="json"),
        "context": context.model_dump(mode="json"),
        "events": [item.model_dump(mode="json") for item in events],
    }


@router.get("/cases", response_model=list[CaseSummary])
async def list_cases(
    session: SessionDep,
    case_status: str | None = None,
    limit: int = 100,
) -> list[CaseSummary]:
    stmt = (
        select(InvestigationCaseModel)
        .order_by(InvestigationCaseModel.created_at.desc())
        .limit(min(max(limit, 1), 500))
    )
    if case_status:
        stmt = stmt.where(InvestigationCaseModel.status == case_status)
    models = list(await session.scalars(stmt))
    return [
        CaseSummary(
            case_id=item.case_id,
            task_signature=item.task_signature,
            target_object_ids=list(item.target_object_ids),
            goal=item.goal,
            status=item.status,
            current_revision=item.current_revision,
            initial_knowledge_revision=item.initial_knowledge_revision,
            created_at=item.created_at,
            closed_at=item.closed_at,
        )
        for item in models
    ]


@router.get("/cases/{case_id}")
async def case_detail(case_id: str, session: SessionDep) -> dict[str, object]:
    case = await session.get(InvestigationCaseModel, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
    state_service = InvestigationStateService()
    state_view = await state_service.get_state(session, case_id)
    needs = await state_service.list_evidence_needs(session, case_id)
    trajectories = list(
        await session.scalars(
            select(InvestigationTrajectoryModel)
            .where(InvestigationTrajectoryModel.case_id == case_id)
            .order_by(InvestigationTrajectoryModel.started_at.desc())
        )
    )
    snapshots = list(
        await session.scalars(
            select(InvestigationSnapshotModel)
            .where(InvestigationSnapshotModel.case_id == case_id)
            .order_by(InvestigationSnapshotModel.created_at.desc())
        )
    )
    return {
        "case": CaseSummary(
            case_id=case.case_id,
            task_signature=case.task_signature,
            target_object_ids=list(case.target_object_ids),
            goal=case.goal,
            status=case.status,
            current_revision=case.current_revision,
            initial_knowledge_revision=case.initial_knowledge_revision,
            created_at=case.created_at,
            closed_at=case.closed_at,
        ).model_dump(mode="json"),
        "state": state_view.model_dump(mode="json"),
        "evidence_needs": [item.model_dump(mode="json") for item in needs],
        "trajectories": [
            {
                "trajectory_id": item.trajectory_id,
                "status": item.status,
                "outcome": item.outcome,
                "started_at": item.started_at.isoformat(),
                "finished_at": item.finished_at.isoformat() if item.finished_at else None,
                "tool_calls": item.tool_calls,
                "latency_ms": item.latency_ms,
            }
            for item in trajectories
        ],
        "snapshots": [
            {
                "snapshot_id": item.snapshot_id,
                "case_revision": item.case_revision,
                "knowledge_revision": item.knowledge_revision,
                "policy_revision": item.policy_revision,
                "capability_registry_revision": item.capability_registry_revision,
                "created_at": item.created_at.isoformat(),
            }
            for item in snapshots
        ],
    }


@router.post("/cases", status_code=status.HTTP_201_CREATED)
async def create_case(payload: CaseCreateRequest, session: SessionDep) -> dict[str, object]:
    settings = _settings()
    _require_workbench_mutation(settings)
    if payload.object_id:
        obj = await session.get(ObjectModel, payload.object_id)
        if obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="object not found")
        object_id = obj.object_id
    elif payload.cve_id:
        view = await get_vulnerability_by_cve(session, payload.cve_id)
        if view is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="vulnerability not found",
            )
        object_id = view.object_id
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="object_id or cve_id is required",
        )
    latest_revision = int(
        await session.scalar(select(func.max(KnowledgeRevisionModel.revision))) or 0
    )
    case = await CaseService().create(
        session,
        task_signature=payload.task_signature,
        target_object_ids=[object_id],
        goal=payload.goal,
        initial_knowledge_revision=latest_revision,
    )
    opened = await InvestigationStateService().open_evidence_need(
        session,
        case_id=case.case_id,
        base_case_revision=0,
        need_id=str(uuid4()),
        proposition_or_question=payload.evidence_question,
        purpose=payload.purpose,
        target_objects=[object_id],
        evidence_contract=EvidenceNeedContract(required_source_roles=payload.required_source_roles),
        priority=payload.priority,
    )
    await session.commit()
    return {
        "case": case.model_dump(mode="json"),
        "evidence_need": opened.need.model_dump(mode="json"),
    }


@router.post("/cases/{case_id}/runs", status_code=status.HTTP_201_CREATED)
async def create_investigation_run(
    case_id: str,
    payload: InvestigationRunRequest,
    session: SessionDep,
) -> dict[str, object]:
    settings = _settings()
    _require_workbench_mutation(settings)
    case_model = await session.get(InvestigationCaseModel, case_id)
    if case_model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
    state_service = InvestigationStateService()
    if payload.required_need_ids:
        required_need_ids = payload.required_need_ids
    else:
        needs = await state_service.list_evidence_needs(
            session,
            case_id,
            statuses={EvidenceNeedStatus.OPEN, EvidenceNeedStatus.BLOCKED},
        )
        required_need_ids = [item.need_id for item in needs]
    if not required_need_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="case has no open evidence need",
        )
    trigger_ref = f"workbench:{uuid4()}"
    launched = await InvestigationTaskLauncher(
        policy_path=settings.runtime_policy_path,
        task_event_stream_name=settings.task_event_stream_name,
        state_service=state_service,
    ).launch(
        session,
        case_id=case_id,
        task_kind=payload.task_kind,
        required_need_ids=required_need_ids,
        principal="user:workbench",
        trigger_ref=trigger_ref,
        surface="api-workbench",
        request_id=None,
        trace_id=None,
        allow_wait=payload.allow_wait,
        timeout_seconds=payload.timeout_seconds,
        agent_turns=payload.agent_turns,
        tool_calls=payload.tool_calls,
    )
    await session.commit()
    return {
        "run": launched.run.model_dump(mode="json"),
        "admission": launched.admission.model_dump(mode="json"),
        "model_configured": bool(settings.model_base_url and settings.model_name),
    }


@router.post("/enrichment", status_code=status.HTTP_202_ACCEPTED)
async def trigger_enrichment(
    payload: EnrichmentTriggerRequest,
    session: SessionDep,
) -> dict[str, object]:
    settings = _settings()
    _require_workbench_mutation(settings)
    if payload.object_id:
        object_id = payload.object_id
        if await session.get(ObjectModel, object_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="object not found")
    else:
        view = await get_vulnerability_by_cve(session, payload.cve_id)
        if view is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="vulnerability not found",
            )
        object_id = view.object_id
    from apps.worker.celery_app import celery_app

    trigger_ref = f"workbench:{uuid4()}"
    message = celery_app.send_task(
        "secfusion.enrichment.vulnerability",
        args=[
            {
                "cve_id": payload.cve_id.upper(),
                "object_id": object_id,
                "trigger_ref": trigger_ref,
            }
        ],
    )
    return {
        "accepted": True,
        "celery_task_id": message.id,
        "trigger_ref": trigger_ref,
        "object_id": object_id,
        "cve_id": payload.cve_id.upper(),
    }


@router.post("/cases/{case_id}/decision")
async def run_decision(
    case_id: str,
    request: Request,
    session: SessionDep,
) -> dict[str, object]:
    settings = _settings()
    _require_workbench_mutation(settings)
    if not settings.model_base_url or not settings.model_name:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="model provider is not configured",
        )
    state_service = InvestigationStateService()
    try:
        state_view = await state_service.get_state(session, case_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found") from exc
    citation_sources = await _citation_sources(session, state_view)
    await session.rollback()
    async with httpx.AsyncClient(timeout=settings.model_timeout_seconds) as client:
        provider = create_recorded_model_provider(
            settings,
            request.app.state.session_factory,
            client,
        )
        if provider is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="model provider is unavailable",
            )
        proposal = await ModelDecisionPlanner(provider).plan(
            state_view,
            citation_sources=citation_sources,
        )
    async with session.begin():
        outcome = await DecisionRuntime().commit_proposal(
            session,
            state=state_view,
            proposal=proposal,
            citation_sources=citation_sources,
        )
    return outcome.model_dump(mode="json")


async def _citation_sources(session: AsyncSession, state_view) -> list[CitationSource]:
    refs = {
        ref
        for group in (
            state_view.confirmed,
            state_view.tentative,
            state_view.conflicts,
            state_view.unknowns,
            state_view.hypotheses,
        )
        for item in group
        for ref in item.evidence_refs
        if ref.startswith("evidence:")
    }
    result: list[CitationSource] = []
    for ref in sorted(refs):
        link_id = ref.removeprefix("evidence:")
        link = await session.get(EvidenceLinkModel, link_id)
        if link is None:
            continue
        observation = await session.get(ObservationModel, link.observation_id)
        if observation is None:
            continue
        source_ref = f"source:{observation.source_id}:{observation.external_object_id}"
        if observation.external_revision:
            source_ref += f"@{observation.external_revision}"
        result.append(
            CitationSource(
                evidence_ref=ref,
                source_ref=source_ref,
                locator=cast(dict[str, JsonValue], dict(link.locator)),
            )
        )
    return result
