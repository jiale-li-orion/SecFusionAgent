from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from fakeredis.aioredis import FakeRedis
from pydantic import BaseModel, JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.evaluation_runtime import ensure_benchmark_deployment_revision
from apps.investigation_capabilities import CapabilityPlannerContextProvider
from apps.investigation_delegation import (
    DelegatedEnrichmentPolicy,
    EnrichmentDelegationAdapter,
)
from apps.observation_promotion import ObservationPromotionService
from apps.perception_execution import BrokeredPhysicalObservationPort
from apps.perception_routes import ExternalObservationRoute, StaticPerceptionExecutionResolver
from apps.runtime_models import register_runtime_models
from packages.enrichment.runtime.executor import EnrichmentOperatorExecution
from packages.enrichment.runtime.role import EnrichmentRoleRuntime
from packages.enrichment.runtime.state import (
    EnrichmentAttemptStatus,
    EnrichmentSemanticOutcome,
)
from packages.evaluation.benchmark import (
    BenchmarkCase,
    BenchmarkCaseRunStatus,
    BenchmarkDomain,
    BenchmarkExecutionMode,
    BenchmarkRunStatus,
    BenchmarkStore,
    BenchmarkSuite,
    MeasurementSource,
    metric_definition,
)
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.knowledge.contracts import (
    EnrichmentCandidate,
    ObjectCandidate,
    RelationCandidate,
)
from packages.intelligence.knowledge.vocabulary import EnrichmentDimension
from packages.intelligence.knowledge.write import EvidenceBackedKnowledgeWriter
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import (
    EvidenceLinkModel,
    ExternalIdentifierModel,
    KnowledgeRevisionModel,
    ObjectModel,
    RelationModel,
)
from packages.investigation.cases.service import CaseService
from packages.investigation.perception.contracts import (
    EvidenceRequirement,
    EvidenceTarget,
    PerceptionOperation,
    PerceptionRequest,
    PerceptionStepResult,
    PerceptionTarget,
)
from packages.investigation.perception.runtime import PerceptionRuntime
from packages.investigation.runtime.contracts import (
    DelegationAction,
    EnrichmentDelegationRequest,
    InvestigationPlannerDecision,
    PerceptionAction,
    StatePatchAction,
    StopAction,
)
from packages.investigation.runtime.planner import ModelInvestigationPlanner
from packages.investigation.runtime.role import InvestigationRoleRuntime
from packages.investigation.runtime.tasks import build_investigation_contract
from packages.investigation.skills.contracts import SkillStatus
from packages.investigation.skills.seeds import seeded_skills
from packages.investigation.skills.service import SkillStore
from packages.investigation.state.contracts import (
    EvidenceNeedContract,
    ProposedState,
    StatePatch,
    StatePatchOperation,
)
from packages.investigation.state.service import InvestigationStateService
from packages.investigation.storage.models import PerceptionEventModel
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.runtime.artifacts import MemoryRuntimeBlobStore, RuntimeArtifactService
from packages.runtime.budget import BudgetGovernor, BudgetLimits
from packages.runtime.capability.broker import (
    CapabilityBroker,
    InvocationGrants,
    NativeExecutionResult,
)
from packages.runtime.capability.contracts import (
    CapabilityBinding,
    CapabilityContract,
    CapabilityDescriptor,
    CapabilityRequest,
    CapabilityResultStatus,
    EffectSemantics,
    ExecutionClass,
    ImplementationKind,
    ToolImplementation,
    canonical_arguments_digest,
    native_schema_hash,
)
from packages.runtime.capability.registry import CapabilityRegistry
from packages.runtime.execution.service import ExecutionRunService
from packages.runtime.policy.contracts import Authorization, PolicyDecisionPoint
from packages.runtime.policy.engine import RuntimePolicyRule, StaticPolicyEngine
from packages.runtime.sandbox.broker import SandboxBroker
from packages.runtime.storage.models import BudgetAccountModel, CapabilityInvocationModel
from packages.shared.config import get_settings
from packages.shared.db import Base, create_engine, create_session_factory
from packages.shared.model_provider import StructuredModelRequest
from packages.sources.contracts import (
    AcquisitionTrigger,
    IngestEnvelope,
    RetentionMode,
    SourceDefinition,
    SourceRole,
)
from packages.sources.registry.service import sync_source_definitions
from packages.task_runtime.context.materializer import ContextMaterializer
from packages.task_runtime.contracts.execution import ExecutionEnvelope
from packages.task_runtime.contracts.models import (
    ContextManifest,
    ExecutionProfile,
    TaskKind,
    TaskRunStatus,
)
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.events.redis_stream import (
    ack_task_event_message,
    dispatch_pending_task_events,
    read_task_event_messages,
)
from packages.task_runtime.scheduler import (
    DependencyWakeDisposition,
    DependencyWakeScheduler,
    QueuedRoleExecutor,
    RoleDispatchDisposition,
)
from packages.task_runtime.storage.models import TaskRunModel
from packages.task_runtime.storage.service import (
    create_task_run,
    get_task_context,
    get_task_contract_for_run,
    get_task_event,
    get_task_run,
    list_task_events,
)

SUITE_ID = "m5-agent-runtime-controlled-v1"
EVALUATOR_REVISION = "agent-runtime-controlled-v1"
STREAM = "secfusion:task-events:agent-runtime-controlled"
SOURCE = SourceDefinition(
    source_id="fixture-primary-release-agent-benchmark",
    adapter_type="fixture",
    source_class="development_platform",
    authority_scope=["release_state", "fix_status"],
    source_role=SourceRole.PRIMARY,
    source_family="fixture-primary-release-agent-benchmark",
    access_mode="api",
    update_semantics="mutable",
    retention_mode=RetentionMode.TIME_BOUNDED,
)
SECONDARY_SOURCE = SourceDefinition(
    source_id="fixture-secondary-release-agent-benchmark",
    adapter_type="fixture",
    source_class="independent_research",
    authority_scope=["release_state", "fix_status"],
    source_role=SourceRole.REFERENCE,
    source_family="fixture-secondary-release-agent-benchmark",
    access_mode="api",
    update_semantics="mutable",
    retention_mode=RetentionMode.TIME_BOUNDED,
)


class ControlledProbeResult(BaseModel):
    case_id: str
    metrics: dict[str, float]
    diagnostics: dict[str, JsonValue]


class _VerifyFixBoundaryModel:
    name = "agent-runtime-controlled-planner"
    version = "v1"

    def __init__(self, *, object_id: str, need_id: str) -> None:
        self._object_id = object_id
        self._need_id = need_id
        self.requests: list[StructuredModelRequest] = []

    async def generate_structured(self, request, response_model):
        assert response_model is InvestigationPlannerDecision
        self.requests.append(request)
        if len(self.requests) == 1:
            return InvestigationPlannerDecision(
                action=PerceptionAction(
                    request=PerceptionRequest(
                        request_id="model-owned-placeholder",
                        operation=PerceptionOperation.OBSERVE_EXTERNAL,
                        target=PerceptionTarget(
                            object_id=self._object_id,
                            query_text="v1.2.3",
                            source_ids=[SOURCE.source_id],
                            verification_intent="verify first release containing fix commit",
                        ),
                        desired_observation="primary release containment evidence",
                        evidence_requirement=EvidenceRequirement(
                            required_source_roles=["primary"],
                            min_independent_sources=1,
                        ),
                    )
                )
            )
        evidence_ref = _first_evidence_handle(request.data)
        return InvestigationPlannerDecision(
            action=StatePatchAction(
                patch=StatePatch(
                    patch_id="model-owned-placeholder",
                    case_id="model-owned-placeholder",
                    base_case_revision=0,
                    producer="model-owned-placeholder",
                    operations=[
                        StatePatchOperation(
                            proposition="Release v1.2.3 contains the fix commit.",
                            target_ref=f"object:{self._object_id}",
                            proposed_state=ProposedState.CONFIRMED,
                            evidence_refs=[evidence_ref],
                            resolves_need_id=self._need_id,
                        )
                    ],
                )
            )
        )


class _FallbackBindingExecutor:
    def __init__(self, *, expected_tool_impl_id: str) -> None:
        self._expected_tool_impl_id = expected_tool_impl_id
        self.calls: list[str] = []

    async def execute(self, implementation, *, native_arguments, timeout_seconds):
        del timeout_seconds
        self.calls.append(implementation.tool_impl_id)
        if implementation.tool_impl_id != self._expected_tool_impl_id:
            raise AssertionError(
                f"unexpected fallback implementation: {implementation.tool_impl_id}"
            )
        if native_arguments != {"tag": "v1.2.3"}:
            raise AssertionError(f"unexpected fallback arguments: {native_arguments}")
        return NativeExecutionResult(
            status=CapabilityResultStatus.SUCCEEDED,
            raw_artifact_ref="artifact:controlled-fallback-success",
            consumed_budget={"tool_calls": Decimal("1")},
            extracted_candidates=[{"statement": "fallback binding succeeded"}],
            provenance={"fallback_binding": True},
        )


class _PrimaryReleaseExecutor:
    def __init__(self, *, artifact_ref: str, acquisition_run_id: str) -> None:
        self._artifact_ref = artifact_ref
        self._acquisition_run_id = acquisition_run_id
        self.calls = 0

    async def execute(self, implementation, *, native_arguments, timeout_seconds):
        del implementation, timeout_seconds
        self.calls += 1
        if native_arguments != {"tag": "v1.2.3"}:
            raise AssertionError(f"unexpected native capability arguments: {native_arguments}")
        return NativeExecutionResult(
            status=CapabilityResultStatus.SUCCEEDED,
            raw_artifact_ref=self._artifact_ref,
            consumed_budget={"tool_calls": Decimal("1")},
            extracted_candidates=[{"statement": "Primary release v1.2.3 contains the fix commit."}],
            provenance={
                "acquisition_run_id": self._acquisition_run_id,
                "external_object_id": "release:v1.2.3",
                "external_revision": "v1.2.3",
                "canonical_url": "https://example.invalid/releases/v1.2.3",
                "published_at": _now().isoformat(),
                "updated_at": _now().isoformat(),
            },
        )


class _DelegatedFixBoundaryModel:
    name = "agent-runtime-controlled-delegation-planner"
    version = "v1"

    def __init__(self, *, object_id: str, need_id: str, cve_id: str) -> None:
        self._object_id = object_id
        self._need_id = need_id
        self._cve_id = cve_id
        self.requests: list[StructuredModelRequest] = []

    async def generate_structured(self, request, response_model):
        assert response_model is InvestigationPlannerDecision
        self.requests.append(request)
        if len(self.requests) == 1:
            return InvestigationPlannerDecision(
                action=DelegationAction(
                    request=EnrichmentDelegationRequest(
                        delegation_id="model-owned-placeholder",
                        target_object_id=self._object_id,
                        cve_id=self._cve_id,
                        required_dimensions=[EnrichmentDimension.FIX_REMEDIATION],
                        reason="missing durable fix boundary evidence",
                    )
                )
            )
        if len(self.requests) == 2:
            relation_id = _first_relation_id(request.data, relation_type="fixed-version")
            return InvestigationPlannerDecision(
                action=PerceptionAction(
                    request=PerceptionRequest(
                        request_id="model-owned-placeholder",
                        operation=PerceptionOperation.INSPECT,
                        target=PerceptionTarget(
                            evidence_targets=[
                                EvidenceTarget(
                                    target_kind="relation",
                                    target_id=relation_id,
                                )
                            ]
                        ),
                        evidence_requirement=EvidenceRequirement(
                            required_source_roles=["primary"],
                            min_independent_sources=1,
                        ),
                    )
                )
            )
        evidence_ref = _first_evidence_handle(request.data)
        return InvestigationPlannerDecision(
            action=StatePatchAction(
                patch=StatePatch(
                    patch_id="model-owned-placeholder",
                    case_id="model-owned-placeholder",
                    base_case_revision=0,
                    producer="model-owned-placeholder",
                    operations=[
                        StatePatchOperation(
                            proposition=(
                                "Primary enrichment evidence establishes fixed version v1.2.3."
                            ),
                            target_ref=f"object:{self._object_id}",
                            proposed_state=ProposedState.CONFIRMED,
                            evidence_refs=[evidence_ref],
                            resolves_need_id=self._need_id,
                        )
                    ],
                )
            )
        )


class _DurableFixEnrichmentExecutor:
    def __init__(self, *, factory, object_id: str, now: datetime) -> None:
        self._factory = factory
        self._object_id = object_id
        self._now = now
        self._ingress = EvidenceIngress(MemoryArtifactStore(), now=lambda: now)
        self._writer = EvidenceBackedKnowledgeWriter(now=lambda: now)
        self._acquisition_run_id = str(uuid4())
        self._wrote = False
        self.calls: list[str] = []

    async def execute(self, plan, *, cve_id: str, parent_run_id: str):
        self.calls.append(plan.operator_id)
        if self._wrote:
            return EnrichmentOperatorExecution(
                operator_id=plan.operator_id,
                status=EnrichmentAttemptStatus.SUCCEEDED,
                semantic_outcomes={
                    EnrichmentDimension.FIX_REMEDIATION: EnrichmentSemanticOutcome.NO_CHANGE
                },
            )
        async with self._factory() as session, session.begin():
            session.add(
                AcquisitionRunModel(
                    run_id=self._acquisition_run_id,
                    source_id=SOURCE.source_id,
                    trigger="investigation",
                    parent_run_id=parent_run_id,
                    query_spec={"filters": {"cve_id": cve_id}},
                    status="success",
                    cursor_in={},
                    cursor_out={"result_count": 1},
                    attempt=1,
                    created_at=self._now,
                    started_at=self._now,
                    finished_at=self._now,
                )
            )
            envelope = IngestEnvelope.for_json_payload(
                acquisition_run_id=self._acquisition_run_id,
                trigger=AcquisitionTrigger.INVESTIGATION,
                source_id=SOURCE.source_id,
                external_object_id=f"{cve_id}:fixed-version",
                payload={"cve_id": cve_id, "fixed_version": "v1.2.3"},
                canonical_url="https://example.invalid/advisories/fixed-version",
                published_at=self._now,
                updated_at=self._now,
                external_revision="v1.2.3",
                observed_at=self._now,
            )
            observation = await self._ingress.accept(session, SOURCE, envelope)
            result = await self._writer.apply(
                session,
                root_object_id=self._object_id,
                source=SOURCE,
                observation=observation,
                candidate=EnrichmentCandidate(
                    relations=[
                        RelationCandidate(
                            relation_type="fixed-version",
                            target=ObjectCandidate(
                                object_type="SoftwareVersion",
                                canonical_key="software-version:fixture/project:v1.2.3",
                                properties={"display_name": "v1.2.3"},
                            ),
                            qualifier={"release": "v1.2.3"},
                            locator={"kind": "fixture", "field": "fixed_version"},
                        )
                    ],
                    replace_relation_types=["fixed-version"],
                ),
                processor_name="agent-runtime-controlled-delegation",
                processor_version="1",
            )
            evidence_links = list(
                await session.scalars(
                    select(EvidenceLinkModel).where(
                        EvidenceLinkModel.target_kind == "relation",
                        EvidenceLinkModel.target_id.in_(result.relation_ids),
                    )
                )
            )
        self._wrote = True
        return EnrichmentOperatorExecution(
            operator_id=plan.operator_id,
            status=EnrichmentAttemptStatus.SUCCEEDED,
            semantic_outcomes={
                EnrichmentDimension.FIX_REMEDIATION: EnrichmentSemanticOutcome.RESOLVED
            },
            evidence_refs=[item.evidence_link_id for item in evidence_links],
            output_refs=[f"knowledge-revision:{result.knowledge_revision}"],
        )


class _UnusedSandboxBackend:
    backend_id = "openshell"

    async def create(self, lease):
        raise AssertionError(f"controlled external observation should not create sandbox: {lease}")

    async def exec(self, backend_handle_ref, request, *, timeout_seconds):
        raise AssertionError(
            f"controlled external observation should not exec sandbox: "
            f"{backend_handle_ref} {request} {timeout_seconds}"
        )

    async def export(self, backend_handle_ref, relative_paths):
        raise AssertionError(
            f"controlled external observation should not export sandbox: "
            f"{backend_handle_ref} {relative_paths}"
        )

    async def destroy(self, backend_handle_ref):
        raise AssertionError(
            f"controlled external observation should not destroy sandbox: {backend_handle_ref}"
        )


class _NoSignalPlanner:
    def __init__(self) -> None:
        self.calls = 0

    async def next_action(self, frame):
        self.calls += 1
        return PerceptionAction(
            request=PerceptionRequest(
                request_id="controlled-no-signal",
                operation=PerceptionOperation.OBSERVE_EXTERNAL,
                target=PerceptionTarget(
                    query_text="controlled-no-new-signal",
                    source_ids=[SOURCE.source_id],
                ),
                evidence_requirement=EvidenceRequirement(
                    required_source_roles=["primary"],
                    min_independent_sources=1,
                ),
            )
        )


class _DeadlineSentinelPlanner:
    def __init__(self) -> None:
        self.calls = 0

    async def next_action(self, frame):
        self.calls += 1
        return StopAction(reason="planner_should_not_run_after_deadline")


class _DeadlineBoundary:
    async def blocking_reason(self, task_run_id: str) -> str | None:
        del task_run_id
        return "deadline_reached"


class _ControlledFailurePlanner:
    def __init__(self) -> None:
        self.calls = 0

    async def next_action(self, frame):
        del frame
        self.calls += 1
        raise RuntimeError("controlled_recoverable_planner_failure")


class _ControlledRecoveryPlanner:
    def __init__(self, *, object_id: str, need_id: str) -> None:
        self._object_id = object_id
        self._need_id = need_id
        self.calls = 0

    async def next_action(self, frame):
        self.calls += 1
        return StatePatchAction(
            patch=StatePatch(
                patch_id=str(uuid4()),
                case_id=frame.state.case_id,
                base_case_revision=frame.state.case_revision,
                producer="InvestigationRole@controlled-recovery",
                operations=[
                    StatePatchOperation(
                        proposition="Controlled recovery resolved the durable evidence gap.",
                        target_ref=f"object:{self._object_id}",
                        proposed_state=ProposedState.UNKNOWN,
                        resolves_need_id=self._need_id,
                    )
                ],
            )
        )


class _NoSignalPhysicalObservationPort:
    async def execute(self, *, task_run_id, request, step):
        del task_run_id, request, step
        return PerceptionStepResult(unresolved=["controlled_no_new_signal"])


def _now() -> datetime:
    return datetime(2026, 10, 3, 0, 0, tzinfo=UTC)


def _first_evidence_handle(value: JsonValue) -> str:
    if isinstance(value, dict):
        handles = value.get("evidence_handles")
        if isinstance(handles, list):
            for item in handles:
                if isinstance(item, str) and item:
                    return item
        for item in value.values():
            try:
                return _first_evidence_handle(item)
            except LookupError:
                pass
    elif isinstance(value, list):
        for item in value:
            try:
                return _first_evidence_handle(item)
            except LookupError:
                pass
    raise LookupError("controlled planner second turn did not receive durable EvidenceRef")


def _first_relation_id(value: JsonValue, *, relation_type: str) -> str:
    if isinstance(value, dict):
        if value.get("relation_type") == relation_type:
            relation_id = value.get("relation_id")
            if isinstance(relation_id, str) and relation_id:
                return relation_id
        for item in value.values():
            try:
                return _first_relation_id(item, relation_type=relation_type)
            except LookupError:
                pass
    elif isinstance(value, list):
        for item in value:
            try:
                return _first_relation_id(item, relation_type=relation_type)
            except LookupError:
                pass
    raise LookupError(f"controlled planner did not receive relation_type={relation_type}")


async def _seed_basic_role_run(
    factory,
    *,
    now: datetime,
    deadline_at: datetime,
    signature: str,
    capability_scope: list[str] | None = None,
    evidence_contract: EvidenceNeedContract | None = None,
) -> tuple[str, str, str, str]:
    state_service = InvestigationStateService(now=lambda: now)
    async with factory() as session, session.begin():
        revision = KnowledgeRevisionModel(committed_at=now)
        session.add(revision)
        await session.flush()
        object_id = str(uuid4())
        session.add(
            ObjectModel(
                object_id=object_id,
                object_type="Vulnerability",
                canonical_key=f"cve:{signature}",
                properties={"display_name": signature},
                created_revision=revision.revision,
            )
        )
        await session.flush()
        case = await CaseService(now=lambda: now).create(
            session,
            task_signature=signature,
            target_object_ids=[object_id],
            goal="Resolve the controlled EvidenceNeed within bounded runtime policy.",
            initial_knowledge_revision=revision.revision,
        )
        need = await state_service.open_evidence_need(
            session,
            case_id=case.case_id,
            base_case_revision=0,
            need_id=str(uuid4()),
            proposition_or_question="Can the controlled evidence gap be resolved?",
            purpose="controlled_stop_probe",
            target_objects=[object_id],
            evidence_contract=evidence_contract
            or EvidenceNeedContract(
                required_source_roles=["primary"],
                min_independent_sources=1,
            ),
            writer="benchmark:agent-runtime-controlled",
            reason_code="controlled_stop_seed",
        )
        run_id = str(uuid4())
        budget_id = f"budget:{run_id}"
        execution_id = f"execution:{run_id}"
        contract = build_investigation_contract(
            task_contract_id=f"verify:{run_id}",
            principal="benchmark:agent-runtime",
            task_kind=TaskKind.VERIFY_VERSION_FIX,
            case_id=case.case_id,
            target_object_ids=[object_id],
            required_need_ids=[need.need.need_id],
            policy_revision="policy-v1",
        )
        await create_task_run(
            session,
            contract=contract,
            manifest=ContextManifest(
                context_id=f"context:{run_id}",
                context_revision=1,
                task_contract_ref=f"{contract.task_contract_id}@1",
                role_ref="InvestigationRole@1",
                case_ref=case.case_id,
                knowledge_revision=revision.revision,
                investigation_state_ref=f"case:{case.case_id}@1",
                object_refs=[object_id],
                policy_context_ref="policy-context:v1",
                capability_envelope_ref="capability:controlled:none",
                budget_ref=budget_id,
            ),
            role=canonical_roles()["InvestigationRole"],
            execution_envelope_ref=execution_id,
            stream_name=STREAM,
            case_id=case.case_id,
            run_id=run_id,
            now=now,
        )
        await BudgetGovernor(now=lambda: now).create_account(
            session,
            account_id=budget_id,
            task_run_id=run_id,
            limits=BudgetLimits(
                quantities={"agent_turns": Decimal("4"), "tool_calls": Decimal("2")}
            ),
        )
        await ExecutionRunService(now=lambda: now).create(
            session,
            ExecutionEnvelope(
                execution_id=execution_id,
                task_contract_id=contract.task_contract_id,
                task_run_id=run_id,
                case_id=case.case_id,
                role_revision="InvestigationRole@1",
                context_manifest_revision=1,
                execution_profile=ExecutionProfile.VERIFY,
                capability_scope=list(capability_scope or []),
                deadline_at=deadline_at,
                budget_ref=budget_id,
                policy_revision="policy-v1",
                identity_scope=["public"],
                network_policy="proxied",
                side_effect_policy="internal-state",
                sandbox_profile_revision="process_restricted@1",
            ),
        )
        await ExecutionRunService(now=lambda: now).start(session, execution_id)
    return case.case_id, object_id, need.need.need_id, run_id


def _registry() -> CapabilityRegistry:
    input_schema: dict[str, JsonValue] = {
        "type": "object",
        "properties": {"tag": {"type": "string"}},
        "required": ["tag"],
    }
    output_schema: dict[str, JsonValue] = {"type": "object"}
    schema_hash = native_schema_hash(input_schema, output_schema)
    implementation = ToolImplementation(
        tool_impl_id="fixture-release-reader-agent-benchmark",
        implementation_revision=1,
        implementation_kind=ImplementationKind.PROVIDER_API,
        native_name="fixture.release.read",
        transport="fixture",
        native_input_schema=input_schema,
        native_output_schema=output_schema,
        health_ref="health:fixture-release-reader-agent-benchmark",
        native_schema_hash=schema_hash,
    )
    contract = CapabilityContract(
        capability_id="repo.read_release",
        contract_revision=1,
        action="read",
        applicable_resource_types=["repository.release"],
        canonical_input_schema=input_schema,
        canonical_output_schema=output_schema,
        observation_semantics="primary_release_observation",
        effect_semantics=EffectSemantics.OBSERVATION,
        authority_semantics=["primary_if_bound_source_is_primary"],
        idempotency="safe",
        reversibility="not_applicable",
        data_ingress_class="public",
        data_egress_class="none",
        risk_class="low",
    )
    binding = CapabilityBinding(
        binding_id="fixture-release-reader-binding-agent-benchmark",
        binding_revision=1,
        capability_id=contract.capability_id,
        contract_revision=1,
        tool_impl_id=implementation.tool_impl_id,
        implementation_revision=1,
        resource_resolver="identity",
        effect_resolver="contract",
        authority_mapper="fixture-primary-release",
        execution_class=ExecutionClass.PROXIED_PROVIDER_READ,
        credential_profile="none",
        network_profile="proxied",
        sandbox_profile="none",
        health_requirement="healthy",
        cost_class="low",
        latency_class="interactive",
        native_schema_hash=schema_hash,
    )
    return CapabilityRegistry(
        revision="registry-agent-runtime-controlled-v1",
        contracts=[contract],
        descriptors={
            contract.capability_id: CapabilityDescriptor(
                purpose="Read primary release state and fix-containment evidence"
            )
        },
        implementations=[implementation],
        bindings=[binding],
    )


def _fallback_registry() -> tuple[CapabilityRegistry, str, str]:
    input_schema: dict[str, JsonValue] = {
        "type": "object",
        "properties": {"tag": {"type": "string"}},
        "required": ["tag"],
    }
    output_schema: dict[str, JsonValue] = {"type": "object"}
    schema_hash = native_schema_hash(input_schema, output_schema)
    preferred_impl = ToolImplementation(
        tool_impl_id="fixture-release-reader-preferred",
        implementation_revision=1,
        implementation_kind=ImplementationKind.PROVIDER_API,
        native_name="fixture.release.preferred",
        transport="fixture",
        native_input_schema=input_schema,
        native_output_schema=output_schema,
        health_ref="health:fixture-preferred",
        native_schema_hash=schema_hash,
    )
    fallback_impl = ToolImplementation(
        tool_impl_id="fixture-release-reader-fallback",
        implementation_revision=1,
        implementation_kind=ImplementationKind.PROVIDER_API,
        native_name="fixture.release.fallback",
        transport="fixture",
        native_input_schema=input_schema,
        native_output_schema=output_schema,
        health_ref="health:fixture-fallback",
        native_schema_hash=schema_hash,
    )
    contract = CapabilityContract(
        capability_id="repo.read_release",
        contract_revision=1,
        action="read",
        applicable_resource_types=["repository.release"],
        canonical_input_schema=input_schema,
        canonical_output_schema=output_schema,
        observation_semantics="primary_release_observation",
        effect_semantics=EffectSemantics.OBSERVATION,
        authority_semantics=["primary_if_bound_source_is_primary"],
        idempotency="safe",
        reversibility="not_applicable",
        data_ingress_class="public",
        data_egress_class="none",
        risk_class="low",
    )
    preferred_binding = CapabilityBinding(
        binding_id="fixture-release-binding-preferred",
        binding_revision=1,
        capability_id=contract.capability_id,
        contract_revision=1,
        tool_impl_id=preferred_impl.tool_impl_id,
        implementation_revision=1,
        resource_resolver="identity",
        effect_resolver="contract",
        authority_mapper="fixture-primary-release",
        execution_class=ExecutionClass.PROXIED_PROVIDER_READ,
        credential_profile="none",
        network_profile="proxied",
        sandbox_profile="none",
        health_requirement="healthy",
        cost_class="low",
        latency_class="interactive",
        fallback_rank=1,
        native_schema_hash=schema_hash,
    )
    fallback_binding = CapabilityBinding(
        binding_id="fixture-release-binding-fallback",
        binding_revision=1,
        capability_id=contract.capability_id,
        contract_revision=1,
        tool_impl_id=fallback_impl.tool_impl_id,
        implementation_revision=1,
        resource_resolver="identity",
        effect_resolver="contract",
        authority_mapper="fixture-primary-release",
        execution_class=ExecutionClass.PROXIED_PROVIDER_READ,
        credential_profile="none",
        network_profile="proxied",
        sandbox_profile="none",
        health_requirement="healthy",
        cost_class="low",
        latency_class="interactive",
        fallback_rank=10,
        native_schema_hash=schema_hash,
    )
    registry = CapabilityRegistry(
        revision="registry-agent-runtime-fallback-v1",
        contracts=[contract],
        descriptors={
            contract.capability_id: CapabilityDescriptor(
                purpose="Read release metadata with health-aware fallback"
            )
        },
        implementations=[preferred_impl, fallback_impl],
        bindings=[preferred_binding, fallback_binding],
    )
    return registry, preferred_binding.binding_id, fallback_binding.binding_id


def _policy() -> StaticPolicyEngine:
    return StaticPolicyEngine(
        policy_revision="policy-v1",
        rules=[
            RuntimePolicyRule(
                policy_id="agent-benchmark-visible-release-read",
                policy_revision="policy-v1",
                decision_points=[PolicyDecisionPoint.CAPABILITY_VISIBILITY],
                principal_patterns=["benchmark:agent-runtime"],
                action_patterns=["read"],
                resource_patterns=["capability:repo.read_release"],
                authorization=Authorization.PERMIT,
            ),
            RuntimePolicyRule(
                policy_id="agent-benchmark-invoke-release-read",
                policy_revision="policy-v1",
                decision_points=[PolicyDecisionPoint.CAPABILITY_INVOCATION],
                principal_patterns=["benchmark:agent-runtime"],
                action_patterns=["read"],
                resource_patterns=["repo:fixture/project"],
                authorization=Authorization.PERMIT,
            ),
            RuntimePolicyRule(
                policy_id="agent-benchmark-promote-primary-observation",
                policy_revision="policy-v1",
                decision_points=[PolicyDecisionPoint.OBSERVATION_PROMOTION],
                principal_patterns=["benchmark:agent-runtime"],
                action_patterns=["promote_observation"],
                resource_patterns=[f"source:{SOURCE.source_id}"],
                authorization=Authorization.PERMIT,
            ),
        ],
    )


async def _probe_perception_capability() -> ControlledProbeResult:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = _now()
    state_service = InvestigationStateService(now=lambda: now)
    budget = BudgetGovernor(now=lambda: now)
    execution_service = ExecutionRunService(now=lambda: now)
    runtime_artifacts = RuntimeArtifactService(MemoryRuntimeBlobStore(), now=lambda: now)
    run_id = str(uuid4())
    execution_id = f"execution:{run_id}"
    budget_id = f"budget:{run_id}"
    acquisition_run_id = str(uuid4())
    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, [SOURCE])
            revision = KnowledgeRevisionModel(committed_at=now)
            session.add(revision)
            await session.flush()
            object_id = str(uuid4())
            session.add(
                ObjectModel(
                    object_id=object_id,
                    object_type="Vulnerability",
                    canonical_key="cve:CVE-2026-AGENT-CONTROLLED",
                    properties={"display_name": "CVE-2026-AGENT-CONTROLLED"},
                    created_revision=revision.revision,
                )
            )
            await session.flush()
            case = await CaseService(now=lambda: now).create(
                session,
                task_signature="agent-runtime-controlled-perception",
                target_object_ids=[object_id],
                goal="Verify the first release containing the fix commit.",
                initial_knowledge_revision=revision.revision,
            )
            need = await state_service.open_evidence_need(
                session,
                case_id=case.case_id,
                base_case_revision=0,
                need_id=str(uuid4()),
                proposition_or_question="Which release first contains the fix commit?",
                purpose="verify_fix_release",
                target_objects=[object_id],
                evidence_contract=EvidenceNeedContract(
                    required_source_roles=["primary"],
                    min_independent_sources=1,
                ),
                preferred_source_roles=["primary"],
                freshness_requirement={"max_age_seconds": 3600},
                writer="benchmark:agent-runtime-controlled",
                reason_code="controlled_gap_seed",
            )
            contract = build_investigation_contract(
                task_contract_id=f"verify:{run_id}",
                principal="benchmark:agent-runtime",
                task_kind=TaskKind.VERIFY_VERSION_FIX,
                case_id=case.case_id,
                target_object_ids=[object_id],
                required_need_ids=[need.need.need_id],
                policy_revision="policy-v1",
            )
            await create_task_run(
                session,
                contract=contract,
                manifest=ContextManifest(
                    context_id=f"context:{run_id}",
                    context_revision=1,
                    task_contract_ref=f"{contract.task_contract_id}@1",
                    role_ref="InvestigationRole@1",
                    case_ref=case.case_id,
                    knowledge_revision=revision.revision,
                    investigation_state_ref=f"case:{case.case_id}@1",
                    object_refs=[object_id],
                    policy_context_ref="policy-context:v1",
                    capability_envelope_ref="capability:verify:v1",
                    budget_ref=budget_id,
                ),
                role=canonical_roles()["InvestigationRole"],
                execution_envelope_ref=execution_id,
                stream_name=STREAM,
                case_id=case.case_id,
                run_id=run_id,
                now=now,
            )
            await budget.create_account(
                session,
                account_id=budget_id,
                task_run_id=run_id,
                limits=BudgetLimits(
                    quantities={"tool_calls": Decimal("2"), "agent_turns": Decimal("4")}
                ),
            )
            envelope = ExecutionEnvelope(
                execution_id=execution_id,
                task_contract_id=contract.task_contract_id,
                task_run_id=run_id,
                case_id=case.case_id,
                role_revision="InvestigationRole@1",
                context_manifest_revision=1,
                execution_profile=ExecutionProfile.VERIFY,
                capability_scope=["repo.read_release"],
                deadline_at=now + timedelta(minutes=5),
                budget_ref=budget_id,
                policy_revision="policy-v1",
                identity_scope=["public"],
                network_policy="proxied",
                side_effect_policy="read-only",
                sandbox_profile_revision="process_restricted@1",
            )
            await execution_service.create(session, envelope)
            await execution_service.start(session, execution_id)
            session.add(
                AcquisitionRunModel(
                    run_id=acquisition_run_id,
                    source_id=SOURCE.source_id,
                    trigger="investigation",
                    parent_run_id=None,
                    query_spec={"tag": "v1.2.3"},
                    status="success",
                    cursor_in={},
                    cursor_out={"result_count": 1},
                    attempt=1,
                    created_at=now,
                    started_at=now,
                    finished_at=now,
                )
            )
            artifact = await runtime_artifacts.write(
                session,
                execution_id=execution_id,
                producer_kind="capability",
                producer_ref="capability:repo.read_release",
                logical_name="release-v1.2.3.json",
                media_type="application/json",
                body=b'{"tag":"v1.2.3","contains_fix":true}',
            )
            seed = seeded_skills()[0]
            validated = seed.model_copy(
                update={
                    "manifest": seed.manifest.model_copy(
                        update={
                            "status": SkillStatus.VALIDATED,
                            "validation_ref": "benchmark:agent-runtime-controlled-v1",
                        }
                    )
                }
            )
            await SkillStore(now=lambda: now).publish(session, validated)

        registry = _registry()
        policy = _policy()
        executor = _PrimaryReleaseExecutor(
            artifact_ref=artifact.artifact_ref,
            acquisition_run_id=acquisition_run_id,
        )
        capability_broker = CapabilityBroker(registry, policy, budget, now=lambda: now)
        sandbox_broker = SandboxBroker(
            policy,
            {"openshell": _UnusedSandboxBackend()},
            available_backend_components={"openshell"},
            execution_service=execution_service,
            now=lambda: now,
        )
        resolver = StaticPerceptionExecutionResolver(
            factory,
            external_routes=[
                ExternalObservationRoute(
                    route_id="agent-benchmark-primary-release",
                    route_revision=1,
                    capability_requirement="external_observation",
                    capability_id="repo.read_release",
                    contract_revision=1,
                    action="read",
                    resource_type="repository.release",
                    resource="repo:fixture/project",
                    argument_map={"tag": "query_text"},
                    estimated_budget={"tool_calls": Decimal("1")},
                    healthy_refs={"health:fixture-release-reader-agent-benchmark"},
                    available_execution_classes={ExecutionClass.PROXIED_PROVIDER_READ},
                    promotion_source_id=SOURCE.source_id,
                    promotion_target_kind="object",
                    promote_request_target=True,
                )
            ],
        )
        promotion = ObservationPromotionService(
            factory,
            policy,
            runtime_artifacts,
            EvidenceIngress(MemoryArtifactStore(), now=lambda: now),
            {SOURCE.source_id: SOURCE},
        )
        physical_port = BrokeredPhysicalObservationPort(
            capability_broker=capability_broker,
            capability_executor=executor,
            sandbox_broker=sandbox_broker,
            resolver=resolver,
            session_factory=factory,
            promotion_port=promotion,
            execution_service=execution_service,
        )
        provider = _VerifyFixBoundaryModel(object_id=object_id, need_id=need.need.need_id)
        planner = ModelInvestigationPlanner(
            factory,
            provider,
            materializer=ContextMaterializer(
                platform_invariant_revision="platform-v1",
                platform_invariant={
                    "state_write": "StatePatch gate",
                    "tool_execution": "Capability/Sandbox broker",
                    "ephemeral_observation_is_not_evidence": True,
                },
            ),
            capability_context_provider=CapabilityPlannerContextProvider(
                factory,
                registry,
                policy,
                semantic_class_map={
                    "repo.read_release": ["evidence.read", "graph.read"]
                },
                healthy_refs={"health:fixture-release-reader-agent-benchmark"},
                available_execution_classes={ExecutionClass.PROXIED_PROVIDER_READ},
                execution_service=execution_service,
            ),
            stream_name=STREAM,
        )
        outcome = await InvestigationRoleRuntime(
            factory,
            planner,
            state_service=state_service,
            perception_runtime=PerceptionRuntime(physical_port),
            stream_name=STREAM,
            now=lambda: now,
        ).run(run_id)

        async with factory() as session:
            run = await session.get(TaskRunModel, run_id)
            state = await state_service.get_state(session, case.case_id)
            events = await list_task_events(session, run_id)
            context = await get_task_context(session, run_id)
            invocations = list(
                await session.scalars(
                    select(CapabilityInvocationModel).where(
                        CapabilityInvocationModel.task_run_id == run_id
                    )
                )
            )
            perceptions = list(
                await session.scalars(
                    select(PerceptionEventModel).where(
                        PerceptionEventModel.task_run_id == run_id
                    )
                )
            )
            evidence_links = list(
                await session.scalars(
                    select(EvidenceLinkModel).where(EvidenceLinkModel.target_id == object_id)
                )
            )
            observations = list(
                await session.scalars(
                    select(ObservationModel).where(ObservationModel.source_id == SOURCE.source_id)
                )
            )

        if run is None or run.status != "completed":
            raise RuntimeError(f"controlled InvestigationRole did not complete: {run}")
        if outcome.result.resolved_need_ids != [need.need.need_id]:
            raise RuntimeError("controlled EvidenceNeed was not resolved")
        if len(invocations) != 1 or len(perceptions) != 1:
            raise RuntimeError(
                "controlled acquisition expected one capability/perception invocation"
            )
        if len(evidence_links) != 1 or len(observations) != 1:
            raise RuntimeError("controlled acquisition did not promote one durable Evidence chain")

        invocation = invocations[0]
        perception = perceptions[0]
        observation = observations[0]
        expected_arguments: dict[str, JsonValue] = {"tag": "v1.2.3"}
        request_json = cast(dict[str, JsonValue], invocation.request_json)
        observed_arguments = request_json.get("canonical_arguments")
        argument_correct = observed_arguments == expected_arguments
        capability_correct = invocation.capability_id == "repo.read_release"
        source_role_satisfied = SOURCE.source_role is SourceRole.PRIMARY
        fresh = (perception.finished_at - observation.observed_at).total_seconds() <= 3600
        useful = bool(
            state.confirmed
            and evidence_links[0].evidence_link_id in set(state.confirmed[0].evidence_refs)
        )
        metrics = {
            "agent.useful_acquisition_precision": float(useful),
            "agent.redundant_acquisition_rate": 0.0,
            "agent.source_role_satisfaction": float(source_role_satisfied),
            "agent.freshness_satisfaction": float(fresh),
            "agent.capability_selection_correctness": float(capability_correct),
            "agent.argument_correctness": float(argument_correct),
            "agent.unnecessary_denied_request_rate": 0.0,
            "agent.capability_invocation_count": float(len(invocations)),
        }
        return ControlledProbeResult(
            case_id="agent-perception-capability",
            metrics=metrics,
            diagnostics=cast(
                dict[str, JsonValue],
                {
                    "subsystem": (
                        "InvestigationRole->Perception->CapabilityBroker->"
                        "EvidenceIngress->StatePatch"
                    ),
                    "task_run_status": run.status,
                    "resolved_need_ids": outcome.result.resolved_need_ids,
                    "capability_invocation_ids": [item.invocation_id for item in invocations],
                    "perception_event_ids": [item.perception_event_id for item in perceptions],
                    "evidence_refs": [item.evidence_link_id for item in evidence_links],
                    "observation_ids": [item.observation_id for item in observations],
                    "task_event_types": [item.event_type.value for item in events],
                    "context_revision": context.context_revision,
                    "planner_request_count": len(provider.requests),
                    "expected_arguments_digest": canonical_arguments_digest(expected_arguments),
                    "observed_arguments_digest": invocation.arguments_digest,
                    "source_role": SOURCE.source_role.value,
                    "freshness_max_age_seconds": 3600,
                },
            ),
        )
    finally:
        await engine.dispose()


async def _probe_episode_recovery() -> ControlledProbeResult:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = _now()
    state_service = InvestigationStateService(now=lambda: now)
    execution_service = ExecutionRunService(now=lambda: now)
    try:
        case_id, object_id, need_id, first_run_id = await _seed_basic_role_run(
            factory,
            now=now,
            deadline_at=now + timedelta(minutes=5),
            signature="CVE-2026-AGENT-RECOVERY",
            evidence_contract=EvidenceNeedContract(require_evidence=False),
        )
        failure_planner = _ControlledFailurePlanner()
        first_failed = False
        try:
            await InvestigationRoleRuntime(
                factory,
                failure_planner,
                state_service=state_service,
                stream_name=STREAM,
                now=lambda: now,
            ).run(first_run_id)
        except RuntimeError as exc:
            first_failed = str(exc) == "controlled_recoverable_planner_failure"

        async with factory() as session:
            first_run = await get_task_run(session, first_run_id)
            first_context = await get_task_context(session, first_run_id)
            state = await state_service.get_state(session, case_id)
        if first_run.status is not TaskRunStatus.FAILED or not first_failed:
            raise RuntimeError("controlled recovery first episode did not fail as expected")

        second_run_id = str(uuid4())
        second_budget_id = f"budget:{second_run_id}"
        second_execution_id = f"execution:{second_run_id}"
        second_contract = build_investigation_contract(
            task_contract_id=f"verify:{second_run_id}",
            principal="benchmark:agent-runtime",
            task_kind=TaskKind.VERIFY_VERSION_FIX,
            case_id=case_id,
            target_object_ids=[object_id],
            required_need_ids=[need_id],
            policy_revision="policy-v1",
        )
        async with factory() as session, session.begin():
            await create_task_run(
                session,
                contract=second_contract,
                manifest=ContextManifest(
                    context_id=f"context:{second_run_id}",
                    context_revision=1,
                    task_contract_ref=f"{second_contract.task_contract_id}@1",
                    role_ref="InvestigationRole@1",
                    case_ref=case_id,
                    knowledge_revision=first_context.knowledge_revision,
                    investigation_state_ref=f"case:{case_id}@{state.case_revision}",
                    object_refs=[object_id],
                    policy_context_ref="policy-context:v1",
                    capability_envelope_ref="capability:controlled:none",
                    budget_ref=second_budget_id,
                ),
                role=canonical_roles()["InvestigationRole"],
                execution_envelope_ref=second_execution_id,
                stream_name=STREAM,
                case_id=case_id,
                run_id=second_run_id,
                now=now,
            )
            await BudgetGovernor(now=lambda: now).create_account(
                session,
                account_id=second_budget_id,
                task_run_id=second_run_id,
                limits=BudgetLimits(
                    quantities={"agent_turns": Decimal("3"), "tool_calls": Decimal("0")}
                ),
            )
            await execution_service.create(
                session,
                ExecutionEnvelope(
                    execution_id=second_execution_id,
                    task_contract_id=second_contract.task_contract_id,
                    task_run_id=second_run_id,
                    case_id=case_id,
                    role_revision="InvestigationRole@1",
                    context_manifest_revision=1,
                    execution_profile=ExecutionProfile.VERIFY,
                    capability_scope=[],
                    deadline_at=now + timedelta(minutes=5),
                    budget_ref=second_budget_id,
                    policy_revision="policy-v1",
                    identity_scope=["public"],
                    network_policy="proxied",
                    side_effect_policy="internal-state",
                    sandbox_profile_revision="process_restricted@1",
                ),
            )
            await execution_service.start(session, second_execution_id)

        recovery_planner = _ControlledRecoveryPlanner(object_id=object_id, need_id=need_id)
        second_outcome = await InvestigationRoleRuntime(
            factory,
            recovery_planner,
            state_service=state_service,
            stream_name=STREAM,
            now=lambda: now,
        ).run(second_run_id)
        async with factory() as session:
            second_run = await get_task_run(session, second_run_id)
        recovered = (
            second_run.status is TaskRunStatus.COMPLETED
            and second_outcome.run_status is TaskRunStatus.COMPLETED
            and need_id in second_outcome.result.resolved_need_ids
        )
        return ControlledProbeResult(
            case_id="agent-episode-recovery",
            metrics={"agent.recovery_success_rate": 1.0 if recovered else 0.0},
            diagnostics=cast(
                dict[str, JsonValue],
                {
                    "subsystem": (
                        "TaskRun failure->same Case/EvidenceNeed->"
                        "new InvestigationRole episode"
                    ),
                    "case_id": case_id,
                    "need_id": need_id,
                    "failed_run_id": first_run_id,
                    "failed_run_status": first_run.status.value,
                    "failed_stop_reason": first_run.stop_reason,
                    "recovery_run_id": second_run_id,
                    "recovery_run_status": second_run.status.value,
                    "recovery_stop_reason": second_run.stop_reason,
                    "same_case": second_run.case_id == first_run.case_id == case_id,
                    "recovery_planner_calls": recovery_planner.calls,
                },
            ),
        )
    finally:
        await engine.dispose()


async def _probe_delegated_enrichment_resume() -> ControlledProbeResult:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = _now()
    state_service = InvestigationStateService(now=lambda: now)
    budget = BudgetGovernor(now=lambda: now)
    execution_service = ExecutionRunService(now=lambda: now)
    redis = FakeRedis(decode_responses=True)
    cve_id = "CVE-2026-AGENT-DELEGATION"
    run_id = str(uuid4())
    execution_id = f"execution:{run_id}"
    budget_id = f"budget:{run_id}"
    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, [SOURCE])
            revision = KnowledgeRevisionModel(committed_at=now)
            session.add(revision)
            await session.flush()
            object_id = str(uuid4())
            session.add(
                ObjectModel(
                    object_id=object_id,
                    object_type="Vulnerability",
                    canonical_key=f"cve:{cve_id}",
                    properties={"display_name": cve_id},
                    created_revision=revision.revision,
                )
            )
            session.add(
                ExternalIdentifierModel(
                    external_identifier_id=str(uuid4()),
                    namespace="cve",
                    value=cve_id,
                    object_id=object_id,
                )
            )
            await session.flush()
            case = await CaseService(now=lambda: now).create(
                session,
                task_signature="agent-runtime-controlled-delegation",
                target_object_ids=[object_id],
                goal="Verify fixed version after filling the missing remediation dimension.",
                initial_knowledge_revision=revision.revision,
            )
            need = await state_service.open_evidence_need(
                session,
                case_id=case.case_id,
                base_case_revision=0,
                need_id=str(uuid4()),
                proposition_or_question="Which version first contains the fix?",
                purpose="verify_fix_release",
                target_objects=[object_id],
                evidence_contract=EvidenceNeedContract(
                    required_source_roles=["primary"],
                    min_independent_sources=1,
                ),
                writer="benchmark:agent-runtime-controlled",
                reason_code="controlled_delegation_gap_seed",
            )
            contract = build_investigation_contract(
                task_contract_id=f"verify:{run_id}",
                principal="benchmark:agent-runtime",
                task_kind=TaskKind.VERIFY_VERSION_FIX,
                case_id=case.case_id,
                target_object_ids=[object_id],
                required_need_ids=[need.need.need_id],
                policy_revision="policy-v1",
            )
            await create_task_run(
                session,
                contract=contract,
                manifest=ContextManifest(
                    context_id=f"context:{run_id}",
                    context_revision=1,
                    task_contract_ref=f"{contract.task_contract_id}@1",
                    role_ref="InvestigationRole@1",
                    case_ref=case.case_id,
                    knowledge_revision=revision.revision,
                    investigation_state_ref=f"case:{case.case_id}@1",
                    object_refs=[object_id],
                    policy_context_ref="policy-context:v1",
                    capability_envelope_ref="capability:verify:v1",
                    budget_ref=budget_id,
                ),
                role=canonical_roles()["InvestigationRole"],
                execution_envelope_ref=execution_id,
                stream_name=STREAM,
                case_id=case.case_id,
                run_id=run_id,
                now=now,
            )
            await budget.create_account(
                session,
                account_id=budget_id,
                task_run_id=run_id,
                limits=BudgetLimits(
                    quantities={"tool_calls": Decimal("4"), "agent_turns": Decimal("6")}
                ),
            )
            await execution_service.create(
                session,
                ExecutionEnvelope(
                    execution_id=execution_id,
                    task_contract_id=contract.task_contract_id,
                    task_run_id=run_id,
                    case_id=case.case_id,
                    role_revision="InvestigationRole@1",
                    context_manifest_revision=1,
                    execution_profile=ExecutionProfile.VERIFY,
                    capability_scope=["repo.read_release"],
                    deadline_at=now + timedelta(minutes=5),
                    budget_ref=budget_id,
                    policy_revision="policy-v1",
                    identity_scope=["public"],
                    network_policy="proxied",
                    side_effect_policy="internal-state",
                    sandbox_profile_revision="process_restricted@1",
                ),
            )
            await execution_service.start(session, execution_id)
            seed = seeded_skills()[0]
            validated = seed.model_copy(
                update={
                    "manifest": seed.manifest.model_copy(
                        update={
                            "status": SkillStatus.VALIDATED,
                            "validation_ref": "benchmark:agent-runtime-controlled-delegation-v1",
                        }
                    )
                }
            )
            await SkillStore(now=lambda: now).publish(session, validated)
            existing_fixed = list(
                await session.scalars(
                    select(RelationModel).where(
                        RelationModel.source_object_id == object_id,
                        RelationModel.relation_type == "fixed-version",
                    )
                )
            )
            if existing_fixed:
                raise RuntimeError("delegation probe requires missing fixed-version relation")

        registry = _registry()
        policy = _policy()
        provider = _DelegatedFixBoundaryModel(
            object_id=object_id,
            need_id=need.need.need_id,
            cve_id=cve_id,
        )
        planner = ModelInvestigationPlanner(
            factory,
            provider,
            materializer=ContextMaterializer(
                platform_invariant_revision="platform-v1",
                platform_invariant={
                    "state_write": "StatePatch gate",
                    "delegation": "bounded child TaskRun",
                    "ephemeral_observation_is_not_evidence": True,
                },
            ),
            capability_context_provider=CapabilityPlannerContextProvider(
                factory,
                registry,
                policy,
                semantic_class_map={
                    "repo.read_release": ["evidence.read", "graph.read"]
                },
                healthy_refs={"health:fixture-release-reader-agent-benchmark"},
                available_execution_classes={ExecutionClass.PROXIED_PROVIDER_READ},
                execution_service=execution_service,
            ),
            stream_name=STREAM,
        )
        delegation = EnrichmentDelegationAdapter(
            factory,
            policy=DelegatedEnrichmentPolicy(
                budget_quantities={"tool_calls": Decimal("2"), "agent_turns": Decimal("1")},
                capability_scope=["repo.read_release"],
                identity_scope=["public"],
            ),
            budget_governor=budget,
            execution_service=execution_service,
            stream_name=STREAM,
        )
        parent_runtime = InvestigationRoleRuntime(
            factory,
            planner,
            state_service=state_service,
            delegation_port=delegation,
            stream_name=STREAM,
            now=lambda: now,
        )
        waiting = await parent_runtime.run(run_id)
        if waiting.run_status is not TaskRunStatus.WAITING_DEPENDENCY:
            raise RuntimeError("controlled parent did not wait on delegated child")

        async with factory() as session:
            child = await session.scalar(
                select(TaskRunModel).where(TaskRunModel.parent_run_id == run_id)
            )
        if child is None or child.role_id != "EnrichmentRole" or child.status != "queued":
            raise RuntimeError("controlled delegation did not create queued EnrichmentRole child")

        child_executor = _DurableFixEnrichmentExecutor(
            factory=factory,
            object_id=object_id,
            now=now,
        )
        child_runtime = EnrichmentRoleRuntime(
            factory,
            child_executor,
            stream_name=STREAM,
            now=lambda: now,
        )

        async def run_child(claimed_run_id: str) -> object:
            async with factory() as session, session.begin():
                claimed = await get_task_run(session, claimed_run_id)
                await execution_service.start(session, claimed.execution_envelope_ref)
            return await child_runtime.run(claimed_run_id)

        child_dispatch = await QueuedRoleExecutor(
            factory,
            {"EnrichmentRole": run_child},
            stream_name=STREAM,
        ).execute(child.run_id)
        if child_dispatch.disposition is not RoleDispatchDisposition.EXECUTED:
            raise RuntimeError("controlled EnrichmentRole child was not executed")

        async with factory() as session:
            child_after = await get_task_run(session, child.run_id)
            fixed_relations = list(
                await session.scalars(
                    select(RelationModel).where(
                        RelationModel.source_object_id == object_id,
                        RelationModel.relation_type == "fixed-version",
                        RelationModel.superseded_revision.is_(None),
                    )
                )
            )
            child_events = await list_task_events(session, child.run_id)
        if child_after.status is not TaskRunStatus.COMPLETED or len(fixed_relations) != 1:
            raise RuntimeError("controlled child did not materialize one fixed-version relation")
        enrichment_changed = next(
            event for event in child_events if event.event_type.value == "EnrichmentStateChanged"
        )

        async with factory() as session, session.begin():
            await dispatch_pending_task_events(session, redis, now=now)
        messages = await read_task_event_messages(
            redis,
            stream_name=STREAM,
            group_name="agent-runtime-controlled-scheduler",
            consumer_name="agent-runtime-controlled-consumer",
            claim_idle_ms=0,
            block_ms=None,
        )
        wake_results = []
        for message in messages:
            async with factory() as session, session.begin():
                event = await get_task_event(session, message.event_id)
                wake_results.append(
                    await DependencyWakeScheduler(
                        stream_name=STREAM,
                        now=lambda: now,
                    ).process_event(session, event)
                )
            await ack_task_event_message(
                redis,
                stream_name=STREAM,
                group_name="agent-runtime-controlled-scheduler",
                message_id=message.message_id,
            )
        queued_wakes = [
            result
            for result in wake_results
            if result.disposition is DependencyWakeDisposition.QUEUED
        ]
        if [item.source_event_id for item in queued_wakes] != [enrichment_changed.event_id]:
            raise RuntimeError("controlled child event did not uniquely wake parent")

        async def run_parent(claimed_run_id: str) -> object:
            return await parent_runtime.run(claimed_run_id)

        parent_dispatch = await QueuedRoleExecutor(
            factory,
            {"InvestigationRole": run_parent},
            stream_name=STREAM,
        ).execute(run_id)
        if (
            parent_dispatch.disposition is not RoleDispatchDisposition.EXECUTED
            or parent_dispatch.final_status is not TaskRunStatus.COMPLETED
        ):
            raise RuntimeError("controlled parent did not resume to completion")

        async with factory() as session:
            parent_after = await get_task_run(session, run_id)
            state = await state_service.get_state(session, case.case_id)
            manifest = await get_task_context(session, run_id)
            parent_events = await list_task_events(session, run_id)
            child_budget = await session.scalar(
                select(BudgetAccountModel).where(BudgetAccountModel.task_run_id == child.run_id)
            )
            relation_evidence = list(
                await session.scalars(
                    select(EvidenceLinkModel).where(
                        EvidenceLinkModel.target_kind == "relation",
                        EvidenceLinkModel.target_id == fixed_relations[0].relation_id,
                    )
                )
            )
        if len(relation_evidence) != 1 or not state.confirmed:
            raise RuntimeError("controlled parent did not integrate child Evidence into state")

        child_useful = bool(
            relation_evidence[0].evidence_link_id in set(state.confirmed[0].evidence_refs)
            and parent_after.status is TaskRunStatus.COMPLETED
        )
        budget_adherent = bool(
            child_budget is not None
            and child_budget.parent_account_id == budget_id
            and Decimal(child_budget.limits.get("tool_calls", "0")) <= Decimal("4")
            and Decimal(child_budget.limits.get("agent_turns", "0")) <= Decimal("6")
        )
        stale_child_result = manifest.knowledge_revision != fixed_relations[0].created_revision
        metrics = {
            "agent.delegation_precision": float(child_useful),
            "agent.child_task_usefulness": float(child_useful),
            "agent.parent_child_budget_adherence": float(budget_adherent),
            "agent.stale_child_result_rate": float(stale_child_result),
        }
        return ControlledProbeResult(
            case_id="agent-delegated-enrichment-resume",
            metrics=metrics,
            diagnostics=cast(
                dict[str, JsonValue],
                {
                    "subsystem": (
                        "InvestigationRole->EnrichmentRole->TaskEvent->DependencyWake->"
                        "Perception->StatePatch"
                    ),
                    "parent_run_id": run_id,
                    "child_run_id": child.run_id,
                    "child_status": child_after.status.value,
                    "parent_status": parent_after.status.value,
                    "child_budget_parent": (
                        child_budget.parent_account_id if child_budget is not None else None
                    ),
                    "child_budget_limits": child_budget.limits if child_budget is not None else {},
                    "fixed_relation_id": fixed_relations[0].relation_id,
                    "fixed_relation_revision": fixed_relations[0].created_revision,
                    "parent_context_knowledge_revision": manifest.knowledge_revision,
                    "relation_evidence_refs": [
                        item.evidence_link_id for item in relation_evidence
                    ],
                    "parent_task_event_types": [
                        item.event_type.value for item in parent_events
                    ],
                    "child_task_event_types": [item.event_type.value for item in child_events],
                    "planner_request_count": len(provider.requests),
                    "enrichment_operator_calls": child_executor.calls,
                    "wake_source_event_id": enrichment_changed.event_id,
                },
            ),
        )
    finally:
        await redis.aclose()
        await engine.dispose()


async def _probe_health_ranked_fallback() -> ControlledProbeResult:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = _now()
    budget = BudgetGovernor(now=lambda: now)
    execution_service = ExecutionRunService(now=lambda: now)
    try:
        _, _, _, run_id = await _seed_basic_role_run(
            factory,
            now=now,
            deadline_at=now + timedelta(minutes=5),
            signature="CVE-2026-AGENT-FALLBACK",
            capability_scope=["repo.read_release"],
        )
        registry, preferred_binding_id, fallback_binding_id = _fallback_registry()
        executor = _FallbackBindingExecutor(
            expected_tool_impl_id="fixture-release-reader-fallback"
        )
        broker = CapabilityBroker(registry, _policy(), budget, now=lambda: now)
        async with factory() as session, session.begin():
            task = await get_task_contract_for_run(session, run_id)
            envelope = await execution_service.get(session, f"execution:{run_id}")
            desired_case_id = task.desired_state.get("case_id")
            outcome = await broker.invoke(
                session,
                task=task,
                envelope=envelope,
                request=CapabilityRequest(
                    request_id="controlled-health-fallback",
                    task_contract_id=task.task_contract_id,
                    task_run_id=run_id,
                    case_id=desired_case_id if isinstance(desired_case_id, str) else None,
                    principal=task.principal,
                    capability_id="repo.read_release",
                    contract_revision=1,
                    action="read",
                    resource="repo:fixture/project",
                    resource_type="repository.release",
                    canonical_arguments={"tag": "v1.2.3"},
                    intended_effect=EffectSemantics.OBSERVATION,
                    evidence_purpose="verify release under provider-health fallback",
                ),
                executor=executor,
                estimated_budget={"tool_calls": Decimal("1")},
                grants=InvocationGrants(),
                healthy_refs={"health:fixture-fallback"},
                available_execution_classes={ExecutionClass.PROXIED_PROVIDER_READ},
            )
            selected_fallback = outcome.plan.binding_id == fallback_binding_id
            succeeded = outcome.result.status is CapabilityResultStatus.SUCCEEDED
            preferred_skipped = outcome.plan.binding_id != preferred_binding_id
        success = selected_fallback and succeeded and preferred_skipped
        return ControlledProbeResult(
            case_id="agent-health-ranked-fallback",
            metrics={"agent.fallback_success_rate": float(success)},
            diagnostics=cast(
                dict[str, JsonValue],
                {
                    "subsystem": "CapabilityRegistry->CapabilityBroker",
                    "fallback_semantics": "preferred binding filtered by health before invocation",
                    "preferred_binding_id": preferred_binding_id,
                    "fallback_binding_id": fallback_binding_id,
                    "selected_binding_id": outcome.plan.binding_id,
                    "healthy_refs": ["health:fixture-fallback"],
                    "executor_calls": executor.calls,
                    "result_status": outcome.result.status.value,
                },
            ),
        )
    finally:
        await engine.dispose()


async def _probe_conflict_preservation() -> ControlledProbeResult:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = _now()
    ingress = EvidenceIngress(MemoryArtifactStore(), now=lambda: now)
    state_service = InvestigationStateService(now=lambda: now)
    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, [SOURCE, SECONDARY_SOURCE])
            revision = KnowledgeRevisionModel(committed_at=now)
            session.add(revision)
            await session.flush()
            object_id = str(uuid4())
            session.add(
                ObjectModel(
                    object_id=object_id,
                    object_type="Vulnerability",
                    canonical_key="cve:CVE-2026-AGENT-CONFLICT",
                    properties={"display_name": "CVE-2026-AGENT-CONFLICT"},
                    created_revision=revision.revision,
                )
            )
            await session.flush()
            case = await CaseService(now=lambda: now).create(
                session,
                task_signature="agent-runtime-controlled-conflict",
                target_object_ids=[object_id],
                goal="Preserve conflicting fixed-version evidence without collapsing it.",
                initial_knowledge_revision=revision.revision,
            )
            evidence_refs: list[str] = []
            for source, fixed_version in (
                (SOURCE, "v1.2.3"),
                (SECONDARY_SOURCE, "v1.2.4"),
            ):
                acquisition_run_id = str(uuid4())
                session.add(
                    AcquisitionRunModel(
                        run_id=acquisition_run_id,
                        source_id=source.source_id,
                        trigger="investigation",
                        parent_run_id=None,
                        query_spec={"fixed_version": fixed_version},
                        status="success",
                        cursor_in={},
                        cursor_out={"result_count": 1},
                        attempt=1,
                        created_at=now,
                        started_at=now,
                        finished_at=now,
                    )
                )
                ack = await ingress.accept(
                    session,
                    source,
                    IngestEnvelope.for_json_payload(
                        acquisition_run_id=acquisition_run_id,
                        trigger=AcquisitionTrigger.INVESTIGATION,
                        source_id=source.source_id,
                        external_object_id=f"conflict:{fixed_version}",
                        payload={"fixed_version": fixed_version},
                        canonical_url=f"https://example.invalid/{source.source_id}/{fixed_version}",
                        published_at=now,
                        updated_at=now,
                        external_revision=fixed_version,
                        observed_at=now,
                    ),
                )
                evidence_link_id = str(uuid4())
                locator = {"kind": "json", "field": "fixed_version", "value": fixed_version}
                locator_hash = canonical_arguments_digest(cast(dict[str, JsonValue], locator))
                session.add(
                    EvidenceLinkModel(
                        evidence_link_id=evidence_link_id,
                        target_kind="object",
                        target_id=object_id,
                        observation_id=ack.observation_id,
                        artifact_id=ack.artifact_id,
                        locator=locator,
                        locator_hash=locator_hash,
                    )
                )
                evidence_refs.append(evidence_link_id)
            await session.flush()
            result = await state_service.apply_patch(
                session,
                StatePatch(
                    patch_id=str(uuid4()),
                    case_id=case.case_id,
                    base_case_revision=0,
                    producer="InvestigationRole@controlled-conflict",
                    operations=[
                        StatePatchOperation(
                            proposition=(
                                "Conflicting sources report fixed versions "
                                "v1.2.3 and v1.2.4."
                            ),
                            target_ref=f"object:{object_id}",
                            proposed_state=ProposedState.CONFLICT,
                            evidence_refs=evidence_refs,
                        )
                    ],
                ),
            )
            preserved = len(result.state.conflicts) == 1
            collapsed = bool(result.state.confirmed or result.state.tentative)
        collapse_rate = 0.0 if preserved and not collapsed else 1.0
        return ControlledProbeResult(
            case_id="agent-conflict-preservation",
            metrics={"agent.conflict_collapse_rate": collapse_rate},
            diagnostics=cast(
                dict[str, JsonValue],
                {
                    "subsystem": "InvestigationStateService->StatePatch",
                    "conflict_group_count": 1,
                    "conflict_bucket_size": len(result.state.conflicts),
                    "confirmed_bucket_size": len(result.state.confirmed),
                    "tentative_bucket_size": len(result.state.tentative),
                    "evidence_refs": evidence_refs,
                    "source_roles": [SOURCE.source_role.value, SECONDARY_SOURCE.source_role.value],
                },
            ),
        )
    finally:
        await engine.dispose()


async def _probe_no_progress_stop() -> ControlledProbeResult:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = _now()
    try:
        _, _, _, run_id = await _seed_basic_role_run(
            factory,
            now=now,
            deadline_at=now + timedelta(minutes=5),
            signature="CVE-2026-AGENT-NO-PROGRESS",
        )
        planner = _NoSignalPlanner()
        outcome = await InvestigationRoleRuntime(
            factory,
            planner,
            perception_runtime=PerceptionRuntime(_NoSignalPhysicalObservationPort()),
            stream_name=STREAM,
            max_iterations=5,
            no_progress_limit=2,
            now=lambda: now,
        ).run(run_id)
        if outcome.run_status is not TaskRunStatus.BLOCKED:
            raise RuntimeError("no-progress probe did not terminate blocked")
        no_progress_iterations = max(outcome.result.iterations - 1, 0)
        rate = no_progress_iterations / outcome.result.iterations
        return ControlledProbeResult(
            case_id="agent-no-progress-stop",
            metrics={"agent.no_progress_iteration_rate": rate},
            diagnostics=cast(
                dict[str, JsonValue],
                {
                    "stop_reason": outcome.result.stop_reason,
                    "iterations": outcome.result.iterations,
                    "planner_calls": planner.calls,
                    "no_progress_limit": 2,
                    "expected_stop_reason": "no_progress",
                    "bounded_stop_correct": outcome.result.stop_reason == "no_progress",
                },
            ),
        )
    finally:
        await engine.dispose()


async def _probe_deadline_stop() -> ControlledProbeResult:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = _now()
    try:
        _, _, _, run_id = await _seed_basic_role_run(
            factory,
            now=now,
            deadline_at=now - timedelta(seconds=1),
            signature="CVE-2026-AGENT-DEADLINE",
        )
        planner = _DeadlineSentinelPlanner()
        outcome = await InvestigationRoleRuntime(
            factory,
            planner,
            execution_boundary=_DeadlineBoundary(),
            stream_name=STREAM,
            max_iterations=4,
            no_progress_limit=2,
            now=lambda: now,
        ).run(run_id)
        correct = outcome.result.stop_reason == "deadline_reached" and planner.calls == 0
        return ControlledProbeResult(
            case_id="agent-deadline-stop",
            metrics={"agent.budget_deadline_stop_correctness": float(correct)},
            diagnostics=cast(
                dict[str, JsonValue],
                {
                    "stop_reason": outcome.result.stop_reason,
                    "planner_calls": planner.calls,
                    "frozen_deadline_relation": "deadline_at < now before first planning turn",
                    "expected_stop_reason": "deadline_reached",
                    "expected_planner_calls": 0,
                },
            ),
        )
    finally:
        await engine.dispose()


async def _run(*, suite_revision: int, deployment_revision_id: str | None) -> dict[str, Any]:
    probes = [
        await _probe_perception_capability(),
        await _probe_delegated_enrichment_resume(),
        await _probe_health_ranked_fallback(),
        await _probe_conflict_preservation(),
        await _probe_episode_recovery(),
        await _probe_no_progress_stop(),
        await _probe_deadline_stop(),
    ]
    now = datetime.now(UTC)
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    store = BenchmarkStore()
    try:
        async with factory() as session, session.begin():
            deployment_id = await ensure_benchmark_deployment_revision(
                session,
                settings,
                deployment_revision_id=deployment_revision_id,
            )
            case_refs: list[str] = []
            for probe in probes:
                case = BenchmarkCase(
                    case_id=probe.case_id,
                    case_revision=suite_revision,
                    input={
                        "control": probe.case_id,
                        "task_kind": TaskKind.VERIFY_VERSION_FIX.value,
                    },
                    execution_profile="controlled_agent_runtime",
                    expected_behavior={
                        "metrics": cast(dict[str, JsonValue], probe.metrics),
                    },
                    gold_ref=f"agent-runtime-controlled-gold-v1#{probe.case_id}",
                    tags=["agent", "controlled", "m5", probe.case_id],
                    latency_class="controlled",
                    replay_tier="R0",
                    created_at=now,
                )
                await store.register_case(session, case)
                case_refs.append(f"{case.case_id}@{case.case_revision}")
            await store.register_suite(
                session,
                BenchmarkSuite(
                    suite_id=SUITE_ID,
                    suite_revision=suite_revision,
                    domain=BenchmarkDomain.M5_AGENT,
                    purpose=(
                        "Controlled M5 runtime regression over physical acquisition, capability "
                        "selection/arguments, Evidence promotion and StatePatch integration"
                    ),
                    case_refs=case_refs,
                    gold_revision="agent-runtime-controlled-gold-v1",
                    evaluator_revision=EVALUATOR_REVISION,
                    scoring_profile=cast(
                        dict[str, JsonValue],
                        {
                            "metrics": sorted(
                                {metric for probe in probes for metric in probe.metrics}
                            ),
                            "scope": (
                                "controlled_runtime_regression_not_live_external_agent_score"
                            ),
                        },
                    ),
                    created_at=now,
                ),
            )
            run = await store.start_run(
                session,
                suite_ref=f"{SUITE_ID}@{suite_revision}",
                deployment_revision_id=deployment_id,
                execution_mode=BenchmarkExecutionMode.LIVE_CONTROLLED,
                environment=settings.environment,
                model_config_ref="model:fixture-deterministic-agent-planner",
                now=now,
            )

        for probe in probes:
            async with factory() as session, session.begin():
                case_run = await store.start_case_run(
                    session,
                    benchmark_run_id=run.benchmark_run_id,
                    case_ref=f"{probe.case_id}@{suite_revision}",
                    now=now,
                )
                for metric_name, value in probe.metrics.items():
                    definition = metric_definition(metric_name)
                    source = (
                        MeasurementSource.EXACT
                        if metric_name == "agent.capability_invocation_count"
                        else MeasurementSource.SCORER
                    )
                    await store.observe_metric(
                        session,
                        case_run_id=case_run.case_run_id,
                        metric_name=metric_name,
                        value=value,
                        direction=definition.direction,
                        measurement_source=source,
                        subject_ref=f"agent-controlled:{probe.case_id}",
                        metadata=probe.diagnostics,
                        now=now,
                    )
                await store.finish_case_run(
                    session,
                    case_run.case_run_id,
                    status=BenchmarkCaseRunStatus.PASSED,
                    now=now,
                )
        async with factory() as session, session.begin():
            await store.finish_run(
                session,
                run.benchmark_run_id,
                status=BenchmarkRunStatus.COMPLETED,
                now=now,
            )
        return {
            "schema_version": "agent-runtime-controlled-benchmark-v1",
            "benchmark_run_id": run.benchmark_run_id,
            "deployment_revision_id": deployment_id,
            "suite_ref": f"{SUITE_ID}@{suite_revision}",
            "execution_mode": BenchmarkExecutionMode.LIVE_CONTROLLED.value,
            "scope": "controlled_runtime_regression_not_live_external_agent_score",
            "cases": {
                probe.case_id: {
                    "metrics": probe.metrics,
                    "diagnostics": probe.diagnostics,
                }
                for probe in probes
            },
        }
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run controlled M5 Agent runtime benchmark")
    parser.add_argument("--suite-revision", type=int, required=True)
    parser.add_argument("--deployment-revision-id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = asyncio.run(
        _run(
            suite_revision=args.suite_revision,
            deployment_revision_id=args.deployment_revision_id,
        )
    )
    encoded = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()
