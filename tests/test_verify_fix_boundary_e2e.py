from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fakeredis.aioredis import FakeRedis
from pydantic import JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

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
    PerceptionOperation,
    PerceptionRequest,
    PerceptionTarget,
)
from packages.investigation.perception.runtime import PerceptionRuntime
from packages.investigation.runtime.contracts import (
    DelegationAction,
    EnrichmentDelegationRequest,
    InvestigationPlannerDecision,
    PerceptionAction,
    StatePatchAction,
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
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.runtime.artifacts import MemoryRuntimeBlobStore, RuntimeArtifactService
from packages.runtime.budget import BudgetGovernor, BudgetLimits
from packages.runtime.capability.broker import CapabilityBroker, NativeExecutionResult
from packages.runtime.capability.contracts import (
    CapabilityBinding,
    CapabilityContract,
    CapabilityDescriptor,
    CapabilityResultStatus,
    EffectSemantics,
    ExecutionClass,
    ImplementationKind,
    ToolImplementation,
    native_schema_hash,
)
from packages.runtime.capability.registry import CapabilityRegistry
from packages.runtime.execution.service import ExecutionRunService
from packages.runtime.policy.contracts import Authorization, PolicyDecisionPoint
from packages.runtime.policy.engine import RuntimePolicyRule, StaticPolicyEngine
from packages.runtime.sandbox.broker import SandboxBroker
from packages.shared.db import Base
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
from packages.task_runtime.scheduler import DependencyWakeDisposition, DependencyWakeScheduler
from packages.task_runtime.storage.models import TaskRunModel
from packages.task_runtime.storage.service import (
    create_task_run,
    get_task_context,
    get_task_event,
    list_task_events,
)

NOW = datetime(2026, 9, 27, 14, 0, tzinfo=UTC)
STREAM = "secfusion:task-events:verify-fix-boundary-e2e"
SOURCE = SourceDefinition(
    source_id="fixture-primary-release-api-verify-e2e",
    adapter_type="fixture",
    source_class="development_platform",
    authority_scope=["release_state", "fix_status"],
    source_role=SourceRole.PRIMARY,
    source_family="fixture-primary-release-api-verify-e2e",
    access_mode="api",
    update_semantics="mutable",
    retention_mode=RetentionMode.TIME_BOUNDED,
)


class _VerifyFixBoundaryModel:
    name = "verify-fix-boundary-e2e"
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


class _PrimaryReleaseExecutor:
    def __init__(self, *, artifact_ref: str, acquisition_run_id: str) -> None:
        self._artifact_ref = artifact_ref
        self._acquisition_run_id = acquisition_run_id
        self.calls = 0

    async def execute(self, implementation, *, native_arguments, timeout_seconds):
        del implementation, timeout_seconds
        self.calls += 1
        assert native_arguments["tag"] == "v1.2.3"
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
                "published_at": NOW.isoformat(),
                "updated_at": NOW.isoformat(),
            },
        )


class _DelegatedFixBoundaryModel:
    name = "verify-fix-boundary-delegation-e2e"
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
                        required_dimensions=[EnrichmentDimension.FIX_REMEDIATION.value],
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
                                {
                                    "target_kind": "relation",
                                    "target_id": relation_id,
                                }
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
    def __init__(self, *, factory, object_id: str) -> None:
        self._factory = factory
        self._object_id = object_id
        self._ingress = EvidenceIngress(MemoryArtifactStore(), now=lambda: NOW)
        self._writer = EvidenceBackedKnowledgeWriter(now=lambda: NOW)
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
                    created_at=NOW,
                    started_at=NOW,
                    finished_at=NOW,
                )
            )
            envelope = IngestEnvelope.for_json_payload(
                acquisition_run_id=self._acquisition_run_id,
                trigger=AcquisitionTrigger.INVESTIGATION,
                source_id=SOURCE.source_id,
                external_object_id=f"{cve_id}:fixed-version",
                payload={"cve_id": cve_id, "fixed_version": "v1.2.3"},
                canonical_url="https://example.invalid/advisories/fixed-version",
                published_at=NOW,
                updated_at=NOW,
                external_revision="v1.2.3",
                observed_at=NOW,
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
                processor_name="verify-fix-boundary-delegated-fixture",
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
        raise AssertionError(f"VERIFY external-only fixture should not create sandbox: {lease}")

    async def exec(self, backend_handle_ref, request, *, timeout_seconds):
        raise AssertionError(
            f"VERIFY external-only fixture should not exec sandbox: "
            f"{backend_handle_ref} {request} {timeout_seconds}"
        )

    async def export(self, backend_handle_ref, relative_paths):
        raise AssertionError(
            f"VERIFY external-only fixture should not export sandbox: "
            f"{backend_handle_ref} {relative_paths}"
        )

    async def destroy(self, backend_handle_ref):
        raise AssertionError(
            f"VERIFY external-only fixture should not destroy sandbox: {backend_handle_ref}"
        )


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
    raise LookupError("model second turn did not receive durable evidence handle")


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
    raise LookupError(f"model context did not receive relation_type={relation_type}")


def _registry() -> CapabilityRegistry:
    input_schema: dict[str, JsonValue] = {
        "type": "object",
        "properties": {"tag": {"type": "string"}},
        "required": ["tag"],
    }
    output_schema: dict[str, JsonValue] = {"type": "object"}
    schema_hash = native_schema_hash(input_schema, output_schema)
    implementation = ToolImplementation(
        tool_impl_id="fixture-release-reader-verify-e2e",
        implementation_revision=1,
        implementation_kind=ImplementationKind.PROVIDER_API,
        native_name="fixture.release.read",
        transport="fixture",
        native_input_schema=input_schema,
        native_output_schema=output_schema,
        health_ref="health:fixture-release-reader",
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
        binding_id="fixture-release-reader-binding-verify-e2e",
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
        revision="registry-verify-fix-e2e-v1",
        contracts=[contract],
        descriptors={
            contract.capability_id: CapabilityDescriptor(
                purpose="Read primary release state and fix-containment evidence"
            )
        },
        implementations=[implementation],
        bindings=[binding],
    )


def _policy() -> StaticPolicyEngine:
    return StaticPolicyEngine(
        policy_revision="policy-v1",
        rules=[
            RuntimePolicyRule(
                policy_id="verify-fix-visible-release-read",
                policy_revision="policy-v1",
                decision_points=[PolicyDecisionPoint.CAPABILITY_VISIBILITY],
                principal_patterns=["user:test"],
                action_patterns=["read"],
                resource_patterns=["capability:repo.read_release"],
                authorization=Authorization.PERMIT,
            ),
            RuntimePolicyRule(
                policy_id="verify-fix-invoke-release-read",
                policy_revision="policy-v1",
                decision_points=[PolicyDecisionPoint.CAPABILITY_INVOCATION],
                principal_patterns=["user:test"],
                action_patterns=["read"],
                resource_patterns=["repo:fixture/project"],
                authorization=Authorization.PERMIT,
            ),
            RuntimePolicyRule(
                policy_id="verify-fix-promote-primary-observation",
                policy_revision="policy-v1",
                decision_points=[PolicyDecisionPoint.OBSERVATION_PROMOTION],
                principal_patterns=["user:test"],
                action_patterns=["promote_observation"],
                resource_patterns=[f"source:{SOURCE.source_id}"],
                authorization=Authorization.PERMIT,
            ),
        ],
    )


@pytest.mark.asyncio
async def test_verify_fix_boundary_runs_canonical_task_to_evidence_to_state_chain() -> None:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    state_service = InvestigationStateService(now=lambda: NOW)
    budget = BudgetGovernor(now=lambda: NOW)
    execution_service = ExecutionRunService(now=lambda: NOW)
    runtime_artifacts = RuntimeArtifactService(MemoryRuntimeBlobStore(), now=lambda: NOW)
    run_id = str(uuid4())
    execution_id = f"execution:{run_id}"
    budget_id = f"budget:{run_id}"
    acquisition_run_id = str(uuid4())

    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, [SOURCE])
            revision = KnowledgeRevisionModel(committed_at=NOW)
            session.add(revision)
            await session.flush()

            object_id = str(uuid4())
            session.add(
                ObjectModel(
                    object_id=object_id,
                    object_type="Vulnerability",
                    canonical_key="cve:CVE-2026-90909",
                    properties={"display_name": "CVE-2026-90909"},
                    created_revision=revision.revision,
                )
            )
            await session.flush()
            case = await CaseService(now=lambda: NOW).create(
                session,
                task_signature="verify-fix-boundary-e2e",
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
            )
            contract = build_investigation_contract(
                task_contract_id=f"verify:{run_id}",
                principal="user:test",
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
                now=NOW,
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
                deadline_at=NOW + timedelta(minutes=5),
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
                    created_at=NOW,
                    started_at=NOW,
                    finished_at=NOW,
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
                            "validation_ref": "m7-replay:verify-fix-boundary-e2e:v1",
                        }
                    )
                }
            )
            await SkillStore(now=lambda: NOW).publish(session, validated)

        registry = _registry()
        policy = _policy()
        executor = _PrimaryReleaseExecutor(
            artifact_ref=artifact.artifact_ref,
            acquisition_run_id=acquisition_run_id,
        )
        capability_broker = CapabilityBroker(registry, policy, budget, now=lambda: NOW)
        sandbox_broker = SandboxBroker(
            policy,
            {"openshell": _UnusedSandboxBackend()},
            available_backend_components={"openshell"},
            execution_service=execution_service,
            now=lambda: NOW,
        )
        resolver = StaticPerceptionExecutionResolver(
            factory,
            external_routes=[
                ExternalObservationRoute(
                    route_id="verify-fix-primary-release",
                    route_revision=1,
                    capability_requirement="external_observation",
                    capability_id="repo.read_release",
                    contract_revision=1,
                    action="read",
                    resource_type="repository.release",
                    resource="repo:fixture/project",
                    argument_map={"tag": "query_text"},
                    estimated_budget={"tool_calls": Decimal("1")},
                    healthy_refs={"health:fixture-release-reader"},
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
            EvidenceIngress(MemoryArtifactStore(), now=lambda: NOW),
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
                    "repo.read_release": ["evidence.read", "graph.read"],
                },
                healthy_refs={"health:fixture-release-reader"},
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
            now=lambda: NOW,
        ).run(run_id)

        assert outcome.run_status.value == "completed"
        assert outcome.result.resolved_need_ids == [need.need.need_id]
        assert executor.calls == 1
        assert len(provider.requests) == 2
        assert "investigation.verify_fix_boundary" in provider.requests[0].system_instruction
        assert '"kind":"capability_cards"' in provider.requests[0].system_instruction
        assert "repo.read_release" in provider.requests[0].system_instruction

        async with factory() as session:
            state = await state_service.get_state(session, case.case_id)
            manifest = await get_task_context(session, run_id)
            events = await list_task_events(session, run_id)
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
            run = await session.get(TaskRunModel, run_id)

        assert run is not None and run.status == "completed"
        assert len(evidence_links) == 1
        assert len(observations) == 1
        evidence_ref = evidence_links[0].evidence_link_id
        assert state.confirmed[0].evidence_refs == [evidence_ref]
        assert manifest.investigation_state_ref == f"case:{case.case_id}@{state.case_revision}"
        assert manifest.skill_selection_refs == [validated.manifest.ref]
        event_types = [event.event_type.value for event in events]
        assert event_types[0:3] == ["TaskCreated", "TaskPatched", "TaskStarted"]
        assert "EvidenceFound" in event_types
        assert "InvestigationStateChanged" in event_types
        assert event_types[-1] == "TaskCompleted"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_verify_fix_boundary_delegates_missing_fix_then_resumes_from_durable_world() -> None:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    state_service = InvestigationStateService(now=lambda: NOW)
    budget = BudgetGovernor(now=lambda: NOW)
    execution_service = ExecutionRunService(now=lambda: NOW)
    redis = FakeRedis(decode_responses=True)
    cve_id = "CVE-2026-91919"
    run_id = str(uuid4())
    execution_id = f"execution:{run_id}"
    budget_id = f"budget:{run_id}"

    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, [SOURCE])
            revision = KnowledgeRevisionModel(committed_at=NOW)
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
            case = await CaseService(now=lambda: NOW).create(
                session,
                task_signature="verify-fix-boundary-delegated-e2e",
                target_object_ids=[object_id],
                goal="Verify the first fixed version after filling the missing fix dimension.",
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
            )
            contract = build_investigation_contract(
                task_contract_id=f"verify:{run_id}",
                principal="user:test",
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
                now=NOW,
            )
            await budget.create_account(
                session,
                account_id=budget_id,
                task_run_id=run_id,
                limits=BudgetLimits(
                    quantities={"tool_calls": Decimal("4"), "agent_turns": Decimal("6")}
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
                deadline_at=NOW + timedelta(minutes=5),
                budget_ref=budget_id,
                policy_revision="policy-v1",
                identity_scope=["public"],
                network_policy="proxied",
                side_effect_policy="internal-state",
                sandbox_profile_revision="process_restricted@1",
            )
            await execution_service.create(session, envelope)
            await execution_service.start(session, execution_id)
            seed = seeded_skills()[0]
            validated = seed.model_copy(
                update={
                    "manifest": seed.manifest.model_copy(
                        update={
                            "status": SkillStatus.VALIDATED,
                            "validation_ref": "m7-replay:verify-fix-boundary-delegated-e2e:v1",
                        }
                    )
                }
            )
            await SkillStore(now=lambda: NOW).publish(session, validated)

            initial_fix_relations = list(
                await session.scalars(
                    select(RelationModel).where(
                        RelationModel.source_object_id == object_id,
                        RelationModel.relation_type == "fixed-version",
                    )
                )
            )
            assert initial_fix_relations == []

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
                    "repo.read_release": ["evidence.read", "graph.read"],
                },
                healthy_refs={"health:fixture-release-reader"},
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
            now=lambda: NOW,
        )

        waiting = await parent_runtime.run(run_id)
        assert waiting.run_status is TaskRunStatus.WAITING_DEPENDENCY
        assert waiting.result.stop_reason.startswith("task_dependency:")
        assert len(provider.requests) == 1

        async with factory() as session:
            child = await session.scalar(
                select(TaskRunModel).where(TaskRunModel.parent_run_id == run_id)
            )
        assert child is not None
        assert child.role_id == "EnrichmentRole"
        child_executor = _DurableFixEnrichmentExecutor(factory=factory, object_id=object_id)
        child_outcome = await EnrichmentRoleRuntime(
            factory,
            child_executor,
            stream_name=STREAM,
            now=lambda: NOW,
        ).run(child.run_id)
        assert child_outcome.run_status is TaskRunStatus.COMPLETED
        assert (
            child_outcome.result.dimension_status[EnrichmentDimension.FIX_REMEDIATION].value
            == "resolved"
        )

        async with factory() as session:
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
        assert len(fixed_relations) == 1
        enrichment_changed = next(
            event for event in child_events if event.event_type.value == "EnrichmentStateChanged"
        )

        async with factory() as session, session.begin():
            delivered = await dispatch_pending_task_events(session, redis, now=NOW)
            assert delivered > 0
        messages = await read_task_event_messages(
            redis,
            stream_name=STREAM,
            group_name="verify-fix-boundary-scheduler",
            consumer_name="verify-fix-boundary-consumer",
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
                        now=lambda: NOW,
                    ).process_event(session, event)
                )
            assert (
                await ack_task_event_message(
                    redis,
                    stream_name=STREAM,
                    group_name="verify-fix-boundary-scheduler",
                    message_id=message.message_id,
                )
                == 1
            )
        queued_wakes = [
            result
            for result in wake_results
            if result.disposition is DependencyWakeDisposition.QUEUED
        ]
        assert [result.source_event_id for result in queued_wakes] == [enrichment_changed.event_id]
        async with factory() as session:
            queued_parent = await session.get(TaskRunModel, run_id)
            assert queued_parent is not None and queued_parent.status == "queued"

        completed = await parent_runtime.run(run_id)
        assert completed.run_status is TaskRunStatus.COMPLETED
        assert completed.result.resolved_need_ids == [need.need.need_id]
        assert len(provider.requests) == 3
        assert "fixed-version" in str(provider.requests[1].data)

        async with factory() as session:
            state = await state_service.get_state(session, case.case_id)
            manifest = await get_task_context(session, run_id)
            parent_events = await list_task_events(session, run_id)
            evidence_links = list(
                await session.scalars(
                    select(EvidenceLinkModel).where(
                        EvidenceLinkModel.target_kind == "relation",
                        EvidenceLinkModel.target_id == fixed_relations[0].relation_id,
                    )
                )
            )
        assert len(evidence_links) == 1
        assert state.confirmed[0].evidence_refs == [evidence_links[0].evidence_link_id]
        assert manifest.knowledge_revision == fixed_relations[0].created_revision
        assert manifest.investigation_state_ref == f"case:{case.case_id}@{state.case_revision}"
        parent_event_types = [event.event_type.value for event in parent_events]
        assert parent_event_types.count("TaskStarted") == 2
        assert "EvidenceFound" in parent_event_types
        assert "InvestigationStateChanged" in parent_event_types
        assert parent_event_types[-1] == "TaskCompleted"
    finally:
        await redis.aclose()
        await engine.dispose()
