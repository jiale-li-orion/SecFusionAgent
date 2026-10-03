from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from apps.watch_runtime import RuntimeWatchWakeAdmission
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import (
    EvidenceLinkModel,
    KnowledgeRevisionModel,
    ObjectModel,
)
from packages.investigation.cases.service import CaseService
from packages.investigation.perception.contracts import (
    EvidenceRequirement,
    EvidenceTarget,
    PerceptionOperation,
    PerceptionRequest,
    PerceptionTarget,
)
from packages.investigation.runtime.contracts import (
    DelegationAction,
    DelegationResult,
    EnrichmentDelegationRequest,
    InvestigationFrame,
    PerceptionAction,
    StatePatchAction,
    StopAction,
    WaitAction,
)
from packages.investigation.runtime.role import InvestigationRoleRuntime
from packages.investigation.runtime.tasks import build_investigation_contract
from packages.investigation.runtime.watch import WatchWakeDisposition, WatchWakeService
from packages.investigation.state.contracts import (
    EvidenceNeedContract,
    ProposedState,
    StatePatch,
    StatePatchOperation,
)
from packages.investigation.state.service import InvestigationStateService
from packages.investigation.state.world_change import KnowledgeChangeNotice, WorldChangeService
from packages.investigation.storage.models import InvestigationCaseModel
from packages.runtime.budget import BudgetGovernor, BudgetLimits
from packages.runtime.execution.service import ExecutionRunService
from packages.runtime.policy.contracts import Authorization, PolicyDecisionPoint, PolicyObligation
from packages.runtime.policy.engine import RuntimePolicyRule, StaticPolicyEngine
from packages.shared.db import Base
from packages.sources.storage.models import SourceModel
from packages.task_runtime.contracts.execution import ExecutionEnvelope
from packages.task_runtime.contracts.models import (
    ContextManifest,
    ExecutionProfile,
    TaskEventType,
    TaskKind,
    TaskRunStatus,
)
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.models import TaskRunModel
from packages.task_runtime.storage.service import (
    create_task_run,
    get_task_context,
    get_task_run,
    list_task_events,
)

NOW = datetime(2026, 9, 27, 4, 30, tzinfo=UTC)
STREAM = "secfusion:task-events:investigation-role-test"


def _watch_policy(*, permit: bool = True, obligation: bool = False) -> StaticPolicyEngine:
    return StaticPolicyEngine(
        policy_revision="policy-v1",
        rules=[
            RuntimePolicyRule(
                policy_id="watch-resume-test",
                policy_revision="policy-v1",
                decision_points=[PolicyDecisionPoint.WATCH_RESUME],
                principal_patterns=["user:alice"],
                action_patterns=["resume_watch"],
                resource_patterns=["case:*"],
                authorization=Authorization.PERMIT if permit else Authorization.DENY,
                obligations=([PolicyObligation(kind="fresh_world_revision")] if obligation else []),
            )
        ],
    )


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed_case_need_and_evidence(session) -> tuple[str, str, str, str]:
    revision = KnowledgeRevisionModel(committed_at=NOW)
    session.add(revision)
    await session.flush()
    object_id = str(uuid4())
    session.add(
        ObjectModel(
            object_id=object_id,
            object_type="Vulnerability",
            canonical_key="cve:CVE-2026-61616",
            properties={},
            created_revision=revision.revision,
        )
    )
    source_id = "vendor-primary-investigation-test"
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
            definition_hash="investigation-test-source",
            managed_by="test",
            enabled=True,
            updated_at=NOW,
        )
    )
    await session.flush()
    observation_id = str(uuid4())
    session.add(
        ObservationModel(
            observation_id=observation_id,
            source_id=source_id,
            acquisition_run_id=None,
            acquisition_trigger="replay",
            external_object_id="vendor-advisory-1",
            external_revision="v1",
            canonical_url="https://example.invalid/advisory",
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
    evidence_id = str(uuid4())
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
    case = await CaseService(now=lambda: NOW).create(
        session,
        task_signature="verify-fix-boundary",
        target_object_ids=[object_id],
        goal="Verify whether the vendor evidence establishes the fixed release.",
        initial_knowledge_revision=revision.revision,
    )
    need_id = str(uuid4())
    await InvestigationStateService(now=lambda: NOW).open_evidence_need(
        session,
        case_id=case.case_id,
        base_case_revision=0,
        need_id=need_id,
        proposition_or_question="Vendor advisory establishes fixed release v0.22.0",
        purpose="verify_fix_release",
        target_objects=[object_id],
        evidence_contract=EvidenceNeedContract(
            required_source_roles=["primary"],
            min_independent_sources=1,
        ),
    )
    return case.case_id, object_id, need_id, evidence_id


async def _create_run(
    session,
    *,
    case_id: str,
    object_id: str,
    need_id: str,
    task_kind: TaskKind = TaskKind.VERIFY_VERSION_FIX,
    deadline_at: datetime | None = None,
) -> str:
    run_id = str(uuid4())
    contract = build_investigation_contract(
        task_contract_id=f"verify:{run_id}",
        principal="user:alice",
        task_kind=task_kind,
        case_id=case_id,
        target_object_ids=[object_id],
        required_need_ids=[need_id],
        policy_revision="policy-v1",
    )
    manifest = ContextManifest(
        context_id=f"context:{run_id}",
        context_revision=1,
        task_contract_ref=f"{contract.task_contract_id}@1",
        role_ref="InvestigationRole@1",
        case_ref=case_id,
        knowledge_revision=1,
        investigation_state_ref=f"case:{case_id}@1",
        object_refs=[object_id],
        policy_context_ref="policy-context:v1",
        capability_envelope_ref="capability:investigation-local-v1",
        budget_ref=f"budget:{run_id}",
    )
    await create_task_run(
        session,
        contract=contract,
        manifest=manifest,
        role=canonical_roles()["InvestigationRole"],
        execution_envelope_ref=f"execution:{run_id}",
        stream_name=STREAM,
        case_id=case_id,
        run_id=run_id,
        now=NOW,
    )
    await BudgetGovernor(now=lambda: NOW).create_account(
        session,
        account_id=manifest.budget_ref,
        task_run_id=run_id,
        limits=BudgetLimits(
            quantities={
                "agent_turns": Decimal("8"),
                "tool_calls": Decimal("4"),
            }
        ),
    )
    await ExecutionRunService(now=lambda: NOW).create(
        session,
        ExecutionEnvelope(
            execution_id=f"execution:{run_id}",
            task_contract_id=contract.task_contract_id,
            task_run_id=run_id,
            case_id=case_id,
            role_revision="InvestigationRole@1",
            context_manifest_revision=1,
            execution_profile=(
                ExecutionProfile.WATCH
                if task_kind is TaskKind.WATCH_INCIDENT
                else ExecutionProfile.VERIFY
            ),
            capability_scope=[],
            deadline_at=deadline_at or NOW.replace(hour=5),
            budget_ref=manifest.budget_ref,
            policy_revision=contract.policy_revision,
            identity_scope=["public"],
            network_policy="proxied",
            side_effect_policy="internal-state",
            sandbox_profile_revision="process_restricted@1",
        ),
    )
    return run_id


class _PerceiveThenPatchPlanner:
    async def next_action(self, frame: InvestigationFrame):
        assert frame.selected_need is not None
        object_id = frame.selected_need.target_objects[0]
        if frame.last_percept is None:
            return PerceptionAction(
                request=PerceptionRequest(
                    request_id=f"perceive:{frame.iteration}",
                    operation=PerceptionOperation.INSPECT,
                    target=PerceptionTarget(
                        evidence_targets=[EvidenceTarget(target_kind="object", target_id=object_id)]
                    ),
                    evidence_requirement=EvidenceRequirement(
                        required_source_roles=["primary"],
                        min_independent_sources=1,
                    ),
                )
            )
        assert frame.last_percept.evidence_handles
        assert not frame.last_percept.unresolved
        return StatePatchAction(
            patch=StatePatch(
                patch_id=f"patch:{frame.task_contract.task_contract_id}",
                case_id=frame.state.case_id,
                base_case_revision=frame.state.case_revision,
                producer="InvestigationRole:test-planner",
                operations=[
                    StatePatchOperation(
                        proposition="Vendor advisory establishes fixed release v0.22.0",
                        target_ref=f"object:{object_id}",
                        proposed_state=ProposedState.CONFIRMED,
                        evidence_refs=list(frame.last_percept.evidence_handles),
                        resolves_need_id=frame.selected_need.need_id,
                    )
                ],
            )
        )


class _WaitPlanner:
    async def next_action(self, frame: InvestigationFrame):
        del frame
        return WaitAction(reason="waiting_for_world_update")


class _PrematureSuccessPlanner:
    async def next_action(self, frame: InvestigationFrame):
        del frame
        return StopAction(reason="evidence_sufficient")


class _DeadlineSentinelPlanner:
    def __init__(self) -> None:
        self.calls = 0

    async def next_action(self, frame: InvestigationFrame):
        del frame
        self.calls += 1
        return StopAction(reason="planner_should_not_run_after_deadline")


class _DeadlineBoundary:
    async def blocking_reason(self, task_run_id: str) -> str | None:
        del task_run_id
        return "deadline_reached"


@pytest.mark.asyncio
async def test_investigation_role_enforces_execution_deadline_before_planning() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            case_id, object_id, need_id, _ = await _seed_case_need_and_evidence(session)
            run_id = await _create_run(
                session,
                case_id=case_id,
                object_id=object_id,
                need_id=need_id,
                deadline_at=NOW - timedelta(seconds=1),
            )
        planner = _DeadlineSentinelPlanner()
        outcome = await InvestigationRoleRuntime(
            factory,
            planner,
            execution_boundary=_DeadlineBoundary(),
            stream_name=STREAM,
            now=lambda: NOW,
        ).run(run_id)
        assert outcome.run_status is TaskRunStatus.BLOCKED
        assert outcome.result.stop_reason == "deadline_reached"
        assert planner.calls == 0
    finally:
        await engine.dispose()


class _DelegatePlanner:
    async def next_action(self, frame: InvestigationFrame):
        assert frame.selected_need is not None
        return DelegationAction(
            request=EnrichmentDelegationRequest(
                delegation_id="fill-fix-remediation",
                target_object_id=frame.selected_need.target_objects[0],
                cve_id="CVE-2026-61616",
                required_dimensions=["fix_remediation"],
                reason="missing durable fix boundary evidence",
            )
        )


class _DelegationPort:
    def __init__(self) -> None:
        self.calls: list[tuple[str, EnrichmentDelegationRequest]] = []

    async def delegate_enrichment(self, *, parent_run_id, request):
        self.calls.append((parent_run_id, request))
        return DelegationResult(
            child_run_id="child-enrichment-1",
            child_context_ref="context:child-enrichment-1@1",
            child_execution_ref="execution:child-enrichment-1",
        )


@pytest.mark.asyncio
async def test_investigation_role_perceives_evidence_commits_state_and_completes() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            case_id, object_id, need_id, evidence_id = await _seed_case_need_and_evidence(session)
            run_id = await _create_run(
                session,
                case_id=case_id,
                object_id=object_id,
                need_id=need_id,
            )

        outcome = await InvestigationRoleRuntime(
            factory,
            _PerceiveThenPatchPlanner(),
            stream_name=STREAM,
            now=lambda: NOW,
        ).run(run_id)

        assert outcome.run_status is TaskRunStatus.COMPLETED
        assert outcome.result.resolved_need_ids == [need_id]
        assert outcome.result.open_need_ids == []
        assert outcome.result.final_case_revision == 4

        async with factory() as session:
            state = await InvestigationStateService(now=lambda: NOW).get_state(session, case_id)
            assert state.case_revision == 4
            assert len(state.confirmed) == 1
            assert state.confirmed[0].evidence_refs == [evidence_id]
            events = await list_task_events(session, run_id)
        assert [event.event_type.value for event in events] == [
            "TaskCreated",
            "TaskPatched",
            "TaskStarted",
            "EvidenceFound",
            "ContextUpdated",
            "InvestigationStateChanged",
            "ContextUpdated",
            "TaskCompleted",
        ]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_watch_resume_policy_fails_closed_before_new_task_run_is_created() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            case_id, object_id, need_id, _ = await _seed_case_need_and_evidence(session)
            old_run_id = await _create_run(
                session,
                case_id=case_id,
                object_id=object_id,
                need_id=need_id,
                task_kind=TaskKind.WATCH_INCIDENT,
            )
        await InvestigationRoleRuntime(
            factory,
            _WaitPlanner(),
            stream_name=STREAM,
            now=lambda: NOW,
        ).run(old_run_id)

        async with factory() as session, session.begin():
            revision = KnowledgeRevisionModel(committed_at=NOW)
            session.add(revision)
            await session.flush()
            impacts = await WorldChangeService(now=lambda: NOW).process(
                session,
                KnowledgeChangeNotice(revision=revision.revision, object_ids=[object_id]),
            )
            denied = await WatchWakeService(
                admission_port=RuntimeWatchWakeAdmission(
                    _watch_policy(permit=False),
                    now=lambda: NOW,
                ),
                stream_name=STREAM,
                now=lambda: NOW,
            ).spawn_for_world_change(
                session,
                impact=impacts[0],
                trigger_ref=f"knowledge-revision:{revision.revision}",
            )
            assert denied.disposition is WatchWakeDisposition.POLICY_DENIED
            assert denied.policy_authorization == Authorization.DENY.value
            assert denied.run_id is not None
            assert await session.get(TaskRunModel, denied.run_id) is None

            obligation_blocked = await WatchWakeService(
                admission_port=RuntimeWatchWakeAdmission(
                    _watch_policy(obligation=True),
                    now=lambda: NOW,
                ),
                stream_name=STREAM,
                now=lambda: NOW,
            ).spawn_for_world_change(
                session,
                impact=impacts[0],
                trigger_ref=f"knowledge-revision:{revision.revision}:obligation",
            )
            assert (
                obligation_blocked.disposition is WatchWakeDisposition.POLICY_OBLIGATION_UNSATISFIED
            )
            assert obligation_blocked.run_id is not None
            assert await session.get(TaskRunModel, obligation_blocked.run_id) is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_relevant_world_change_spawns_new_watch_run_and_replay_is_idempotent() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            case_id, object_id, need_id, _ = await _seed_case_need_and_evidence(session)
            old_run_id = await _create_run(
                session,
                case_id=case_id,
                object_id=object_id,
                need_id=need_id,
                task_kind=TaskKind.WATCH_INCIDENT,
            )
        parked = await InvestigationRoleRuntime(
            factory,
            _WaitPlanner(),
            stream_name=STREAM,
            now=lambda: NOW,
        ).run(old_run_id)
        assert parked.run_status is TaskRunStatus.COMPLETED

        async with factory() as session, session.begin():
            revision = KnowledgeRevisionModel(committed_at=NOW)
            session.add(revision)
            await session.flush()
            impacts = await WorldChangeService(now=lambda: NOW).process(
                session,
                KnowledgeChangeNotice(
                    revision=revision.revision,
                    object_ids=[object_id],
                ),
            )
            assert len(impacts) == 1 and impacts[0].case_activated is True
            watch_wake = WatchWakeService(
                admission_port=RuntimeWatchWakeAdmission(
                    _watch_policy(),
                    now=lambda: NOW,
                ),
                stream_name=STREAM,
                now=lambda: NOW,
            )
            wake = await watch_wake.spawn_for_world_change(
                session,
                impact=impacts[0],
                trigger_ref=f"knowledge-revision:{revision.revision}",
            )
            assert wake.disposition is WatchWakeDisposition.QUEUED
            assert wake.run_id is not None and wake.run_id != old_run_id

            new_run = await get_task_run(session, wake.run_id)
            new_context = await get_task_context(session, wake.run_id)
            old_context = await get_task_context(session, old_run_id)
            new_budget = await BudgetGovernor(now=lambda: NOW).snapshot(
                session,
                new_context.budget_ref,
            )
            old_budget = await BudgetGovernor(now=lambda: NOW).snapshot(
                session,
                old_context.budget_ref,
            )
            new_execution = await ExecutionRunService(now=lambda: NOW).get(
                session,
                new_run.execution_envelope_ref,
            )
            old_run = await get_task_run(session, old_run_id)
            old_execution = await ExecutionRunService(now=lambda: NOW).get(
                session,
                old_run.execution_envelope_ref,
            )
            assert new_run.status is TaskRunStatus.QUEUED
            assert new_context.parent_context_id == old_context.context_id
            assert new_context.knowledge_revision == revision.revision
            assert new_context.investigation_state_ref == f"case:{case_id}@1"
            assert new_context.skill_selection_refs == []
            assert new_context.budget_ref == f"budget:{wake.run_id}"
            assert new_budget.limits == old_budget.limits
            assert new_execution.execution_profile is ExecutionProfile.WATCH
            assert new_execution.capability_scope == old_execution.capability_scope
            assert new_execution.identity_scope == old_execution.identity_scope
            assert new_execution.network_policy == old_execution.network_policy
            assert new_execution.trace_context["watch_previous_run_id"] == old_run_id
            assert (
                new_execution.trace_context["watch_policy_decision_ref"] == wake.policy_decision_ref
            )

            replay = await watch_wake.spawn_for_world_change(
                session,
                impact=impacts[0],
                trigger_ref=f"knowledge-revision:{revision.revision}",
            )
            assert replay.disposition is WatchWakeDisposition.REPLAY
            assert replay.run_id == wake.run_id

            assert old_run.status is TaskRunStatus.COMPLETED
            assert old_run.stop_reason == "waiting_for_world_update"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_watch_episode_parks_case_and_finishes_run_while_waiting_for_world_update() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            case_id, object_id, need_id, _ = await _seed_case_need_and_evidence(session)
            run_id = await _create_run(
                session,
                case_id=case_id,
                object_id=object_id,
                need_id=need_id,
                task_kind=TaskKind.WATCH_INCIDENT,
            )
        outcome = await InvestigationRoleRuntime(
            factory,
            _WaitPlanner(),
            stream_name=STREAM,
            now=lambda: NOW,
        ).run(run_id)
        assert outcome.run_status is TaskRunStatus.COMPLETED
        assert outcome.result.open_need_ids == [need_id]
        assert outcome.result.stop_reason == "waiting_for_world_update"

        async with factory() as session:
            case = await session.get(InvestigationCaseModel, case_id)
            run = await get_task_run(session, run_id)
            events = await list_task_events(session, run_id)
        assert case is not None and case.status == "waiting"
        assert run.status is TaskRunStatus.COMPLETED
        assert events[-1].event_type is TaskEventType.TASK_COMPLETED
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_investigation_role_delegates_then_waits_for_child() -> None:
    engine, factory = await _database()
    delegation = _DelegationPort()
    try:
        async with factory() as session, session.begin():
            case_id, object_id, need_id, _ = await _seed_case_need_and_evidence(session)
            run_id = await _create_run(
                session,
                case_id=case_id,
                object_id=object_id,
                need_id=need_id,
            )
        outcome = await InvestigationRoleRuntime(
            factory,
            _DelegatePlanner(),
            delegation_port=delegation,
            stream_name=STREAM,
            now=lambda: NOW,
        ).run(run_id)
        assert outcome.run_status is TaskRunStatus.WAITING_DEPENDENCY
        assert outcome.result.stop_reason == "task_dependency:child-enrichment-1"
        assert [item[0] for item in delegation.calls] == [run_id]
        assert delegation.calls[0][1].required_dimensions == ["fix_remediation"]

        async with factory() as session:
            events = await list_task_events(session, run_id)
        assert [event.event_type.value for event in events][-2:] == [
            "Progress",
            "NeedContext",
        ]
        assert events[-2].payload_ref == "child-task:child-enrichment-1"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_planner_cannot_bypass_completion_predicate_with_success_stop_reason() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            case_id, object_id, need_id, _ = await _seed_case_need_and_evidence(session)
            run_id = await _create_run(
                session,
                case_id=case_id,
                object_id=object_id,
                need_id=need_id,
            )
        outcome = await InvestigationRoleRuntime(
            factory,
            _PrematureSuccessPlanner(),
            stream_name=STREAM,
            now=lambda: NOW,
        ).run(run_id)
        assert outcome.run_status is TaskRunStatus.BLOCKED
        assert outcome.result.open_need_ids == [need_id]
        assert outcome.result.stop_reason == (
            "completion_predicate_unsatisfied:evidence_sufficient"
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_investigation_role_can_wait_without_completing_task_run() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            case_id, object_id, need_id, _ = await _seed_case_need_and_evidence(session)
            run_id = await _create_run(
                session,
                case_id=case_id,
                object_id=object_id,
                need_id=need_id,
            )
        outcome = await InvestigationRoleRuntime(
            factory,
            _WaitPlanner(),
            stream_name=STREAM,
            now=lambda: NOW,
        ).run(run_id)
        assert outcome.run_status is TaskRunStatus.WAITING_DEPENDENCY
        assert outcome.result.open_need_ids == [need_id]
        assert outcome.result.stop_reason == "waiting_for_world_update"
    finally:
        await engine.dispose()
