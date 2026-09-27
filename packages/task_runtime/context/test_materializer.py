from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.shared.db import Base
from packages.task_runtime.context.materializer import (
    ContextMaterializer,
    FragmentCacheClass,
    FragmentTrustClass,
    MaterializedFragment,
)
from packages.task_runtime.contracts.models import (
    ContextManifest,
    DelegationCeiling,
    EffectCeiling,
    TaskContract,
    TaskKind,
)
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.service import create_task_run

NOW = datetime(2026, 9, 27, 6, 0, tzinfo=UTC)


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed_run(session) -> str:
    run_id = str(uuid4())
    contract = TaskContract(
        task_contract_id=f"enrichment:{run_id}",
        contract_revision=1,
        principal="user:test",
        task_kind=TaskKind.ENRICHMENT,
        target_resources=["object:vuln-1"],
        desired_state={"goal": "test materialization"},
        evidence_contract={},
        output_contract={},
        temporal_contract={"scope": "current"},
        effect_ceiling=EffectCeiling.INTERNAL_STATE,
        delegation_ceiling=DelegationCeiling(),
        completion_predicate={"type": "test"},
        policy_revision="policy-v1",
    )
    manifest = ContextManifest(
        context_id=f"context:{run_id}",
        context_revision=1,
        task_contract_ref=f"{contract.task_contract_id}@1",
        role_ref="EnrichmentRole@1",
        knowledge_revision=42,
        evidence_refs=["evidence:e1"],
        object_refs=["object:vuln-1"],
        skill_selection_refs=["skill:verify-fix@1"],
        policy_context_ref="policy-context:v1",
        capability_envelope_ref="capability-envelope:v1",
        budget_ref=f"budget:{run_id}",
        cache_hint="cache:seed",
    )
    await create_task_run(
        session,
        contract=contract,
        manifest=manifest,
        role=canonical_roles()["EnrichmentRole"],
        execution_envelope_ref=f"execution:{run_id}",
        stream_name="secfusion:task-events:test",
        run_id=run_id,
        now=NOW,
    )
    return run_id


def _materializer() -> ContextMaterializer:
    return ContextMaterializer(
        platform_invariant_revision="platform-v1",
        platform_invariant={
            "fact_authority": "Evidence/Knowledge and State gates",
            "permission_authority": "Policy/Capability runtime",
        },
    )


@pytest.mark.asyncio
async def test_prompt_assembly_is_deterministic_reference_preserving_and_layered() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            run_id = await _seed_run(session)

        skill = MaterializedFragment.build(
            kind="skill_manifest",
            source_ref="skill:verify-fix@1",
            source_revision="1",
            disclosure_level="manifest",
            selection_reason="task_kind_match",
            trust_class=FragmentTrustClass.PROCEDURAL,
            cache_class=FragmentCacheClass.TASK_STABLE,
            content={"purpose": "Verify fix boundary", "guard": "require evidence"},
        )
        capability = MaterializedFragment.build(
            kind="capability_card",
            source_ref="capability-view:github-read@1",
            source_revision="1",
            disclosure_level="card",
            selection_reason="primary evidence available",
            trust_class=FragmentTrustClass.RUNTIME_CONTROL,
            cache_class=FragmentCacheClass.TASK_STABLE,
            content={"action": "read_release", "risk_class": "low"},
        )
        dynamic = MaterializedFragment.build(
            kind="evidence_scope",
            source_ref="evidence:e1",
            source_revision="42",
            trust_class=FragmentTrustClass.EVIDENCE_REFERENCE,
            cache_class=FragmentCacheClass.STATE_DYNAMIC,
            content={"evidence_ref": "evidence:e1"},
        )
        ephemeral = MaterializedFragment.build(
            kind="ephemeral_observation",
            source_ref="observation:ephemeral-1",
            source_revision="1",
            trust_class=FragmentTrustClass.UNTRUSTED_EXTERNAL,
            cache_class=FragmentCacheClass.EPHEMERAL,
            content={"text": "external provider says fixed"},
        )

        async with factory() as session:
            first = await _materializer().materialize(
                session,
                task_run_id=run_id,
                disclosure_fragments=[skill, capability],
                dynamic_fragments=[dynamic],
                ephemeral_fragments=[ephemeral],
                runtime_disclosure_refs={"capability-view:github-read@1"},
                percept_refs=["percept:p1"],
                state_projection_revision="state@42",
            )
            second = await _materializer().materialize(
                session,
                task_run_id=run_id,
                disclosure_fragments=[skill, capability],
                dynamic_fragments=[dynamic],
                ephemeral_fragments=[ephemeral],
                runtime_disclosure_refs={"capability-view:github-read@1"},
                percept_refs=["percept:p1"],
                state_projection_revision="state@42",
            )

        assert first == second
        assert first.materialized_skill_refs == ["skill:verify-fix@1"]
        assert first.materialized_capability_view_refs == ["capability-view:github-read@1"]
        assert first.percept_refs == ["percept:p1"]
        assert first.cache_handle_hints[0] == "cache:seed"
        cache_classes = [fragment.cache_class for fragment in first.fragments]
        assert cache_classes == sorted(
            cache_classes,
            key=lambda item: {
                FragmentCacheClass.STATIC: 0,
                FragmentCacheClass.TASK_STABLE: 1,
                FragmentCacheClass.STATE_DYNAMIC: 2,
                FragmentCacheClass.EPHEMERAL: 3,
            }[item],
        )
        assert "evidence:e1" in first.materialized_fragment_refs
        assert "observation:ephemeral-1" in first.materialized_fragment_refs

        request = first.to_model_request()
        assert "platform_invariant" in request.system_instruction
        assert "skill_manifest" in request.system_instruction
        assert "external provider says fixed" not in request.system_instruction
        assert request.data["percept_refs"] == ["percept:p1"]
        assert request.metadata["assembly_hash"] == first.assembly_hash
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_prompt_hash_changes_when_selection_reason_or_percept_refs_change() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            run_id = await _seed_run(session)
        base = MaterializedFragment.build(
            kind="skill_manifest",
            source_ref="skill:verify-fix@1",
            source_revision="1",
            disclosure_level="manifest",
            selection_reason="task_kind_match",
            trust_class=FragmentTrustClass.PROCEDURAL,
            cache_class=FragmentCacheClass.TASK_STABLE,
            content={"purpose": "Verify fix boundary"},
        )
        changed_reason = MaterializedFragment.build(
            kind="skill_manifest",
            source_ref="skill:verify-fix@1",
            source_revision="1",
            disclosure_level="manifest",
            selection_reason="explicit_guard_match",
            trust_class=FragmentTrustClass.PROCEDURAL,
            cache_class=FragmentCacheClass.TASK_STABLE,
            content={"purpose": "Verify fix boundary"},
        )
        assert base.fragment_id != changed_reason.fragment_id

        async with factory() as session:
            first = await _materializer().materialize(
                session,
                task_run_id=run_id,
                disclosure_fragments=[base],
                percept_refs=["percept:p1"],
            )
            second = await _materializer().materialize(
                session,
                task_run_id=run_id,
                disclosure_fragments=[base],
                percept_refs=["percept:p2"],
            )
        assert first.assembly_hash != second.assembly_hash
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_materializer_rejects_scope_expansion_and_wrong_cache_layer() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            run_id = await _seed_run(session)
        unauthorized = MaterializedFragment.build(
            kind="state",
            source_ref="evidence:not-in-context",
            source_revision="1",
            trust_class=FragmentTrustClass.DURABLE_STATE,
            cache_class=FragmentCacheClass.STATE_DYNAMIC,
            content={"value": "should not materialize"},
        )
        async with factory() as session:
            with pytest.raises(ValueError, match="cannot expand ContextManifest"):
                await _materializer().materialize(
                    session,
                    task_run_id=run_id,
                    dynamic_fragments=[unauthorized],
                )

        wrong_layer = unauthorized.model_copy(
            update={
                "source_ref": "evidence:e1",
                "cache_class": FragmentCacheClass.EPHEMERAL,
            }
        )
        async with factory() as session:
            with pytest.raises(ValueError, match="cache_class=state_dynamic"):
                await _materializer().materialize(
                    session,
                    task_run_id=run_id,
                    dynamic_fragments=[wrong_layer],
                )
    finally:
        await engine.dispose()
