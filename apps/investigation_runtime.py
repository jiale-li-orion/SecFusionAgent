from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.investigation_delegation import (
    DelegatedEnrichmentPolicy,
    EnrichmentDelegationAdapter,
)
from apps.model_runtime import RuntimePromptAssemblyRecorder, create_recorded_model_provider
from packages.investigation.perception.runtime import PerceptionRuntime
from packages.investigation.runtime.contracts import InvestigationExecutionBoundary
from packages.investigation.runtime.planner import ModelInvestigationPlanner
from packages.investigation.runtime.role import InvestigationRoleRuntime
from packages.runtime.artifacts import RuntimeArtifactService
from packages.runtime.budget import BudgetGovernor
from packages.runtime.execution.service import ExecutionRunService
from packages.shared.config import Settings
from packages.task_runtime.context.materializer import ContextMaterializer
from packages.task_runtime.storage.service import get_task_run


class InvestigationRuntimeUnavailable(RuntimeError):
    pass


class RuntimeInvestigationExecutionBoundary(InvestigationExecutionBoundary):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        execution_service: ExecutionRunService,
    ) -> None:
        self._session_factory = session_factory
        self._execution = execution_service

    async def blocking_reason(self, task_run_id: str) -> str | None:
        async with self._session_factory() as session:
            run = await get_task_run(session, task_run_id)
            envelope = await self._execution.get(session, run.execution_envelope_ref)
        if datetime.now(UTC) >= envelope.deadline_at:
            return "deadline_reached"
        return None


def create_configured_investigation_runtime(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    client: httpx.AsyncClient,
    *,
    budget_governor: BudgetGovernor | None = None,
    execution_service: ExecutionRunService | None = None,
    artifact_service: RuntimeArtifactService | None = None,
) -> InvestigationRoleRuntime:
    if not settings.model_base_url or not settings.model_name:
        raise InvestigationRuntimeUnavailable(
            "InvestigationRole requires SECFUSION_MODEL_BASE_URL and SECFUSION_MODEL_NAME"
        )
    provider = create_recorded_model_provider(
        settings,
        session_factory,
        client,
        artifact_service=artifact_service,
    )
    if provider is None:
        raise InvestigationRuntimeUnavailable("configured model provider is unavailable")

    budget = budget_governor or BudgetGovernor()
    execution = execution_service or ExecutionRunService()
    planner = ModelInvestigationPlanner(
        session_factory,
        provider,
        materializer=ContextMaterializer(
            platform_invariant_revision="investigation-runtime-v1",
            platform_invariant={
                "fact_authority": "Evidence/Knowledge references only",
                "state_write": "StatePatch gate only",
                "external_execution": "Capability/Policy control plane only",
                "ephemeral_observation_is_not_evidence": True,
            },
        ),
        prompt_assembly_recorder=RuntimePromptAssemblyRecorder(),
        stream_name=settings.task_event_stream_name,
    )
    delegation = EnrichmentDelegationAdapter(
        session_factory,
        policy=DelegatedEnrichmentPolicy(
            budget_quantities={
                "agent_turns": Decimal("1"),
                "tool_calls": Decimal("4"),
            },
            capability_scope=[],
            identity_scope=[],
        ),
        budget_governor=budget,
        execution_service=execution,
        stream_name=settings.task_event_stream_name,
    )
    return InvestigationRoleRuntime(
        session_factory,
        planner,
        perception_runtime=PerceptionRuntime(),
        delegation_port=delegation,
        execution_boundary=RuntimeInvestigationExecutionBoundary(session_factory, execution),
        stream_name=settings.task_event_stream_name,
    )
