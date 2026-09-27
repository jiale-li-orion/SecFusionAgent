from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.evaluation.skill_promotion import (
    ReplayValidationKind,
    SkillPromotionGate,
    SkillReplayCaseSpec,
)
from packages.investigation.cases.service import CaseService
from packages.investigation.experience.compressor import ExperienceCompressor
from packages.investigation.experience.service import ExperienceSupportRecord, ExperienceVersion
from packages.investigation.replay.contracts import (
    ReplayCheckpoint,
    ReplayLoopTopology,
    ReplayRuntimeBinding,
)
from packages.investigation.skills.contracts import SkillStatus
from packages.investigation.skills.seeds import seeded_skills
from packages.investigation.skills.service import SkillStore
from packages.investigation.skills.storage import SkillVersionModel
from packages.investigation.trajectory.service import TrajectoryService
from packages.shared.db import Base

NOW = datetime(2026, 9, 27, 21, 0, tzinfo=UTC)


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _patch():
    experience = ExperienceVersion(
        experience_id="experience-1",
        experience_version_id="experience-version-1",
        version=1,
        name="Fix boundary replay lesson",
        task_signature="verify_version_fix",
        status="active",
        scope={"capability_preferences": ["repository.compare"]},
        trigger_signals=["release_metadata_missing"],
        applicable_conditions=["fix commit is known"],
        recommended_actions=["compare release ancestry"],
        evidence_expectation=["release containment evidence"],
        failure_modes=["PR merge time is not release containment"],
        stop_conditions=["return unknown after primary paths are exhausted"],
        fallback_actions=["check package registry publication metadata"],
        validation_summary={"replay_cases": 2},
        success_count=1,
        failure_count=1,
        partial_count=0,
        last_validated_at=NOW,
    )
    supports = [
        ExperienceSupportRecord(
            trajectory_id="prior-support",
            outcome="success",
            evaluation={"correct": True},
            evaluator="m7-fixture",
            created_at=NOW,
        ),
        ExperienceSupportRecord(
            trajectory_id="prior-counterexample",
            outcome="failure",
            evaluation={"timestamp_false_positive": True},
            evaluator="m7-fixture",
            created_at=NOW,
        ),
    ]
    compressor = ExperienceCompressor()
    pattern = compressor.extract(experience, support_records=supports)
    base = seeded_skills()[0]
    patch = compressor.propose_patch(
        base,
        pattern,
        rationale="Replay exposed a release-timestamp failure mode.",
    )
    return base, patch


async def _case_with_checkpoint(session):
    case = await CaseService(now=lambda: NOW).create(
        session,
        task_signature="verify_version_fix",
        target_object_ids=[],
        goal="M7 replay fixture",
        initial_knowledge_revision=1,
    )
    trajectories = TrajectoryService(now=lambda: NOW)
    source = await trajectories.start(session, case_id=case.case_id)
    checkpoint = ReplayCheckpoint(
        checkpoint_id=f"replay-checkpoint:{case.case_id}",
        case_id=case.case_id,
        snapshot_id=f"snapshot:{case.case_id}",
        case_revision=0,
        knowledge_revision=1,
        task_run_id=f"run:{case.case_id}",
        task_contract_ref="contract:fixture@1",
        context_manifest_ref="context:fixture@1",
        task_event_seq=1,
        trajectory_id=source.trajectory_id,
        trajectory_ordinal=0,
        role_ref="InvestigationRole@1",
        runtime=ReplayRuntimeBinding(
            task_run_id=f"run:{case.case_id}",
            execution_envelope_ref=f"execution:{case.case_id}",
            execution_profile="VERIFY",
            policy_revision="policy-v1",
            network_policy="proxied",
            side_effect_policy="internal-state",
            sandbox_profile_revision="process_restricted@1",
            budget_ref=f"budget:{case.case_id}",
            budget_limits={"agent_turns": "8"},
        ),
        capability_registry_revision="cap-v1",
        skill_refs=["skill:investigation.verify_fix_boundary@1"],
        loop_topology=ReplayLoopTopology.SINGLE_LOOP,
        created_at=NOW,
    )
    await trajectories.append_event(
        session,
        trajectory_id=source.trajectory_id,
        event_type="replay_checkpoint",
        payload={"checkpoint": checkpoint.model_dump(mode="json")},
    )
    await trajectories.finish(
        session,
        trajectory_id=source.trajectory_id,
        outcome="success",
        outcome_summary={"fixture": "checkpoint-source"},
    )
    return case, source.trajectory_id, checkpoint


async def _record_case(
    session,
    *,
    gate: SkillPromotionGate,
    patch_id: str,
    suite_id: str,
    case_id: str,
    checkpoint_id: str,
    checkpoint_trajectory_id: str,
    kind: ReplayValidationKind,
    passed: bool,
):
    source_ref = (
        "trajectory:prior-support"
        if kind is ReplayValidationKind.SUPPORT
        else "trajectory:prior-counterexample"
        if kind is ReplayValidationKind.COUNTEREXAMPLE
        else "regression:seed-skill"
    )
    trajectory = await TrajectoryService(now=lambda: NOW).start(session, case_id=case_id)
    return await gate.record_replay_result(
        session,
        patch_id=patch_id,
        suite_id=suite_id,
        trajectory_id=trajectory.trajectory_id,
        checkpoint_id=checkpoint_id,
        checkpoint_trajectory_id=checkpoint_trajectory_id,
        source_ref=source_ref,
        kind=kind,
        passed=passed,
        failure_reasons=[] if passed else ["regression_detected"],
        metrics={"protocol_score": 1.0 if passed else 0.0},
    )


@pytest.mark.asyncio
async def test_m7_promotion_requires_fixed_suite_and_publishes_active_skill_only_after_pass() -> (
    None
):
    engine, factory = await _database()
    base, patch = _patch()
    try:
        async with factory() as session, session.begin():
            await SkillStore(now=lambda: NOW).publish(session, base)
            case, checkpoint_trajectory_id, checkpoint = await _case_with_checkpoint(session)
            gate = SkillPromotionGate(skill_store=SkillStore(now=lambda: NOW))
            suite = gate.build_suite(
                patch,
                [
                    SkillReplayCaseSpec(
                        case_id=case.case_id,
                        checkpoint_id=checkpoint.checkpoint_id,
                        checkpoint_trajectory_id=checkpoint_trajectory_id,
                        source_ref=(
                            "trajectory:prior-support"
                            if kind is ReplayValidationKind.SUPPORT
                            else "trajectory:prior-counterexample"
                            if kind is ReplayValidationKind.COUNTEREXAMPLE
                            else "regression:seed-skill"
                        ),
                        kind=kind,
                    )
                    for kind in (
                        ReplayValidationKind.SUPPORT,
                        ReplayValidationKind.COUNTEREXAMPLE,
                        ReplayValidationKind.REGRESSION,
                    )
                ],
            )
            results = []
            for kind in (
                ReplayValidationKind.SUPPORT,
                ReplayValidationKind.COUNTEREXAMPLE,
                ReplayValidationKind.REGRESSION,
            ):
                results.append(
                    await _record_case(
                        session,
                        gate=gate,
                        patch_id=patch.patch_id,
                        suite_id=suite.suite_id,
                        case_id=case.case_id,
                        checkpoint_id=checkpoint.checkpoint_id,
                        checkpoint_trajectory_id=checkpoint_trajectory_id,
                        kind=kind,
                        passed=True,
                    )
                )

            incomplete = await gate.promote(
                session,
                patch=patch,
                base_skill=base,
                suite=suite,
                results=results[:2],
            )
            assert incomplete.decision.approved is False
            assert any(
                item.startswith("suite_case_missing:") for item in incomplete.decision.failures
            )
            assert await session.scalar(select(func.count()).select_from(SkillVersionModel)) == 1

            promoted = await gate.promote(
                session,
                patch=patch,
                base_skill=base,
                suite=suite,
                results=results,
            )
            assert promoted.decision.approved is True
            assert promoted.decision.validation_ref is not None
            assert promoted.promoted_skill is not None
            assert promoted.promoted_skill.manifest.version == 2
            assert promoted.promoted_skill.manifest.status is SkillStatus.ACTIVE
            assert (
                promoted.promoted_skill.manifest.validation_ref == promoted.decision.validation_ref
            )
            assert promoted.promoted_skill.manifest.supersedes == base.manifest.ref
            assert promoted.promoted_skill.provenance.validation_case_refs == [
                f"case:{case.case_id}"
            ]
            assert len(promoted.promoted_skill.provenance.supporting_trajectory_refs) >= 3

            online = await SkillStore().search_manifests(
                session,
                namespaces={"investigation"},
            )
            assert [item.ref for item in online] == [promoted.promoted_skill.manifest.ref]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_m7_regression_failure_blocks_promotion_and_replay_result_is_immutable() -> None:
    engine, factory = await _database()
    base, patch = _patch()
    try:
        async with factory() as session, session.begin():
            await SkillStore(now=lambda: NOW).publish(session, base)
            case, checkpoint_trajectory_id, checkpoint = await _case_with_checkpoint(session)
            gate = SkillPromotionGate(skill_store=SkillStore(now=lambda: NOW))
            suite = gate.build_suite(
                patch,
                [
                    SkillReplayCaseSpec(
                        case_id=case.case_id,
                        checkpoint_id=checkpoint.checkpoint_id,
                        checkpoint_trajectory_id=checkpoint_trajectory_id,
                        source_ref=(
                            "trajectory:prior-support"
                            if kind is ReplayValidationKind.SUPPORT
                            else "trajectory:prior-counterexample"
                            if kind is ReplayValidationKind.COUNTEREXAMPLE
                            else "regression:seed-skill"
                        ),
                        kind=kind,
                    )
                    for kind in (
                        ReplayValidationKind.SUPPORT,
                        ReplayValidationKind.COUNTEREXAMPLE,
                        ReplayValidationKind.REGRESSION,
                    )
                ],
            )
            support = await _record_case(
                session,
                gate=gate,
                patch_id=patch.patch_id,
                suite_id=suite.suite_id,
                case_id=case.case_id,
                checkpoint_id=checkpoint.checkpoint_id,
                checkpoint_trajectory_id=checkpoint_trajectory_id,
                kind=ReplayValidationKind.SUPPORT,
                passed=True,
            )
            counterexample = await _record_case(
                session,
                gate=gate,
                patch_id=patch.patch_id,
                suite_id=suite.suite_id,
                case_id=case.case_id,
                checkpoint_id=checkpoint.checkpoint_id,
                checkpoint_trajectory_id=checkpoint_trajectory_id,
                kind=ReplayValidationKind.COUNTEREXAMPLE,
                passed=True,
            )
            regression = await _record_case(
                session,
                gate=gate,
                patch_id=patch.patch_id,
                suite_id=suite.suite_id,
                case_id=case.case_id,
                checkpoint_id=checkpoint.checkpoint_id,
                checkpoint_trajectory_id=checkpoint_trajectory_id,
                kind=ReplayValidationKind.REGRESSION,
                passed=False,
            )
            denied = await gate.promote(
                session,
                patch=patch,
                base_skill=base,
                suite=suite,
                results=[support, counterexample, regression],
            )
            assert denied.decision.approved is False
            assert f"replay_failed:{regression.result_ref}" in denied.decision.failures
            assert denied.promoted_skill is None
            assert await session.scalar(select(func.count()).select_from(SkillVersionModel)) == 1

            with pytest.raises(ValueError, match="outcome conflicts"):
                await gate.record_replay_result(
                    session,
                    patch_id=patch.patch_id,
                    suite_id=suite.suite_id,
                    trajectory_id=regression.trajectory_id,
                    checkpoint_id=checkpoint.checkpoint_id,
                    checkpoint_trajectory_id=checkpoint_trajectory_id,
                    source_ref="regression:seed-skill",
                    kind=ReplayValidationKind.REGRESSION,
                    passed=True,
                    metrics={"protocol_score": 1.0},
                )
    finally:
        await engine.dispose()
