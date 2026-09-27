from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.investigation.skills.contracts import (
    SkillDisclosureLevel,
    SkillStatus,
)
from packages.investigation.skills.materialize import materialize_skill_selection
from packages.investigation.skills.resolver import SkillResolutionContext, SkillResolver
from packages.investigation.skills.seeds import seeded_skills
from packages.investigation.skills.service import SkillStore
from packages.investigation.skills.storage import SkillVersionModel
from packages.investigation.state.contracts import (
    EvidenceNeed,
    EvidenceNeedStatus,
)
from packages.shared.db import Base
from packages.task_runtime.context.materializer import (
    ContextMaterializer,
    FragmentCacheClass,
    FragmentTrustClass,
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

NOW = datetime(2026, 9, 27, 9, 0, tzinfo=UTC)


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _task(*, task_id: str = "verify-fix") -> TaskContract:
    return TaskContract(
        task_contract_id=task_id,
        contract_revision=1,
        principal="user:test",
        task_kind=TaskKind.VERIFY_VERSION_FIX,
        target_resources=["object:vuln-1"],
        desired_state={"predicate": "first_fixed_release"},
        evidence_contract={"source_roles": ["primary"]},
        output_contract={"format": "decision"},
        temporal_contract={"scope": "current"},
        effect_ceiling=EffectCeiling.READ_ONLY,
        delegation_ceiling=DelegationCeiling(),
        completion_predicate={"type": "evidence_sufficient_or_blocked"},
        policy_revision="policy-v1",
    )


def _need() -> EvidenceNeed:
    return EvidenceNeed(
        need_id="need-fix-release",
        case_id="case-1",
        proposition_or_question="Which release first contains the fix commit?",
        purpose="verify_fix_release",
        target_objects=["vuln-1"],
        status=EvidenceNeedStatus.OPEN,
        opened_revision=1,
        updated_revision=1,
        opened_at=NOW,
        updated_at=NOW,
    )


def _validated_verify_skill():
    skill = seeded_skills()[0]
    manifest = skill.manifest.model_copy(
        update={
            "status": SkillStatus.VALIDATED,
            "validation_ref": "m7-replay:verify-fix:v1",
        }
    )
    provenance = skill.provenance.model_copy(
        update={
            "validation_case_refs": ["replay-case:verify-fix-1"],
            "promotion_history": [
                "seeded_as_candidate_pending_m7_replay",
                "validated_by_test_replay_fixture",
            ],
        }
    )
    return skill.model_copy(update={"manifest": manifest, "provenance": provenance})


def _resolution_context(*, capabilities: list[str]) -> SkillResolutionContext:
    return SkillResolutionContext(
        task_run_id="run-verify",
        object_types=["Vulnerability", "Release", "Commit"],
        visible_capability_classes=capabilities,
        available_inputs=["task_contract", "investigation_state"],
        state_signature="state:case-1@3",
        capability_view_revision="capability-view:v1",
    )


@pytest.mark.asyncio
async def test_seed_skills_are_candidate_and_not_online_selectable_by_default() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            store = SkillStore(now=lambda: NOW)
            for skill in seeded_skills():
                assert skill.manifest.status is SkillStatus.CANDIDATE
                await store.publish(session, skill)
            count = await session.scalar(select(func.count()).select_from(SkillVersionModel))
            assert count == 5
            online = await store.search_manifests(session, namespaces={"investigation"})
            assert online == []

            selection = await SkillResolver(store).resolve(
                session,
                task=_task(),
                role=canonical_roles()["InvestigationRole"],
                context=_resolution_context(capabilities=["evidence.read", "graph.read"]),
                evidence_need=_need(),
            )
            assert selection.selected_skill_ref is None
            assert selection.selection_reason == "no_applicable_validated_skill"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_validated_skill_selection_requires_matching_capability_and_inputs() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            store = SkillStore(now=lambda: NOW)
            skill = _validated_verify_skill()
            await store.publish(session, skill)
            resolver = SkillResolver(store)
            selected = await resolver.resolve(
                session,
                task=_task(),
                role=canonical_roles()["InvestigationRole"],
                context=_resolution_context(capabilities=["evidence.read", "graph.read"]),
                evidence_need=_need(),
            )
            assert selected.selected_skill_ref == skill.manifest.ref
            assert selected.candidate_skill_refs == [skill.manifest.ref]
            assert "task_pattern_match" in selected.selection_reason
            assert "evidence_need_pattern_match" in selected.selection_reason

            blocked = await resolver.resolve(
                session,
                task=_task(),
                role=canonical_roles()["InvestigationRole"],
                context=_resolution_context(capabilities=["evidence.read"]),
                evidence_need=_need(),
            )
            assert blocked.selected_skill_ref is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_store_ports_and_progressive_disclosure_preserve_trust_layers() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            store = SkillStore(now=lambda: NOW)
            skill = _validated_verify_skill()
            await store.publish(session, skill)
            manifests = await store.search_manifests(session, namespaces={"investigation"})
            assert [item.ref for item in manifests] == [skill.manifest.ref]
            assert (
                await store.get_procedure(session, skill.manifest.ref)
            ).skill_id == skill.manifest.skill_id
            first_step = skill.procedure.steps[0]
            assert (
                await store.get_step(session, skill.manifest.ref, first_step.step_id)
            ).step_id == first_step.step_id
            assert (await store.get_provenance(session, skill.manifest.ref)).origin

            selection = await SkillResolver(store).resolve(
                session,
                task=_task(),
                role=canonical_roles()["InvestigationRole"],
                context=_resolution_context(capabilities=["evidence.read", "graph.read"]),
                evidence_need=_need(),
            )
            manifest_fragments = await materialize_skill_selection(
                session,
                selection=selection,
                disclosure_level=SkillDisclosureLevel.MANIFEST,
                store=store,
            )
            assert [item.kind for item in manifest_fragments] == ["skill_manifest"]
            assert manifest_fragments[0].cache_class is FragmentCacheClass.TASK_STABLE
            assert manifest_fragments[0].trust_class is FragmentTrustClass.PROCEDURAL

            step_fragments = await materialize_skill_selection(
                session,
                selection=selection,
                disclosure_level=SkillDisclosureLevel.STEP,
                step_id=first_step.step_id,
                store=store,
            )
            assert [item.kind for item in step_fragments] == [
                "skill_manifest",
                "skill_procedure",
                "skill_step",
            ]
            assert step_fragments[-1].cache_class is FragmentCacheClass.STATE_DYNAMIC
            assert isinstance(step_fragments[-1].content, dict)
            assert "failure_guards" in step_fragments[-1].content

            provenance_fragments = await materialize_skill_selection(
                session,
                selection=selection,
                disclosure_level=SkillDisclosureLevel.PROVENANCE,
                step_id=first_step.step_id,
                store=store,
            )
            provenance = provenance_fragments[-1]
            assert provenance.kind == "skill_provenance"
            assert provenance.cache_class is FragmentCacheClass.EPHEMERAL
            assert provenance.trust_class is FragmentTrustClass.PROCEDURAL_PROVENANCE
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_skill_store_rejects_physical_endpoint_or_cli_in_procedure() -> None:
    engine, factory = await _database()
    try:
        skill = seeded_skills()[0]
        first = skill.procedure.steps[0]
        bad_step = first.model_copy(
            update={
                "semantic_instruction": "curl https://api.example.invalid/releases and parse JSON"
            }
        )
        bad_skill = skill.model_copy(
            update={
                "procedure": skill.procedure.model_copy(
                    update={"steps": [bad_step, *skill.procedure.steps[1:]]}
                )
            }
        )
        async with factory() as session, session.begin():
            with pytest.raises(ValueError, match="implementation-agnostic"):
                await SkillStore(now=lambda: NOW).publish(session, bad_skill)
            assert await session.scalar(select(func.count()).select_from(SkillVersionModel)) == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_skill_disclosure_keeps_provenance_out_of_system_instruction() -> None:
    engine, factory = await _database()
    try:
        skill = _validated_verify_skill()
        run_id = str(uuid4())
        task = _task(task_id=f"verify:{run_id}")
        manifest = ContextManifest(
            context_id=f"context:{run_id}",
            context_revision=1,
            task_contract_ref=f"{task.task_contract_id}@1",
            role_ref="InvestigationRole@1",
            skill_selection_refs=[skill.manifest.ref],
            policy_context_ref="policy-context:v1",
            capability_envelope_ref="capability:investigation:v1",
            budget_ref=f"budget:{run_id}",
        )
        async with factory() as session, session.begin():
            store = SkillStore(now=lambda: NOW)
            await store.publish(session, skill)
            await create_task_run(
                session,
                contract=task,
                manifest=manifest,
                role=canonical_roles()["InvestigationRole"],
                execution_envelope_ref=f"execution:{run_id}",
                stream_name="secfusion:task-events:test",
                run_id=run_id,
                now=NOW,
            )
            selection = await SkillResolver(store).resolve(
                session,
                task=task,
                role=canonical_roles()["InvestigationRole"],
                context=SkillResolutionContext(
                    task_run_id=run_id,
                    object_types=["Vulnerability", "Release", "Commit"],
                    visible_capability_classes=["evidence.read", "graph.read"],
                    available_inputs=["task_contract", "investigation_state"],
                    state_signature="state:case-1@3",
                    capability_view_revision="capability-view:v1",
                ),
                evidence_need=_need(),
            )
            fragments = await materialize_skill_selection(
                session,
                selection=selection,
                disclosure_level=SkillDisclosureLevel.PROVENANCE,
                step_id=skill.procedure.steps[0].step_id,
                store=store,
            )
            stable = [
                item for item in fragments if item.cache_class is FragmentCacheClass.TASK_STABLE
            ]
            dynamic = [
                item for item in fragments if item.cache_class is FragmentCacheClass.STATE_DYNAMIC
            ]
            ephemeral = [
                item for item in fragments if item.cache_class is FragmentCacheClass.EPHEMERAL
            ]
            assembly = await ContextMaterializer(
                platform_invariant_revision="platform-v1",
                platform_invariant={"authority": "runtime gates"},
            ).materialize(
                session,
                task_run_id=run_id,
                disclosure_fragments=stable,
                dynamic_fragments=dynamic,
                ephemeral_fragments=ephemeral,
            )

        assert assembly.materialized_skill_refs == [skill.manifest.ref]
        request = assembly.to_model_request()
        assert "skill_manifest" in request.system_instruction
        assert "skill_procedure" in request.system_instruction
        assert "skill_step" in request.system_instruction
        assert "skill_provenance" not in request.system_instruction
        assert "skill_provenance" in str(request.data)
    finally:
        await engine.dispose()
