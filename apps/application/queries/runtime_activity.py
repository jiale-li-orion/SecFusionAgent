from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.application.views.investigations import (
    ProductRuntimeActivityView,
    ProductRuntimeEventView,
)
from packages.investigation.storage.models import CaseStateEventModel, InvestigationCaseModel
from packages.task_runtime.storage.models import TaskEventModel, TaskRunModel

_TASK_EVENT_MAP = {
    "TaskCreated": "started",
    "TaskStarted": "status_changed",
    "TaskPatched": "progress",
    "ContextUpdated": "progress",
    "EvidenceFound": "progress",
    "KnowledgeChanged": "progress",
    "EnrichmentStateChanged": "progress",
    "InvestigationStateChanged": "progress",
    "TaskBlocked": "status_changed",
    "NeedInput": "waiting",
    "NeedContext": "waiting",
    "BudgetWarning": "progress",
    "ArtifactProduced": "progress",
    "Progress": "progress",
    "TaskCompleted": "completed",
    "TaskFailed": "failed",
    "TaskCanceled": "canceled",
}

_CASE_EVENT_MAP = {
    "fact_confirmed": "finding_added",
    "fact_retracted": "finding_changed",
    "tentative_added": "finding_changed",
    "tentative_removed": "finding_changed",
    "conflict_opened": "conflict_changed",
    "conflict_resolved": "conflict_changed",
    "unknown_opened": "unknown_changed",
    "unknown_resolved": "unknown_changed",
    "hypothesis_added": "finding_changed",
    "hypothesis_rejected": "finding_changed",
    "evidence_need_opened": "evidence_need_changed",
    "evidence_need_resolved": "evidence_need_changed",
    "evidence_attached": "progress",
    "decision_changed": "decision_ready",
    "perception_recorded": "progress",
}


async def get_runtime_activity(
    session: AsyncSession,
    case_id: str,
) -> ProductRuntimeActivityView | None:
    case = await session.get(InvestigationCaseModel, case_id)
    if case is None:
        return None

    task_rows = (
        await session.execute(
            select(TaskEventModel, TaskRunModel)
            .join(TaskRunModel, TaskRunModel.run_id == TaskEventModel.task_run_id)
            .where(TaskRunModel.case_id == case_id)
        )
    ).all()
    case_events = list(
        await session.scalars(
            select(CaseStateEventModel).where(CaseStateEventModel.case_id == case_id)
        )
    )

    events: list[ProductRuntimeEventView] = []
    for event, run in task_rows:
        events.append(
            ProductRuntimeEventView(
                event_id=f"task:{event.event_id}",
                event_type=_TASK_EVENT_MAP.get(event.event_type, "progress"),
                technical_type=event.event_type,
                source_kind="task",
                case_id=case_id,
                task_run_id=run.run_id,
                role_id=run.role_id,
                status=_status_for_task_event(event.event_type, run.status),
                actor=event.producer,
                summary=_task_summary(event.event_type, run.role_id),
                occurred_at=event.emitted_at,
            )
        )
    for case_event in case_events:
        events.append(
            ProductRuntimeEventView(
                event_id=f"case:{case_event.event_id}",
                event_type=_CASE_EVENT_MAP.get(case_event.event_type, "progress"),
                technical_type=case_event.event_type,
                source_kind="case_state",
                case_id=case_id,
                actor=case_event.writer,
                summary=case_event.proposition or _case_summary(case_event.event_type),
                evidence_refs=list(case_event.evidence_refs),
                case_revision=case_event.case_revision,
                occurred_at=case_event.created_at,
            )
        )
    events.sort(key=lambda item: (item.occurred_at, item.source_kind, item.event_id))
    return ProductRuntimeActivityView(case_id=case_id, events=events)


def _status_for_task_event(event_type: str, current_status: str) -> str | None:
    return {
        "TaskCreated": "submitted",
        "TaskStarted": "running",
        "NeedInput": "waiting_input",
        "NeedContext": "waiting_dependency",
        "TaskBlocked": "blocked",
        "TaskCompleted": "completed",
        "TaskFailed": "failed",
        "TaskCanceled": "cancelled",
    }.get(event_type, current_status if event_type == "TaskPatched" else None)


def _task_summary(event_type: str, role_id: str) -> str:
    phrases = {
        "TaskCreated": "Task accepted by runtime",
        "TaskStarted": "Role started execution",
        "TaskPatched": "Task state updated",
        "ContextUpdated": "Context updated",
        "EvidenceFound": "New evidence entered the task context",
        "KnowledgeChanged": "Knowledge changed during execution",
        "EnrichmentStateChanged": "Enrichment state changed",
        "InvestigationStateChanged": "Investigation state changed",
        "TaskBlocked": "Task was blocked",
        "NeedInput": "Task is waiting for user input",
        "NeedContext": "Task is waiting for a dependency",
        "BudgetWarning": "Execution budget warning",
        "ArtifactProduced": "Runtime artifact produced",
        "Progress": "Task reported progress",
        "TaskCompleted": "Task completed",
        "TaskFailed": "Task failed",
        "TaskCanceled": "Task canceled",
    }
    return f"{role_id}: {phrases.get(event_type, event_type)}"


def _case_summary(event_type: str) -> str:
    return {
        "fact_confirmed": "Finding confirmed",
        "fact_retracted": "Confirmed finding retracted",
        "tentative_added": "Tentative finding added",
        "tentative_removed": "Tentative finding removed",
        "conflict_opened": "Evidence conflict opened",
        "conflict_resolved": "Evidence conflict resolved",
        "unknown_opened": "Unknown recorded",
        "unknown_resolved": "Unknown resolved",
        "hypothesis_added": "Hypothesis added",
        "hypothesis_rejected": "Hypothesis rejected",
        "evidence_need_opened": "New evidence need opened",
        "evidence_need_resolved": "Evidence need resolved",
        "evidence_attached": "Evidence attached",
        "decision_changed": "Decision became available",
        "perception_recorded": "Perception recorded",
    }.get(event_type, event_type)
