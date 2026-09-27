from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.investigation.runtime.tasks import build_investigation_contract
from packages.runtime.model import (
    PromptAssemblyRecord,
    PromptAssemblyRecordService,
    PromptFragmentRecord,
)
from packages.runtime.storage.models import ExecutionRunModel
from packages.shared.db import Base
from packages.task_runtime.contracts.models import ContextManifest, TaskKind
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.service import create_task_run

NOW = datetime(2026, 9, 27, 14, 0, tzinfo=UTC)


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _record() -> PromptAssemblyRecord:
    return PromptAssemblyRecord(
        assembly_id="assembly-1",
        assembly_hash="a" * 64,
        execution_id="execution:prompt-test",
        task_run_id="run-prompt-test",
        task_contract_id="contract-prompt-test",
        context_manifest_ref="context:prompt-test",
        context_manifest_revision=2,
        role_revision="InvestigationRole@1",
        platform_invariant_revision="platform-v1",
        execution_profile_revision="VERIFY@1",
        policy_context_revision="policy-context:v1",
        state_projection_revision="case:1@2",
        percept_refs=["percept:1"],
        materialized_skill_refs=["skill:verify@1"],
        materialized_capability_view_refs=["capability-view:verify-v1"],
        materialized_fragment_refs=["object:1", "percept:1"],
        ordered_fragment_ids=["fragment-1"],
        materialized_ref_set_digest="b" * 64,
        cache_handle_hints=["prefix:abc"],
        fragment_manifest=[
            PromptFragmentRecord(
                fragment_id="fragment-1",
                kind="knowledge_object",
                source_ref="object:1",
                source_revision="42",
                disclosure_level=None,
                selection_reason="target object",
                trust_class="evidence_reference",
                cache_class="state_dynamic",
                content_hash="c" * 64,
            )
        ],
        created_at=NOW,
    )


@pytest.mark.asyncio
async def test_prompt_assembly_record_is_idempotent_and_metadata_only() -> None:
    engine, factory = await _database()
    service = PromptAssemblyRecordService()
    try:
        async with factory() as session, session.begin():
            contract = build_investigation_contract(
                task_contract_id="contract-prompt-test",
                principal="user:test",
                task_kind=TaskKind.VERIFY_VERSION_FIX,
                case_id="case-prompt-test",
                target_object_ids=["object-prompt-test"],
                required_need_ids=["need-prompt-test"],
                policy_revision="policy-v1",
            )
            manifest = ContextManifest(
                context_id="context:prompt-test",
                context_revision=2,
                task_contract_ref="contract-prompt-test@1",
                role_ref="InvestigationRole@1",
                case_ref="case-prompt-test",
                knowledge_revision=42,
                investigation_state_ref="case:case-prompt-test@2",
                object_refs=["object-prompt-test"],
                policy_context_ref="policy-context:v1",
                capability_envelope_ref="capability:verify:v1",
                budget_ref="budget:prompt-test",
            )
            await create_task_run(
                session,
                contract=contract,
                manifest=manifest,
                role=canonical_roles()["InvestigationRole"],
                execution_envelope_ref="execution:prompt-test",
                stream_name="secfusion:task-events:prompt-record-test",
                case_id="case-prompt-test",
                run_id="run-prompt-test",
                producer="prompt-record-test",
                now=NOW,
            )
            session.add(
                ExecutionRunModel(
                    execution_id="execution:prompt-test",
                    parent_execution_id=None,
                    task_run_id="run-prompt-test",
                    envelope_json={"execution_id": "execution:prompt-test"},
                    status="running",
                    stop_reason=None,
                    created_at=NOW,
                    started_at=NOW,
                    finished_at=None,
                )
            )
            first = await service.persist(session, _record())
            second = await service.persist(session, _record())
            assert second == first
            assert first.fragment_manifest[0].content_hash == "c" * 64
            assert "content" not in first.fragment_manifest[0].model_dump()
    finally:
        await engine.dispose()
