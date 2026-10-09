from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import KnowledgeRevisionModel, ObjectModel
from packages.investigation.cases.service import CaseService
from packages.investigation.perception.contracts import (
    EvidenceRequirement,
    EvidenceTarget,
    Percept,
    PerceptionOperation,
    PerceptionRequest,
    PerceptionTarget,
)
from packages.investigation.runtime.contracts import (
    InvestigationFrame,
    InvestigationPlannerDecision,
    PerceptionAction,
    StatePatchAction,
)
from packages.investigation.runtime.planner import (
    ModelInvestigationPlanner,
    PlannerCapabilityContext,
    _visible_object_ref_aliases,
)
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
from packages.shared.db import Base
from packages.shared.model_provider import StructuredModelRequest
from packages.sources.storage.models import SourceModel
from packages.task_runtime.context.materializer import (
    ContextMaterializer,
    FragmentCacheClass,
    FragmentTrustClass,
    MaterializedFragment,
)
from packages.task_runtime.contracts.models import ContextManifest, TaskKind
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.service import (
    create_task_run,
    get_task_context,
    list_task_events,
)

NOW = datetime(2026, 9, 27, 12, 30, tzinfo=UTC)
STREAM = "secfusion:task-events:model-planner-test"


def test_visible_object_ref_aliases_resolve_nested_relation_target_canonical_key() -> None:
    aliases = _visible_object_ref_aliases(
        [
            MaterializedFragment.build(
                kind="knowledge_object",
                source_ref="vulnerability-id",
                source_revision="1",
                trust_class=FragmentTrustClass.EVIDENCE_REFERENCE,
                cache_class=FragmentCacheClass.STATE_DYNAMIC,
                content={
                    "object_id": "vulnerability-id",
                    "canonical_key": "cve:CVE-2026-86439",
                    "relations": [
                        {
                            "relation_type": "fixed-version",
                            "target": {
                                "object_id": "version-object-id",
                                "canonical_key": "software-version:npm:knowns:0.30.0",
                            },
                        }
                    ],
                },
            )
        ]
    )
    assert aliases["software-version:npm:knowns:0.30.0"] == "object:version-object-id"
    assert aliases["version-object-id"] == "object:version-object-id"


class _CapabilityContext:
    async def resolve(self, *, task_run_id, frame):
        del task_run_id, frame
        ref = "capability-view:verify-v1"
        return PlannerCapabilityContext(
            capability_view_revision="verify-v1",
            execution_profile_revision="VERIFY@1",
            visible_capability_classes=["evidence.read", "graph.read"],
            disclosure_fragments=[
                MaterializedFragment.build(
                    kind="capability_cards",
                    source_ref=ref,
                    source_revision="verify-v1",
                    trust_class=FragmentTrustClass.RUNTIME_CONTROL,
                    cache_class=FragmentCacheClass.TASK_STABLE,
                    content={
                        "cards": [
                            {"capability_class": "evidence.read"},
                            {"capability_class": "graph.read"},
                        ]
                    },
                )
            ],
            runtime_disclosure_refs={ref},
        )


class _RoleModelProvider:
    name = "planner-role-test"
    version = "v1"

    def __init__(self, *, object_id: str, evidence_id: str, need_id: str) -> None:
        self._object_id = object_id
        self._evidence_id = evidence_id
        self._need_id = need_id
        self.requests: list[StructuredModelRequest] = []

    async def generate_structured(self, request, response_model):
        assert response_model is InvestigationPlannerDecision
        self.requests.append(request)
        if len(self.requests) == 1:
            return InvestigationPlannerDecision(
                action=PerceptionAction(
                    request=PerceptionRequest(
                        request_id="model-request",
                        operation=PerceptionOperation.INSPECT,
                        target=PerceptionTarget(
                            evidence_targets=[
                                EvidenceTarget(
                                    target_kind="object",
                                    target_id=self._object_id,
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
        return InvestigationPlannerDecision(
            action=StatePatchAction(
                patch=StatePatch(
                    patch_id="model-patch",
                    case_id="model-case",
                    base_case_revision=0,
                    producer="model",
                    operations=[
                        StatePatchOperation(
                            proposition="Primary advisory establishes the fixed release.",
                            target_ref=self._object_id,
                            proposed_state=ProposedState.CONFIRMED,
                            evidence_refs=[self._evidence_id],
                            resolves_need_id=self._need_id,
                        )
                    ],
                )
            )
        )


class _ModelProvider:
    name = "planner-test"
    version = "v1"

    def __init__(self) -> None:
        self.requests: list[StructuredModelRequest] = []

    async def generate_structured(self, request, response_model):
        assert response_model is InvestigationPlannerDecision
        self.requests.append(request)
        if len(self.requests) == 1:
            return InvestigationPlannerDecision(
                action=PerceptionAction(
                    request=PerceptionRequest(
                        request_id="model-controlled-request-id",
                        case_id="model-controlled-case",
                        need_id="model-controlled-need",
                        operation=PerceptionOperation.INSPECT,
                        target=PerceptionTarget(object_id="placeholder"),
                        budget_ref="model-controlled-budget",
                    )
                )
            )
        return InvestigationPlannerDecision(
            action=StatePatchAction(
                patch=StatePatch(
                    patch_id="model-controlled-patch-id",
                    case_id="model-controlled-case",
                    base_case_revision=0,
                    producer="model-controlled-producer",
                    operations=[
                        StatePatchOperation(
                            proposition="Release v1.2.3 contains the fix commit.",
                            target_ref="object:placeholder",
                            proposed_state=ProposedState.CONFIRMED,
                            evidence_refs=["evidence:placeholder"],
                        )
                    ],
                )
            )
        )


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed(factory):
    state_service = InvestigationStateService(now=lambda: NOW)
    async with factory() as session, session.begin():
        revision = KnowledgeRevisionModel(committed_at=NOW)
        session.add(revision)
        await session.flush()
        object_id = str(uuid4())
        session.add(
            ObjectModel(
                object_id=object_id,
                object_type="Vulnerability",
                canonical_key="cve:CVE-2026-81818",
                properties={"display_name": "CVE-2026-81818"},
                created_revision=revision.revision,
            )
        )
        await session.flush()
        case = await CaseService(now=lambda: NOW).create(
            session,
            task_signature="verify-fix-model-planner",
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
            evidence_contract=EvidenceNeedContract(required_source_roles=["primary"]),
        )
        run_id = str(uuid4())
        contract = build_investigation_contract(
            task_contract_id=f"verify:{run_id}",
            principal="user:test",
            task_kind=TaskKind.VERIFY_VERSION_FIX,
            case_id=case.case_id,
            target_object_ids=[object_id],
            required_need_ids=[need.need.need_id],
            policy_revision="policy-v1",
        )
        manifest = ContextManifest(
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
            budget_ref=f"budget:{run_id}",
        )
        await create_task_run(
            session,
            contract=contract,
            manifest=manifest,
            role=canonical_roles()["InvestigationRole"],
            execution_envelope_ref=f"execution:{run_id}",
            stream_name=STREAM,
            case_id=case.case_id,
            run_id=run_id,
            now=NOW,
        )
        skill = seeded_skills()[0]
        validated = skill.model_copy(
            update={
                "manifest": skill.manifest.model_copy(
                    update={
                        "status": SkillStatus.VALIDATED,
                        "validation_ref": "m7-replay:verify-fix:v1",
                    }
                )
            }
        )
        await SkillStore(now=lambda: NOW).publish(session, validated)
        state = await state_service.get_state(session, case.case_id)
    return run_id, object_id, contract, state, need.need, validated.manifest.ref


async def _attach_primary_evidence(factory, *, object_id: str) -> str:
    source_id = f"vendor-primary-model-planner-{uuid4().hex}"
    observation_id = str(uuid4())
    evidence_id = str(uuid4())
    async with factory() as session, session.begin():
        session.add(
            SourceModel(
                source_id=source_id,
                adapter_type="fixture",
                source_class="vendor_security_material",
                authority_scope=["fix_status"],
                source_role="primary",
                source_family="vendor",
                upstream_source=None,
                access_mode="fixture",
                update_semantics="append",
                discovery_method={},
                time_semantics={},
                identity_semantics={},
                auth_ref=None,
                rate_limit_policy={},
                access_rights={},
                retention_mode="durable_managed",
                schedule_policy={},
                schema_version="1",
                definition_hash=f"model-planner-{source_id}",
                managed_by="test",
                enabled=True,
                updated_at=NOW,
            )
        )
        await session.flush()
        session.add(
            ObservationModel(
                observation_id=observation_id,
                source_id=source_id,
                acquisition_run_id=None,
                acquisition_trigger="replay",
                external_object_id="vendor-advisory-model-planner",
                external_revision="v1",
                canonical_url="https://example.invalid/model-planner-advisory",
                published_at=NOW,
                updated_at=NOW,
                observed_at=NOW,
                content_hash=uuid4().hex + uuid4().hex,
                request_metadata={},
                request_metadata_captured=True,
                idempotency_key=uuid4().hex + uuid4().hex,
                created_at=NOW,
            )
        )
        await session.flush()
        from packages.intelligence.storage.knowledge_models import EvidenceLinkModel

        session.add(
            EvidenceLinkModel(
                evidence_link_id=evidence_id,
                target_kind="object",
                target_id=object_id,
                observation_id=observation_id,
                artifact_id=None,
                locator={"kind": "fixture", "field": "fixed_release"},
                locator_hash=uuid4().hex + uuid4().hex,
            )
        )
    return evidence_id


@pytest.mark.asyncio
async def test_model_planner_materializes_skill_capability_and_runtime_owned_action_ids() -> None:
    engine, factory = await _database()
    provider = _ModelProvider()
    try:
        run_id, _object_id, contract, state, need, skill_ref = await _seed(factory)
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
            capability_context_provider=_CapabilityContext(),
            stream_name=STREAM,
        )
        first_frame = InvestigationFrame(
            task_run_id=run_id,
            task_contract=contract,
            state=state,
            selected_need=need,
            iteration=1,
        )
        first = await planner.next_action(first_frame)
        assert isinstance(first, PerceptionAction)
        assert first.request.request_id.startswith(f"perception:{run_id}:1:")
        assert first.request.case_id == state.case_id
        assert first.request.need_id == need.need_id
        assert first.request.budget_ref == f"budget:{run_id}"

        async with factory() as session:
            manifest = await get_task_context(session, run_id)
        assert manifest.context_revision == 2
        assert manifest.skill_selection_refs == [skill_ref]
        first_request = provider.requests[0]
        assert '"kind":"skill_manifest"' in first_request.system_instruction
        assert '"kind":"skill_procedure"' in first_request.system_instruction
        assert '"kind":"capability_cards"' in first_request.system_instruction
        assert first_request.metadata["assembly_hash"]

        percept = Percept(
            percept_id="percept:verify-fix-1",
            request_id=first.request.request_id,
            observation_handles=["observation:ephemeral-1"],
            unresolved=["required_source_role_missing:primary"],
            cost={"capability_calls": 1},
        )
        second_frame = first_frame.model_copy(update={"iteration": 2, "last_percept": percept})
        second = await planner.next_action(second_frame)
        assert isinstance(second, StatePatchAction)
        assert second.patch.patch_id.startswith(f"patch:{run_id}:2:")
        assert second.patch.case_id == state.case_id
        assert second.patch.base_case_revision == state.case_revision
        assert second.patch.producer == "InvestigationRole:model:planner-test@v1"
        assert second.patch.model_prompt_revision == provider.requests[1].metadata["assembly_hash"]
        assert second.patch.operations[0].target_ref == "object:placeholder"
        assert "model-controlled" not in second.patch.patch_id
        second_request = provider.requests[1]
        assert second_request.metadata["model_payload_persistence"] == (
            "redacted_runtime_artifact"
        )
        data = str(second_request.data)
        assert "percept:verify-fix-1" in data
        assert "observation:ephemeral-1" in data
        assert "percept:verify-fix-1" not in second_request.system_instruction
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_model_planner_runs_full_investigation_role_loop_through_state_gate() -> None:
    engine, factory = await _database()
    try:
        run_id, object_id, _contract, _state, need, skill_ref = await _seed(factory)
        evidence_id = await _attach_primary_evidence(factory, object_id=object_id)
        provider = _RoleModelProvider(
            object_id=object_id,
            evidence_id=evidence_id,
            need_id=need.need_id,
        )
        planner = ModelInvestigationPlanner(
            factory,
            provider,
            materializer=ContextMaterializer(
                platform_invariant_revision="platform-v1",
                platform_invariant={
                    "state_write": "StatePatch gate",
                    "ephemeral_observation_is_not_evidence": True,
                },
            ),
            capability_context_provider=_CapabilityContext(),
            stream_name=STREAM,
        )
        outcome = await InvestigationRoleRuntime(
            factory,
            planner,
            stream_name=STREAM,
            now=lambda: NOW,
        ).run(run_id)

        assert outcome.run_status.value == "completed"
        assert outcome.result.resolved_need_ids == [need.need_id]
        assert outcome.result.final_case_revision == 4
        assert len(provider.requests) == 2

        async with factory() as session:
            state = await InvestigationStateService(now=lambda: NOW).get_state(
                session, outcome.result.case_id
            )
            manifest = await get_task_context(session, run_id)
            events = await list_task_events(session, run_id)
        assert state.case_revision == 4
        assert len(state.confirmed) == 1
        assert state.confirmed[0].target_ref == f"object:{object_id}"
        assert state.confirmed[0].evidence_refs == [evidence_id]
        assert manifest.investigation_state_ref == f"case:{state.case_id}@4"
        assert manifest.context_revision == 4
        assert manifest.skill_selection_refs == [skill_ref]
        assert [event.event_type.value for event in events] == [
            "TaskCreated",
            "TaskPatched",
            "TaskStarted",
            "ContextUpdated",
            "EvidenceFound",
            "ContextUpdated",
            "InvestigationStateChanged",
            "ContextUpdated",
            "TaskCompleted",
        ]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_research_object_planner_excludes_cve_only_delegation() -> None:
    from packages.investigation.runtime.planner import SourceInvestigationPlannerDecision

    class SourceProvider:
        name = "source-planner-test"
        version = "1"

        async def generate_structured(self, request, response_model):
            assert response_model is SourceInvestigationPlannerDecision
            assert request.metadata["prompt_revision"] == "investigation-model-v2-source"
            assert "source_investigation_guidance" in request.system_instruction
            schema = response_model.model_json_schema()
            assert "DelegationAction" not in schema["$defs"]
            return response_model(action=PerceptionAction(request=PerceptionRequest(
                request_id="source-read", operation=PerceptionOperation.SEARCH,
                target=PerceptionTarget(query_text="source mechanism"),
            )))

    engine, factory = await _database()
    try:
        run_id, object_id, contract, state, need, _ = await _seed(factory)
        async with factory() as session, session.begin():
            obj = await session.get(ObjectModel, object_id)
            obj.object_type = "ResearchWork"
        planner = ModelInvestigationPlanner(factory, SourceProvider(),
            materializer=ContextMaterializer(
                platform_invariant_revision="source-v1", platform_invariant={"source": "read"},
            ), stream_name=STREAM)
        action = await planner.next_action(InvestigationFrame(
            task_run_id=run_id, task_contract=contract, state=state,
            selected_need=need, iteration=1,
        ))
        assert isinstance(action, PerceptionAction)
        assert action.request.target.query_text == "source mechanism"
    finally:
        await engine.dispose()
