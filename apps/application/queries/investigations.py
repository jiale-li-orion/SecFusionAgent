from __future__ import annotations

import base64
import json
from datetime import datetime

from pydantic import JsonValue
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.application.errors import ResourceNotFoundError
from apps.application.queries.ownership import investigation_owner, public_system_case
from apps.application.question_sessions import QuestionSessionStore
from apps.application.views.investigations import (
    DecisionCitationView,
    DecisionConclusionView,
    DecisionView,
    EvidenceNeedSummaryView,
    InvestigationActivitySummaryView,
    InvestigationFindingView,
    InvestigationOriginScope,
    InvestigationPage,
    InvestigationView,
)
from packages.investigation.state.contracts import EvidenceNeedStatus, InvestigationStateItem
from packages.investigation.state.service import InvestigationStateService
from packages.investigation.storage.models import InvestigationCaseModel
from packages.reasoning.decision import DecisionResult
from packages.runtime.storage.models import ExecutionRunModel
from packages.task_runtime.storage.models import TaskContractVersionModel, TaskRunModel


class InvestigationQueries:
    def __init__(
        self,
        state_service: InvestigationStateService | None = None,
        session_store: QuestionSessionStore | None = None,
    ) -> None:
        self._state_service = state_service or InvestigationStateService()
        self._session_store = session_store or QuestionSessionStore()

    async def get(
        self,
        session: AsyncSession,
        case_id: str,
        *,
        principal: str | None = None,
    ) -> InvestigationView:
        case = await session.get(InvestigationCaseModel, case_id)
        if case is None:
            raise ResourceNotFoundError(
                "investigation not found",
                context={"case_id": case_id},
            )
        await self.require_access(session, case_id, principal=principal)
        return await self._view(session, case, principal=principal)

    async def require_access(
        self, session: AsyncSession, case_id: str, *, principal: str | None = None
    ) -> None:
        if principal is None:
            return
        owner, public = (
            await session.execute(select(investigation_owner(case_id), public_system_case(case_id)))
        ).one()
        if owner != principal and not public:
            raise ResourceNotFoundError("investigation not found", context={"case_id": case_id})

    async def list(
        self,
        session: AsyncSession,
        *,
        limit: int = 50,
        cursor: str | None = None,
        status: str | None = None,
        product_only: bool = False,
        principal: str | None = None,
    ) -> InvestigationPage:
        bounded_limit = min(max(limit, 1), 100)
        stmt = select(InvestigationCaseModel)
        if principal is not None:
            stmt = stmt.where(investigation_owner(InvestigationCaseModel.case_id) == principal)
        if product_only:
            product_run = (
                select(TaskRunModel.run_id)
                .join(
                    TaskContractVersionModel,
                    TaskContractVersionModel.task_contract_version_id
                    == TaskRunModel.task_contract_version_id,
                )
                .where(
                    TaskRunModel.case_id == InvestigationCaseModel.case_id,
                    TaskContractVersionModel.principal.startswith("user:"),
                )
                .exists()
            )
            stmt = stmt.where(product_run)
        if status:
            stmt = stmt.where(InvestigationCaseModel.status == status)
        if cursor:
            created_at, case_id = _decode_cursor(cursor)
            stmt = stmt.where(
                or_(
                    InvestigationCaseModel.created_at < created_at,
                    and_(
                        InvestigationCaseModel.created_at == created_at,
                        InvestigationCaseModel.case_id < case_id,
                    ),
                )
            )
        stmt = stmt.order_by(
            InvestigationCaseModel.created_at.desc(),
            InvestigationCaseModel.case_id.desc(),
        ).limit(bounded_limit + 1)
        models = list(await session.scalars(stmt))
        has_more = len(models) > bounded_limit
        visible = models[:bounded_limit]
        items = [await self._view(session, item, principal=principal) for item in visible]
        next_cursor = None
        if has_more and visible:
            tail = visible[-1]
            next_cursor = _encode_cursor(tail.created_at, tail.case_id)
        return InvestigationPage(items=items, next_cursor=next_cursor, has_more=has_more)

    async def _view(
        self,
        session: AsyncSession,
        case: InvestigationCaseModel,
        *,
        principal: str | None = None,
    ) -> InvestigationView:
        state = await self._state_service.get_state(session, case.case_id)
        needs = await self._state_service.list_evidence_needs(
            session,
            case.case_id,
            statuses={EvidenceNeedStatus.OPEN, EvidenceNeedStatus.BLOCKED},
        )
        run_row = await session.execute(
            select(TaskRunModel, TaskContractVersionModel, ExecutionRunModel)
            .join(
                TaskContractVersionModel,
                TaskContractVersionModel.task_contract_version_id
                == TaskRunModel.task_contract_version_id,
            )
            .outerjoin(ExecutionRunModel, ExecutionRunModel.task_run_id == TaskRunModel.run_id)
            .where(TaskRunModel.case_id == case.case_id)
            .order_by(TaskRunModel.created_at.desc(), TaskRunModel.run_id.desc())
            .limit(1)
        )
        latest = run_row.first()
        if latest is None:
            activity = InvestigationActivitySummaryView(phase="created")
            execution_profile = None
            terminal_reason = None
            effective_status = case.status
            owner_principal = None
        else:
            run, contract, execution = latest
            owner_principal = contract.principal
            execution_profile = None
            if execution is not None:
                execution_profile = (
                    str(execution.envelope_json.get("execution_profile") or "") or None
                )
            if run.role_id == "DecisionRole":
                # The final reasoning step is DIRECT; the Case retains its investigation profile.
                investigation_execution = await session.scalar(
                    select(ExecutionRunModel)
                    .join(TaskRunModel, TaskRunModel.run_id == ExecutionRunModel.task_run_id)
                    .where(
                        TaskRunModel.case_id == case.case_id,
                        TaskRunModel.role_id == "InvestigationRole",
                    )
                    .order_by(TaskRunModel.created_at.desc(), TaskRunModel.run_id.desc())
                    .limit(1)
                )
                if investigation_execution is not None:
                    execution_profile = (
                        str(investigation_execution.envelope_json.get("execution_profile") or "")
                        or None
                    )
            activity = InvestigationActivitySummaryView(
                phase=_phase_from_task_status(run.status),
                actor_role=run.role_id,
                task_kind=contract.task_kind,
                task_status=run.status,
                updated_at=run.updated_at,
            )
            terminal_reason = run.stop_reason
            effective_status = _effective_status(case.status, run.status)

        decision = decision_view(state.current_decision, state.updated_at)
        continuation_session_id = None
        if principal is not None:
            continuation_session_id = await self._session_store.latest_session_id_for_investigation(
                session,
                investigation_ref=f"case:{case.case_id}",
                principal=principal,
            )
        return InvestigationView(
            case_id=case.case_id,
            case_lifecycle=case.status,
            continuation_session_id=continuation_session_id,
            origin_scope=_origin_scope(owner_principal),
            can_cancel=(
                principal is not None
                and owner_principal == principal
                and case.status in {"created", "active", "waiting"}
            ),
            revision=state.case_revision,
            status=effective_status,
            execution_profile=execution_profile,
            target_object_ids=list(case.target_object_ids),
            goal=case.goal,
            confirmed_findings=[_finding_view(item) for item in state.confirmed],
            conflicts=[_finding_view(item) for item in state.conflicts],
            unknowns=[_finding_view(item) for item in state.unknowns],
            open_evidence_needs=[
                EvidenceNeedSummaryView(
                    need_id=item.need_id,
                    question=item.proposition_or_question,
                    purpose=item.purpose,
                    status=item.status.value,
                    priority=item.priority,
                    required_source_roles=list(item.evidence_contract.required_source_roles),
                    updated_revision=item.updated_revision,
                )
                for item in needs
            ],
            current_activity=activity,
            latest_decision=decision,
            terminal_reason=terminal_reason,
            created_at=case.created_at,
            updated_at=state.updated_at,
            closed_at=case.closed_at,
        )


def _origin_scope(principal: str | None) -> InvestigationOriginScope:
    if principal is None:
        return "unknown"
    if principal.startswith("system:benchmark"):
        return "benchmark"
    if principal.startswith("user:"):
        return "product"
    return "system"


def _finding_view(item: InvestigationStateItem) -> InvestigationFindingView:
    return InvestigationFindingView(
        proposition=item.proposition,
        target_ref=item.target_ref,
        evidence_refs=list(item.evidence_refs),
        updated_revision=item.updated_revision,
    )


def decision_view(
    payload: dict[str, JsonValue] | None,
    created_at: datetime,
) -> DecisionView | None:
    if payload is None:
        return None
    try:
        decision = DecisionResult.model_validate(payload)
    except ValueError:
        return None
    return DecisionView(
        decision_id=decision.decision_id,
        case_revision=decision.case_revision,
        conclusions=[
            DecisionConclusionView(
                statement=item.statement,
                type=item.type.value,
                evidence_refs=list(item.evidence_refs),
            )
            for item in decision.conclusions
        ],
        citations=[
            DecisionCitationView(
                conclusion_index=item.conclusion_index,
                evidence_ref=item.evidence_ref,
                source_ref=item.source_ref,
                locator=dict(item.locator),
            )
            for item in decision.citations
        ],
        conflicts=list(decision.conflicts),
        unknowns=list(decision.unknowns),
        assumptions=list(decision.assumptions),
        answer=dict(decision.answer_payload),
        stop_reason=decision.stop_reason,
        created_at=created_at,
    )


def _phase_from_task_status(status: str) -> str:
    return {
        "submitted": "accepted",
        "queued": "queued",
        "running": "investigating",
        "waiting_input": "waiting",
        "waiting_dependency": "waiting",
        "blocked": "blocked",
        "completed": "completed",
        "failed": "failed",
        "cancelled": "cancelled",
        "timed_out": "failed",
    }.get(status, "unknown")


def _effective_status(case_status: str, task_status: str) -> str:
    if case_status in {"cancelled", "closed", "resolved", "waiting"}:
        return case_status
    if task_status in {"submitted", "queued", "running"}:
        return "active"
    if task_status in {"waiting_input", "waiting_dependency"}:
        return "waiting"
    if task_status in {"failed", "timed_out", "blocked"}:
        return "failed"
    if task_status == "cancelled":
        return "cancelled"
    return case_status


def _encode_cursor(created_at: datetime, case_id: str) -> str:
    raw = json.dumps([created_at.isoformat(), case_id], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        created_at = datetime.fromisoformat(value[0])
        case_id = str(value[1])
    except (ValueError, TypeError, IndexError, json.JSONDecodeError) as exc:
        raise ValueError("invalid investigation cursor") from exc
    return created_at, case_id
