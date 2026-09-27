from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.observation_promotion import ObservationPromotionService
from apps.perception_execution import ObservationPromotionBinding
from apps.runtime_models import register_runtime_models
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.evidence_models import EvidenceArtifactModel, ObservationModel
from packages.intelligence.storage.knowledge_models import EvidenceLinkModel, ObjectModel
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.runtime.artifacts import MemoryRuntimeBlobStore, RuntimeArtifactService
from packages.runtime.capability.broker import CapabilityInvocationOutcome
from packages.runtime.capability.contracts import (
    CapabilityInvocation,
    CapabilityResult,
    CapabilityResultStatus,
    EffectSemantics,
    ExecutionClass,
    InvocationPlan,
)
from packages.runtime.capability.observations import EphemeralObservation
from packages.runtime.execution.service import ExecutionRunService
from packages.runtime.policy.contracts import (
    Authorization,
    PolicyDecision,
    PolicyDecisionPoint,
    PolicyObligation,
)
from packages.runtime.policy.engine import RuntimePolicyRule, StaticPolicyEngine
from packages.shared.db import Base
from packages.sources.contracts import RetentionMode, SourceDefinition, SourceRole
from packages.sources.registry.service import sync_source_definitions
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

NOW = datetime(2026, 9, 27, 13, 10, tzinfo=UTC)

SOURCE = SourceDefinition(
    source_id="fixture-primary-release-api",
    adapter_type="fixture",
    source_class="development_platform",
    authority_scope=["release_state", "fix_status"],
    source_role=SourceRole.PRIMARY,
    source_family="fixture-primary-release-api",
    access_mode="api",
    update_semantics="mutable",
    retention_mode=RetentionMode.TIME_BOUNDED,
)


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _task(run_id: str) -> TaskContract:
    return TaskContract(
        task_contract_id=f"verify:{run_id}",
        contract_revision=1,
        principal="user:test",
        task_kind=TaskKind.VERIFY_VERSION_FIX,
        target_resources=["repo:example/project"],
        desired_state={"goal": "verify first fixed release"},
        evidence_contract={"required_source_roles": ["primary"]},
        output_contract={"format": "decision"},
        temporal_contract={"scope": "current"},
        effect_ceiling=EffectCeiling.READ_ONLY,
        delegation_ceiling=DelegationCeiling(),
        completion_predicate={"type": "evidence_sufficient_or_blocked"},
        policy_revision="policy-v1",
    )


def _policy(*, permit: bool = True, obligation: bool = False) -> StaticPolicyEngine:
    rules: list[RuntimePolicyRule] = []
    if permit:
        rules.append(
            RuntimePolicyRule(
                policy_id="allow-observation-promotion",
                policy_revision="policy-v1",
                decision_points=[PolicyDecisionPoint.OBSERVATION_PROMOTION],
                principal_patterns=["user:test"],
                action_patterns=["promote_observation"],
                resource_patterns=[f"source:{SOURCE.source_id}"],
                authorization=Authorization.PERMIT,
                obligations=([PolicyObligation(kind="require_audit_log")] if obligation else []),
            )
        )
    return StaticPolicyEngine(policy_revision="policy-v1", rules=rules)


async def _seed_runtime(factory, runtime_artifacts: RuntimeArtifactService):
    run_id = str(uuid4())
    execution_id = f"execution:{run_id}"
    acquisition_run_id = str(uuid4())
    object_id = str(uuid4())
    task = _task(run_id)
    execution_service = ExecutionRunService(now=lambda: NOW)
    async with factory() as session, session.begin():
        await sync_source_definitions(session, [SOURCE])
        session.add(
            ObjectModel(
                object_id=object_id,
                object_type="Vulnerability",
                canonical_key=f"cve:CVE-2026-{run_id[:4]}",
                properties={},
                created_revision=1,
            )
        )
        await create_task_run(
            session,
            contract=task,
            manifest=ContextManifest(
                context_id=f"context:{run_id}",
                context_revision=1,
                task_contract_ref=f"{task.task_contract_id}@1",
                role_ref="InvestigationRole@1",
                object_refs=[object_id],
                policy_context_ref="policy-context:v1",
                capability_envelope_ref="capability:verify:v1",
                budget_ref=f"budget:{run_id}",
            ),
            role=canonical_roles()["InvestigationRole"],
            execution_envelope_ref=execution_id,
            stream_name="secfusion:task-events:promotion-test",
            run_id=run_id,
            now=NOW,
        )
        envelope = ExecutionEnvelope(
            execution_id=execution_id,
            task_contract_id=task.task_contract_id,
            task_run_id=run_id,
            role_revision="InvestigationRole@1",
            context_manifest_revision=1,
            execution_profile=ExecutionProfile.VERIFY,
            capability_scope=["repo.read_release"],
            deadline_at=NOW + timedelta(minutes=5),
            budget_ref=f"budget:{run_id}",
            policy_revision="policy-v1",
            identity_scope=["public"],
            network_policy="proxied",
            side_effect_policy="read-only",
            sandbox_profile_revision="process_restricted@1",
        )
        await execution_service.create(session, envelope)
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
    return task, run_id, execution_id, acquisition_run_id, object_id, artifact.artifact_ref


def _outcome(
    *,
    run_id: str,
    artifact_ref: str,
    acquisition_run_id: str,
) -> CapabilityInvocationOutcome:
    invocation_id = str(uuid4())
    observation = EphemeralObservation(
        observation_id=str(uuid4()),
        request_id="capability:release-read",
        capability_id="repo.read_release",
        source="tool:fixture-release-reader@1",
        provenance={
            "acquisition_run_id": acquisition_run_id,
            "external_object_id": "release:v1.2.3",
            "external_revision": "v1.2.3",
            "canonical_url": "https://example.invalid/releases/v1.2.3",
            "published_at": NOW.isoformat(),
            "updated_at": NOW.isoformat(),
        },
        observed_at=NOW,
        raw_result_ref=artifact_ref,
        extracted_candidates=[{"statement": "Release v1.2.3 contains the fix commit."}],
        trust_label="untrusted_tool_output",
        ttl_seconds=900,
    )
    return CapabilityInvocationOutcome(
        invocation=CapabilityInvocation(
            invocation_id=invocation_id,
            invocation_plan_id="plan:release-read",
            policy_decision_ref="policy-decision:invoke",
            started_at=NOW,
        ),
        plan=InvocationPlan(
            invocation_plan_id="plan:release-read",
            capability_request_ref="capability-request:release-read",
            binding_id="binding:release-read",
            binding_revision=1,
            resolved_resource="repo:example/project",
            resolved_effect=EffectSemantics.OBSERVATION,
            canonical_arguments_digest="0" * 64,
            native_arguments_ref="native-args:release-read",
            execution_class=ExecutionClass.PROXIED_PROVIDER_READ,
            credential_requirement="none",
            network_requirement="proxied",
            sandbox_requirement="none",
            deadline_at=NOW + timedelta(minutes=5),
            budget_reservation_ref=f"budget-reservation:{run_id}",
        ),
        policy_decision=PolicyDecision(
            authorization=Authorization.PERMIT,
            policy_revision="policy-v1",
        ),
        result=CapabilityResult(
            invocation_id=invocation_id,
            status=CapabilityResultStatus.SUCCEEDED,
            raw_artifact_ref=artifact_ref,
            observation_class="ephemeral",
        ),
        observation=observation,
    )


@pytest.mark.asyncio
async def test_observation_promotion_creates_durable_evidence_and_replays_idempotently() -> None:
    engine, factory = await _database()
    runtime_artifacts = RuntimeArtifactService(MemoryRuntimeBlobStore(), now=lambda: NOW)
    try:
        task, run_id, _, acquisition_run_id, object_id, artifact_ref = await _seed_runtime(
            factory, runtime_artifacts
        )
        outcome = _outcome(
            run_id=run_id,
            artifact_ref=artifact_ref,
            acquisition_run_id=acquisition_run_id,
        )
        service = ObservationPromotionService(
            factory,
            _policy(),
            runtime_artifacts,
            EvidenceIngress(MemoryArtifactStore(), now=lambda: NOW),
            {SOURCE.source_id: SOURCE},
        )
        binding = ObservationPromotionBinding(
            source_id=SOURCE.source_id,
            target_kind="object",
            target_id=object_id,
            locator={"kind": "provider_release", "tag": "v1.2.3"},
        )
        first = await service.promote(
            task_run_id=run_id,
            task=task,
            outcome=outcome,
            binding=binding,
        )
        replay = await service.promote(
            task_run_id=run_id,
            task=task,
            outcome=outcome,
            binding=binding,
        )
        assert len(first.candidates) == 1
        candidate = first.candidates[0]
        assert candidate.evidence_ref is not None
        assert candidate.source_role == "primary"
        assert candidate.source_family == SOURCE.source_family
        assert replay.candidates[0].evidence_ref == candidate.evidence_ref
        assert first.cost["promotion_calls"] == 1

        async with factory() as session:
            assert await session.scalar(select(func.count()).select_from(ObservationModel)) == 1
            assert (
                await session.scalar(select(func.count()).select_from(EvidenceArtifactModel)) == 1
            )
            assert await session.scalar(select(func.count()).select_from(EvidenceLinkModel)) == 1
            link = await session.get(EvidenceLinkModel, candidate.evidence_ref)
            assert link is not None
            assert link.target_kind == "object"
            assert link.target_id == object_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_observation_promotion_policy_deny_or_missing_obligation_writes_nothing() -> None:
    for policy, binding_kwargs, expected in (
        (_policy(permit=False), {}, "observation_promotion_deny"),
        (
            _policy(obligation=True),
            {},
            "observation_promotion_obligation_unsatisfied:require_audit_log",
        ),
    ):
        engine, factory = await _database()
        runtime_artifacts = RuntimeArtifactService(MemoryRuntimeBlobStore(), now=lambda: NOW)
        try:
            task, run_id, _, acquisition_run_id, object_id, artifact_ref = await _seed_runtime(
                factory, runtime_artifacts
            )
            service = ObservationPromotionService(
                factory,
                policy,
                runtime_artifacts,
                EvidenceIngress(MemoryArtifactStore(), now=lambda: NOW),
                {SOURCE.source_id: SOURCE},
            )
            result = await service.promote(
                task_run_id=run_id,
                task=task,
                outcome=_outcome(
                    run_id=run_id,
                    artifact_ref=artifact_ref,
                    acquisition_run_id=acquisition_run_id,
                ),
                binding=ObservationPromotionBinding(
                    source_id=SOURCE.source_id,
                    target_kind="object",
                    target_id=object_id,
                    **binding_kwargs,
                ),
            )
            assert expected in result.unresolved
            async with factory() as session:
                assert await session.scalar(select(func.count()).select_from(ObservationModel)) == 0
                assert (
                    await session.scalar(select(func.count()).select_from(EvidenceLinkModel)) == 0
                )
        finally:
            await engine.dispose()


@pytest.mark.asyncio
async def test_observation_promotion_rejects_runtime_artifact_from_other_execution() -> None:
    engine, factory = await _database()
    runtime_artifacts = RuntimeArtifactService(MemoryRuntimeBlobStore(), now=lambda: NOW)
    try:
        task, run_id, _, acquisition_run_id, object_id, _ = await _seed_runtime(
            factory, runtime_artifacts
        )
        other_task, other_run_id, _, _, _, foreign_artifact_ref = await _seed_runtime(
            factory, runtime_artifacts
        )
        del other_task, other_run_id
        service = ObservationPromotionService(
            factory,
            _policy(),
            runtime_artifacts,
            EvidenceIngress(MemoryArtifactStore(), now=lambda: NOW),
            {SOURCE.source_id: SOURCE},
        )
        with pytest.raises(PermissionError, match="escapes TaskRun execution"):
            await service.promote(
                task_run_id=run_id,
                task=task,
                outcome=_outcome(
                    run_id=run_id,
                    artifact_ref=foreign_artifact_ref,
                    acquisition_run_id=acquisition_run_id,
                ),
                binding=ObservationPromotionBinding(
                    source_id=SOURCE.source_id,
                    target_kind="object",
                    target_id=object_id,
                ),
            )
    finally:
        await engine.dispose()
