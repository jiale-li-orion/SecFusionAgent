from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.investigation_capabilities import CapabilityPlannerContextProvider
from apps.investigation_delegation import (
    DelegatedEnrichmentPolicy,
    EnrichmentDelegationAdapter,
)
from apps.model_runtime import RuntimePromptAssemblyRecorder, create_recorded_model_provider
from apps.nvd_observation import NVDObservationPort, nvd_capability_registry
from packages.investigation.perception.runtime import PerceptionRuntime
from packages.investigation.runtime.contracts import InvestigationExecutionBoundary
from packages.investigation.runtime.planner import ModelInvestigationPlanner
from packages.investigation.runtime.role import InvestigationRoleRuntime
from packages.runtime.artifacts import RuntimeArtifactService
from packages.runtime.budget import BudgetGovernor
from packages.runtime.execution.service import ExecutionRunService
from packages.runtime.policy.loader import load_runtime_policy
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
    if artifact_service is None:
        raise InvestigationRuntimeUnavailable("InvestigationRole requires runtime artifact storage")
    registry = nvd_capability_registry()
    policy = load_runtime_policy(settings.runtime_policy_path)
    planner = ModelInvestigationPlanner(
        session_factory,
        provider,
        materializer=ContextMaterializer(
            platform_invariant_revision="investigation-runtime-v2",
            platform_invariant={
                "fact_authority": "Evidence/Knowledge references only",
                "state_write": "StatePatch gate only",
                "external_execution": "Capability/Policy control plane only",
                "ephemeral_observation_is_not_evidence": True,
                "state_patch_rules": (
                    "A confirmed StatePatch with an inferred reasoning_relation is rejected. "
                    "Use confirmed only for propositions directly supported by durable evidence. "
                    "For an inference, use tentative or hypothesis and do not resolve an "
                    "EvidenceNeed that requires confirmed state. If a StatePatch is rejected, "
                    "inspect the rejection "
                    "feedback and submit a corrected action; never repeat the same invalid patch."
                ),
                "enrichment_delegation": (
                    "EnrichmentRole v1 only accepts a Vulnerability with its actual CVE. "
                    "Document, ResearchWork, Repo and InternetAsset investigations use "
                    "local perception (inspect, search, trace) and StatePatch. "
                    "Read source material using perception before drawing conclusions; "
                    "inspect with target.object_id reads current document chunks. "
                    "Use returned durable evidence_ref values as evidence_refs in StatePatch; "
                    "document-chunk references locate text and cannot replace EvidenceLink refs. "
                    "do not repeat an identical perception when its source text is available. "
                    "never invent a CVE to delegate a non-vulnerability object."
                ),
                "official_external_observation": (
                    "For an existing Vulnerability with an actual CVE, observe_external with "
                    "target.object_id reads the latest official NVD record. The returned "
                    "observation is untrusted until the runtime promotes it to a durable "
                    "Evidence reference. Use the promoted evidence_ref for confirmed StatePatch. "
                    "Do not use this operation for non-CVE objects or an arbitrary URL."
                ),
            },
        ),
        capability_context_provider=CapabilityPlannerContextProvider(
            session_factory,
            registry,
            policy,
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
        perception_runtime=PerceptionRuntime(
            NVDObservationPort(
                settings,
                session_factory,
                client,
                artifact_service,
                registry,
                policy,
                budget,
            )
        ),
        delegation_port=delegation,
        execution_boundary=RuntimeInvestigationExecutionBoundary(session_factory, execution),
        stream_name=settings.task_event_stream_name,
    )
