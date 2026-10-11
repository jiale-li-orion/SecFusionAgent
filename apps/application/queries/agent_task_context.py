"""Batch product labels from durable, authorized task context; never infer outcomes."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.application.queries.ownership import investigation_owner, public_system_case
from apps.application.question_sessions import QuestionSessionModel
from apps.application.views.agents import AgentTaskSummaryView
from packages.intelligence.storage.knowledge_models import ObjectModel
from packages.investigation.storage.models import InvestigationCaseModel
from packages.runtime.storage.models import ExecutionRunModel
from packages.task_runtime.storage.models import TaskContractVersionModel, TaskRunModel


def _string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


async def apply_task_context(
    session: AsyncSession,
    summaries: list[AgentTaskSummaryView],
    runs: list[TaskRunModel],
    contracts: list[TaskContractVersionModel],
    executions: list[ExecutionRunModel],
    *,
    principal: str | None,
) -> None:
    contracts_by_id = {row.task_contract_version_id: row for row in contracts}
    runs_by_id = {row.run_id: row for row in runs}
    case_ids = {row.case_id for row in runs if row.case_id}
    case_query = select(InvestigationCaseModel).where(InvestigationCaseModel.case_id.in_(case_ids))
    if principal is not None:
        case_query = case_query.where(
            or_(
                investigation_owner(InvestigationCaseModel.case_id) == principal,
                public_system_case(InvestigationCaseModel.case_id),
            )
        )
    cases = {row.case_id: row for row in await session.scalars(case_query)} if case_ids else {}
    session_by_run: dict[str, str] = {}
    for execution in executions:
        trace = execution.envelope_json.get("trace_context")
        if isinstance(trace, dict) and (session_id := _string(trace.get("product_session_id"))):
            session_by_run[execution.task_run_id] = session_id
    session_query = select(QuestionSessionModel.session_id).where(
        QuestionSessionModel.session_id.in_(set(session_by_run.values()))
    )
    if principal is not None:
        session_query = session_query.where(QuestionSessionModel.principal == principal)
    visible_sessions = set(await session.scalars(session_query)) if session_by_run else set()
    for summary in summaries:
        run = runs_by_id[summary.run_id]
        contract = contracts_by_id.get(run.task_contract_version_id)
        payload = contract.contract_json if contract else {}
        desired = payload.get("desired_state")
        desired = desired if isinstance(desired, dict) else {}
        case = cases.get(run.case_id or "")
        summary.goal = _string(desired.get("question")) or _string(desired.get("goal"))
        if not summary.goal and case:
            summary.goal = case.goal
        targets = payload.get("target_resources")
        summary.target_refs = (
            [ref for ref in targets if isinstance(ref, str)] if isinstance(targets, list) else []
        )
        if not summary.target_refs and case:
            summary.target_refs = [f"object:{ref}" for ref in case.target_object_ids]
        summary.target_label = _string(desired.get("cve_id"))
        linked_session = session_by_run.get(run.run_id)
        summary.session_id = linked_session if linked_session in visible_sessions else None
    object_ids = {
        ref.removeprefix("object:")
        for item in summaries
        for ref in item.target_refs
        if ref.startswith("object:")
    }
    objects = (
        {
            row.object_id: row
            for row in await session.scalars(
                select(ObjectModel).where(ObjectModel.object_id.in_(object_ids))
            )
        }
        if object_ids
        else {}
    )
    for summary in summaries:
        if summary.target_label:
            continue
        labels = []
        for ref in summary.target_refs:
            obj = objects.get(ref.removeprefix("object:")) if ref.startswith("object:") else None
            if obj:
                labels.append(
                    _string(obj.properties.get("name"))
                    or _string(obj.properties.get("title"))
                    or obj.canonical_key
                )
            elif ref.startswith("cve:"):
                labels.append(ref.removeprefix("cve:"))
        summary.target_label = " · ".join(dict.fromkeys(labels)) or None
