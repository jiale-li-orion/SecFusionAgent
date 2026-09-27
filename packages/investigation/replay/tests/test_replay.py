from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.replay_runtime import ReplayCaptureRuntime
from apps.runtime_models import register_runtime_models
from packages.intelligence.storage.knowledge_models import KnowledgeRevisionModel
from packages.investigation.cases.service import CaseService
from packages.investigation.replay import (
    ReplayCheckpointService,
    ReplayExpectation,
    ReplayIntervention,
    ReplayInterventionKind,
    ReplayLoopTopology,
    ReplayObservation,
    ReplayWorldUnavailable,
    apply_replay_intervention,
    evaluate_replay_protocol,
)
from packages.investigation.state.snapshot import InvestigationSnapshotService
from packages.investigation.trajectory.service import TrajectoryService, list_events
from packages.runtime.budget import BudgetGovernor, BudgetLimits
from packages.runtime.execution.service import ExecutionRunService
from packages.shared.db import Base
from packages.task_runtime.contracts.execution import ExecutionEnvelope
from packages.task_runtime.contracts.models import (
    ContextManifest,
    DelegationCeiling,
    EffectCeiling,
    ExecutionProfile,
    TaskContract,
    TaskKind,
)
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.service import create_task_run

NOW = datetime(2026, 9, 27, 20, 0, tzinfo=UTC)
STREAM = "secfusion:task-events:replay-test"


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed_replayable_run(factory):
    async with factory() as session, session.begin():
        revision = KnowledgeRevisionModel(committed_at=NOW)
        session.add(revision)
        await session.flush()
        case = await CaseService(now=lambda: NOW).create(
            session,
            task_signature="verify-fix-boundary-replay",
            target_object_ids=[],
            goal="Verify a fix boundary from pinned evidence.",
            initial_knowledge_revision=revision.revision,
        )
        contract = TaskContract(
            task_contract_id="replay-contract-1",
            contract_revision=1,
            principal="user:test",
            task_kind=TaskKind.VERIFY_VERSION_FIX,
            target_resources=[f"case:{case.case_id}"],
            desired_state={"case_id": case.case_id, "required_need_ids": ["need-1"]},
            evidence_contract={"authority": "m1_m3_evidence_world"},
            output_contract={"result_type": "InvestigationTaskResult"},
            temporal_contract={"scope": "current"},
            effect_ceiling=EffectCeiling.INTERNAL_STATE,
            delegation_ceiling=DelegationCeiling(),
            completion_predicate={"type": "evidence_needs_resolved"},
            policy_revision="policy-v1",
        )
        run_id = "replay-run-1"
        manifest = ContextManifest(
            context_id="replay-context-1",
            context_revision=1,
            task_contract_ref="replay-contract-1@1",
            role_ref="InvestigationRole@1",
            case_ref=case.case_id,
            knowledge_revision=revision.revision,
            investigation_state_ref=f"case:{case.case_id}@0",
            policy_context_ref="policy-context:policy-v1",
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
        budget = BudgetGovernor(now=lambda: NOW)
        await budget.create_account(
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
        await budget.reserve(
            session,
            account_id=manifest.budget_ref,
            reservation_group_id="replay-seed-reservation",
            quantities={"agent_turns": Decimal("1")},
        )
        await ExecutionRunService(now=lambda: NOW).create(
            session,
            ExecutionEnvelope(
                execution_id=f"execution:{run_id}",
                task_contract_id=contract.task_contract_id,
                task_run_id=run_id,
                case_id=case.case_id,
                role_revision="InvestigationRole@1",
                context_manifest_revision=1,
                execution_profile=ExecutionProfile.VERIFY,
                capability_scope=["repo.read", "evidence.promote"],
                deadline_at=NOW + timedelta(minutes=5),
                budget_ref=manifest.budget_ref,
                policy_revision="policy-v1",
                identity_scope=["public"],
                network_policy="proxied",
                side_effect_policy="internal-state",
                sandbox_profile_revision="process_restricted@1",
            ),
        )
        trajectory = await TrajectoryService(now=lambda: NOW).start(
            session,
            case_id=case.case_id,
        )
        await TrajectoryService(now=lambda: NOW).append_event(
            session,
            trajectory_id=trajectory.trajectory_id,
            event_type="planner_action",
            payload={"action": "inspect_fix_boundary"},
        )
        snapshot = await InvestigationSnapshotService().create(
            session,
            case_id=case.case_id,
            policy_revision="policy-v1",
            knowledge_revision=revision.revision,
            capability_registry_revision="cap-registry-v7",
            model_revision="model-v3",
            prompt_assembly_revision="prompt-v5",
            source_availability_snapshot={"github": "available", "osv": "available"},
            created_at=NOW,
        )
    return case.case_id, run_id, trajectory.trajectory_id, snapshot.snapshot_id


@pytest.mark.asyncio
async def test_replay_checkpoint_pins_task_context_trajectory_and_runtime_idempotently() -> None:
    engine, factory = await _database()
    try:
        _, run_id, trajectory_id, snapshot_id = await _seed_replayable_run(factory)
        async with factory() as session, session.begin():
            capture = await ReplayCaptureRuntime().capture(
                session,
                snapshot_id=snapshot_id,
                trajectory_id=trajectory_id,
                task_run_id=run_id,
                skill_refs=["skill:investigation.VerifyFixBoundary@1"],
                loop_topology=ReplayLoopTopology.MULTI_LOOP_DELEGATED,
            )
            replay = await ReplayCaptureRuntime().capture(
                session,
                snapshot_id=snapshot_id,
                trajectory_id=trajectory_id,
                task_run_id=run_id,
                skill_refs=["skill:investigation.VerifyFixBoundary@1"],
                loop_topology=ReplayLoopTopology.MULTI_LOOP_DELEGATED,
            )

            assert capture.replay is False
            assert replay.replay is True
            assert replay.checkpoint.checkpoint_id == capture.checkpoint.checkpoint_id
            checkpoint = capture.checkpoint
            assert checkpoint.task_event_seq == 1
            assert checkpoint.trajectory_ordinal == 1
            assert checkpoint.context_manifest_ref == "replay-context-1@1"
            assert checkpoint.knowledge_revision == 1
            assert checkpoint.runtime.policy_revision == "policy-v1"
            assert checkpoint.runtime.sandbox_profile_revision == "process_restricted@1"
            assert checkpoint.runtime.budget_limits == {
                "agent_turns": "8",
                "tool_calls": "4",
            }
            assert checkpoint.runtime.budget_reserved == {"agent_turns": "1"}

            loaded = await ReplayCheckpointService().get(
                session,
                trajectory_id=trajectory_id,
                checkpoint_id=checkpoint.checkpoint_id,
            )
            assert loaded == checkpoint
            events = await list_events(session, trajectory_id)
            assert [event.event_type for event in events] == [
                "planner_action",
                "replay_checkpoint",
            ]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_replay_prepare_restores_historical_m4_state_and_fails_closed_on_world_drift() -> (
    None
):
    engine, factory = await _database()
    try:
        case_id, run_id, trajectory_id, snapshot_id = await _seed_replayable_run(factory)
        async with factory() as session, session.begin():
            capture = await ReplayCaptureRuntime().capture(
                session,
                snapshot_id=snapshot_id,
                trajectory_id=trajectory_id,
                task_run_id=run_id,
                skill_refs=["skill:investigation.VerifyFixBoundary@1"],
                loop_topology=ReplayLoopTopology.SINGLE_LOOP,
            )
            prepared = await ReplayCheckpointService().prepare(
                session,
                trajectory_id=trajectory_id,
                checkpoint_id=capture.checkpoint.checkpoint_id,
                intervention=ReplayIntervention(
                    kind=ReplayInterventionKind.LOOP_TOPOLOGY,
                    replacement=ReplayLoopTopology.MULTI_LOOP_DELEGATED.value,
                    rationale="controlled topology replay",
                ),
            )
            assert prepared.state.case_id == case_id
            assert prepared.state.case_revision == capture.checkpoint.case_revision == 0
            assert prepared.world_revision == capture.checkpoint.knowledge_revision == 1
            assert prepared.environment.loop_topology is ReplayLoopTopology.MULTI_LOOP_DELEGATED

            session.add(KnowledgeRevisionModel(committed_at=NOW + timedelta(seconds=1)))
            await session.flush()
            with pytest.raises(ReplayWorldUnavailable, match="historical Knowledge projection"):
                await ReplayCheckpointService().prepare(
                    session,
                    trajectory_id=trajectory_id,
                    checkpoint_id=capture.checkpoint.checkpoint_id,
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_snapshot_rejects_future_world_revision() -> None:
    engine, factory = await _database()
    try:
        case_id, _, _, _ = await _seed_replayable_run(factory)
        async with factory() as session, session.begin():
            with pytest.raises(ValueError, match="future knowledge revision"):
                await InvestigationSnapshotService().create(
                    session,
                    case_id=case_id,
                    policy_revision="policy-v1",
                    knowledge_revision=99,
                )
    finally:
        await engine.dispose()


def test_replay_interventions_change_exactly_one_control_dimension() -> None:
    from packages.investigation.replay.contracts import ReplayCheckpoint, ReplayRuntimeBinding

    checkpoint = ReplayCheckpoint(
        checkpoint_id="replay-checkpoint:test",
        case_id="case-1",
        snapshot_id="snapshot-1",
        case_revision=3,
        knowledge_revision=7,
        task_run_id="run-1",
        task_contract_ref="contract-1@1",
        context_manifest_ref="context-1@2",
        task_event_seq=4,
        trajectory_id="trajectory-1",
        trajectory_ordinal=8,
        role_ref="InvestigationRole@1",
        runtime=ReplayRuntimeBinding(
            task_run_id="run-1",
            execution_envelope_ref="execution:run-1",
            execution_profile="VERIFY",
            policy_revision="policy-v1",
            sandbox_profile_revision="process_restricted@1",
            network_policy="proxied",
            side_effect_policy="internal-state",
            budget_ref="budget:run-1",
            budget_limits={"agent_turns": "8"},
        ),
        capability_registry_revision="cap-v1",
        skill_refs=["skill:base@1"],
        loop_topology=ReplayLoopTopology.SINGLE_LOOP,
        created_at=NOW,
    )
    baseline = apply_replay_intervention(checkpoint, None)
    cases = [
        (ReplayInterventionKind.LOOP_TOPOLOGY, "multi_loop_delegated", "loop_topology"),
        (ReplayInterventionKind.CONTEXT_HANDOFF, "summary", "context_handoff_mode"),
        (ReplayInterventionKind.POLICY, "policy-v2", "policy_revision"),
        (ReplayInterventionKind.SANDBOX, "microvm_untrusted@1", "sandbox_profile_revision"),
        (ReplayInterventionKind.SKILL, "skill:patched@2", "skill_refs"),
        (ReplayInterventionKind.CAPABILITY_REGISTRY, "cap-v2", "capability_registry_revision"),
    ]
    baseline_payload = baseline.model_dump(mode="json", exclude={"intervention"})
    for kind, replacement, expected_field in cases:
        variant = apply_replay_intervention(
            checkpoint,
            ReplayIntervention(
                kind=kind,
                replacement=replacement,
                rationale="controlled ablation",
            ),
        )
        variant_payload = variant.model_dump(mode="json", exclude={"intervention"})
        changed = {key for key in baseline_payload if baseline_payload[key] != variant_payload[key]}
        assert changed == {expected_field}


def test_replay_protocol_evaluator_separates_protocol_failure_from_quality_metrics() -> None:
    expectation = ReplayExpectation(
        expected_task_status="completed",
        required_event_types=["TaskStarted", "TaskCompleted"],
        forbidden_event_types=["CapabilityEscalated"],
        expected_stop_reason="evidence_sufficient",
    )
    passed = evaluate_replay_protocol(
        expectation,
        ReplayObservation(
            task_status="completed",
            event_types=["TaskStarted", "Progress", "TaskCompleted"],
            stop_reason="evidence_sufficient",
            metrics={"answer_score": 0.4},
        ),
    )
    assert passed.passed is True
    failed = evaluate_replay_protocol(
        expectation,
        ReplayObservation(
            task_status="completed",
            event_types=["TaskStarted", "CapabilityEscalated", "TaskCompleted"],
            stop_reason="evidence_sufficient",
            authority_violations=["peer_message_promoted_to_fact"],
            metrics={"answer_score": 1.0},
        ),
    )
    assert failed.passed is False
    assert "forbidden_event_present:CapabilityEscalated" in failed.failures
    assert "authority_violation:peer_message_promoted_to_fact" in failed.failures
