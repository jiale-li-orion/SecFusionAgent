from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.investigation.state.contracts import CaseLifecycle
from packages.investigation.state.service import InvestigationStateService
from packages.investigation.state.world_change import WorldChangeImpact
from packages.investigation.storage.models import InvestigationCaseModel
from packages.task_runtime.contracts.models import (
    TERMINAL_TASK_RUN_STATUSES,
    ContextManifest,
    TaskContract,
    TaskKind,
    TaskRunStatus,
)
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.models import (
    ContextManifestVersionModel,
    TaskContractVersionModel,
    TaskRunModel,
)
from packages.task_runtime.storage.service import create_task_run, transition_task_run


class WatchWakeDisposition(StrEnum):
    QUEUED = "queued"
    REPLAY = "replay"
    NOT_ACTIVATED = "not_activated"
    NO_WATCH_TEMPLATE = "no_watch_template"
    TEMPLATE_NOT_TERMINAL = "template_not_terminal"
    TEMPLATE_NOT_WAITING = "template_not_waiting"


class WatchWakeResult(BaseModel):
    case_id: str
    trigger_ref: str
    disposition: WatchWakeDisposition
    run_id: str | None = None


class WatchWakeService:
    """Create one fresh Investigation TaskRun for a relevant WATCH wake."""

    def __init__(
        self,
        *,
        state_service: InvestigationStateService | None = None,
        stream_name: str = "secfusion:task-events",
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._state_service = state_service or InvestigationStateService()
        self._stream_name = stream_name
        self._now = now or (lambda: datetime.now(UTC))

    async def spawn_for_world_change(
        self,
        session: AsyncSession,
        *,
        impact: WorldChangeImpact,
        trigger_ref: str,
    ) -> WatchWakeResult:
        if not impact.case_activated:
            return WatchWakeResult(
                case_id=impact.case_id,
                trigger_ref=trigger_ref,
                disposition=WatchWakeDisposition.NOT_ACTIVATED,
            )

        case = await session.get(InvestigationCaseModel, impact.case_id)
        if case is None:
            raise LookupError(f"investigation case not found: {impact.case_id}")
        if case.status != CaseLifecycle.ACTIVE.value:
            return WatchWakeResult(
                case_id=impact.case_id,
                trigger_ref=trigger_ref,
                disposition=WatchWakeDisposition.NOT_ACTIVATED,
            )

        template = await session.scalar(
            select(TaskRunModel)
            .join(
                TaskContractVersionModel,
                TaskContractVersionModel.task_contract_version_id
                == TaskRunModel.task_contract_version_id,
            )
            .where(
                TaskRunModel.case_id == impact.case_id,
                TaskContractVersionModel.task_kind == TaskKind.WATCH_INCIDENT.value,
            )
            .order_by(TaskRunModel.created_at.desc(), TaskRunModel.run_id.desc())
            .limit(1)
        )
        if template is None:
            return WatchWakeResult(
                case_id=impact.case_id,
                trigger_ref=trigger_ref,
                disposition=WatchWakeDisposition.NO_WATCH_TEMPLATE,
            )
        template_status = TaskRunStatus(template.status)
        if template_status not in TERMINAL_TASK_RUN_STATUSES:
            return WatchWakeResult(
                case_id=impact.case_id,
                trigger_ref=trigger_ref,
                disposition=WatchWakeDisposition.TEMPLATE_NOT_TERMINAL,
                run_id=template.run_id,
            )
        if template.stop_reason != "waiting_for_world_update":
            return WatchWakeResult(
                case_id=impact.case_id,
                trigger_ref=trigger_ref,
                disposition=WatchWakeDisposition.TEMPLATE_NOT_WAITING,
                run_id=template.run_id,
            )

        run_id = _watch_wake_run_id(impact.case_id, trigger_ref)
        if await session.get(TaskRunModel, run_id) is not None:
            return WatchWakeResult(
                case_id=impact.case_id,
                trigger_ref=trigger_ref,
                disposition=WatchWakeDisposition.REPLAY,
                run_id=run_id,
            )

        contract_model = await session.get(
            TaskContractVersionModel,
            template.task_contract_version_id,
        )
        context_model = await session.get(
            ContextManifestVersionModel,
            template.context_manifest_version_id,
        )
        if contract_model is None or context_model is None:
            raise RuntimeError("WATCH template references missing contract/context version")
        contract = TaskContract.model_validate(contract_model.contract_json)
        previous = ContextManifest.model_validate(context_model.manifest_json)
        state = await self._state_service.get_state(session, impact.case_id)
        manifest = ContextManifest(
            context_id=f"context:watch-wake:{run_id}",
            context_revision=1,
            parent_context_id=previous.context_id,
            task_contract_ref=previous.task_contract_ref,
            role_ref=previous.role_ref,
            case_ref=previous.case_ref,
            knowledge_revision=impact.world_revision,
            investigation_state_ref=f"case:{impact.case_id}@{state.case_revision}",
            enrichment_state_refs=[],
            evidence_refs=list(previous.evidence_refs),
            object_refs=list(previous.object_refs),
            relation_refs=list(previous.relation_refs),
            trajectory_checkpoint_ref=previous.trajectory_checkpoint_ref,
            skill_selection_refs=[],
            experience_pattern_refs=[],
            policy_context_ref=previous.policy_context_ref,
            capability_envelope_ref=f"capability:watch:{run_id}",
            budget_ref=f"budget:{run_id}",
            cache_hint=None,
        )
        await create_task_run(
            session,
            contract=contract,
            manifest=manifest,
            role=canonical_roles()["InvestigationRole"],
            execution_envelope_ref=f"execution:{run_id}",
            stream_name=self._stream_name,
            case_id=impact.case_id,
            run_id=run_id,
            producer="watch-wake-runtime",
            now=self._now(),
        )
        await transition_task_run(
            session,
            run_id=run_id,
            target=TaskRunStatus.QUEUED,
            payload_ref=f"watch-wake:{trigger_ref}",
            idempotency_key=f"watch-wake-queued:{trigger_ref}",
            stream_name=self._stream_name,
            producer="watch-wake-runtime",
            now=self._now(),
        )
        return WatchWakeResult(
            case_id=impact.case_id,
            trigger_ref=trigger_ref,
            disposition=WatchWakeDisposition.QUEUED,
            run_id=run_id,
        )


def _watch_wake_run_id(case_id: str, trigger_ref: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"secfusion:watch-wake:{case_id}:{trigger_ref}"))
