from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.investigation_delegation import (
    DelegatedEnrichmentPolicy,
    EnrichmentDelegationAdapter,
)
from apps.runtime_models import register_runtime_models
from packages.intelligence.storage.knowledge_models import KnowledgeRevisionModel, ObjectModel
from packages.investigation.cases.service import CaseService
from packages.investigation.runtime.contracts import EnrichmentDelegationRequest
from packages.investigation.runtime.tasks import build_investigation_contract
from packages.runtime.budget import BudgetGovernor, BudgetLimits
from packages.runtime.execution.service import ExecutionRunService
from packages.shared.db import Base
from packages.task_runtime.contracts.execution import ExecutionEnvelope
from packages.task_runtime.contracts.models import (
    ContextManifest,
    ExecutionProfile,
    TaskKind,
    TaskRunStatus,
)
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.service import (
    create_task_run,
    get_task_context,
    get_task_contract_for_run,
    get_task_run,
    transition_task_run,
)

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
STREAM = "secfusion:task-events:delegation-test"


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed_parent(session, budget: BudgetGovernor, execution: ExecutionRunService):
    revision = KnowledgeRevisionModel(committed_at=NOW)
    session.add(revision)
    await session.flush()
    object_id = str(uuid4())
    session.add(
        ObjectModel(
            object_id=object_id,
            object_type="Vulnerability",
            canonical_key="cve:CVE-2026-71717",
            properties={},
            created_revision=revision.revision,
        )
    )
    await session.flush()
    case = await CaseService(now=lambda: NOW).create(
        session,
        task_signature="delegation-parent",
        target_object_ids=[object_id],
        goal="Verify fix boundary with delegated enrichment.",
        initial_knowledge_revision=revision.revision,
    )
    run_id = str(uuid4())
    contract = build_investigation_contract(
        task_contract_id=f"verify:{run_id}",
        principal="user:alice",
        task_kind=TaskKind.VERIFY_VERSION_FIX,
        case_id=case.case_id,
        target_object_ids=[object_id],
        required_need_ids=["need-fix-boundary"],
        policy_revision="policy-v1",
    )
    budget_id = f"budget:{run_id}"
    execution_id = f"execution:{run_id}"
    manifest = ContextManifest(
        context_id=f"context:{run_id}",
        context_revision=1,
        task_contract_ref=f"{contract.task_contract_id}@1",
        role_ref="InvestigationRole@1",
        case_ref=case.case_id,
        knowledge_revision=revision.revision,
        investigation_state_ref=f"case:{case.case_id}@0",
        object_refs=[object_id],
        policy_context_ref="policy-context:v1",
        capability_envelope_ref="capability:parent:v1",
        budget_ref=budget_id,
    )
    await create_task_run(
        session,
        contract=contract,
        manifest=manifest,
        role=canonical_roles()["InvestigationRole"],
        execution_envelope_ref=execution_id,
        stream_name=STREAM,
        case_id=case.case_id,
        run_id=run_id,
        now=NOW,
    )
    await transition_task_run(
        session,
        run_id=run_id,
        target=TaskRunStatus.QUEUED,
        payload_ref="queue:test",
        idempotency_key=f"queued:{run_id}",
        stream_name=STREAM,
        producer="test",
        now=NOW,
    )
    await transition_task_run(
        session,
        run_id=run_id,
        target=TaskRunStatus.RUNNING,
        payload_ref="role:InvestigationRole",
        idempotency_key=f"running:{run_id}",
        stream_name=STREAM,
        producer="test",
        now=NOW,
    )
    await budget.create_account(
        session,
        account_id=budget_id,
        task_run_id=run_id,
        limits=BudgetLimits(
            quantities={
                "tool_calls": Decimal("5"),
                "agent_turns": Decimal("4"),
            }
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
        capability_scope=["github.read", "nvd.read"],
        deadline_at=NOW + timedelta(minutes=10),
        budget_ref=budget_id,
        policy_revision="policy-v1",
        identity_scope=["public", "github-readonly"],
        network_policy="proxied",
        side_effect_policy="internal-state",
        sandbox_profile_revision="process_restricted@1",
    )
    await execution.create(session, envelope)
    await execution.start(session, execution_id)
    return run_id, object_id, budget_id, envelope


@pytest.mark.asyncio
async def test_delegated_enrichment_creates_bounded_child_context_budget_and_execution() -> None:
    engine, factory = await _database()
    budget = BudgetGovernor(now=lambda: NOW)
    execution = ExecutionRunService(now=lambda: NOW)
    try:
        async with factory() as session, session.begin():
            parent_run_id, object_id, parent_budget_id, parent_envelope = await _seed_parent(
                session,
                budget,
                execution,
            )
        adapter = EnrichmentDelegationAdapter(
            factory,
            policy=DelegatedEnrichmentPolicy(
                budget_quantities={
                    "tool_calls": Decimal("2"),
                    "agent_turns": Decimal("1"),
                },
                capability_scope=["github.read"],
                identity_scope=["public"],
            ),
            budget_governor=budget,
            execution_service=execution,
            stream_name=STREAM,
        )
        request = EnrichmentDelegationRequest(
            delegation_id="fix-remediation-gap",
            target_object_id=object_id,
            cve_id="CVE-2026-71717",
            required_dimensions=["fix_remediation"],
            reason="missing durable fix boundary evidence",
        )
        first = await adapter.delegate_enrichment(
            parent_run_id=parent_run_id,
            request=request,
        )
        replay = await adapter.delegate_enrichment(
            parent_run_id=parent_run_id,
            request=request,
        )
        assert replay == first

        async with factory() as session:
            child = await get_task_run(session, first.child_run_id)
            child_contract = await get_task_contract_for_run(session, first.child_run_id)
            child_context = await get_task_context(session, first.child_run_id)
            child_envelope = await execution.get(session, first.child_execution_ref)
            parent_budget = await budget.snapshot(session, parent_budget_id)
            child_budget = await budget.snapshot(session, child_envelope.budget_ref)

        assert child.parent_run_id == parent_run_id
        assert child.role_id == "EnrichmentRole"
        assert child_contract.task_kind is TaskKind.ENRICHMENT
        assert child_context.parent_context_id is not None
        assert child_context.object_refs == [object_id]
        assert child_context.case_ref is None
        assert child_context.investigation_state_ref is None
        assert child_envelope.parent_execution_id == parent_envelope.execution_id
        assert child_envelope.capability_scope == ["github.read"]
        assert child_envelope.identity_scope == ["public"]
        assert child_envelope.deadline_at == parent_envelope.deadline_at
        assert parent_budget.reserved["tool_calls"] == Decimal("2.000000")
        assert child_budget.remaining["tool_calls"] == Decimal("2.000000")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_delegated_enrichment_rejects_scope_expansion_before_child_creation() -> None:
    engine, factory = await _database()
    budget = BudgetGovernor(now=lambda: NOW)
    execution = ExecutionRunService(now=lambda: NOW)
    try:
        async with factory() as session, session.begin():
            parent_run_id, object_id, _, _ = await _seed_parent(session, budget, execution)
        adapter = EnrichmentDelegationAdapter(
            factory,
            policy=DelegatedEnrichmentPolicy(
                budget_quantities={"tool_calls": Decimal("1")},
                capability_scope=["forbidden.write"],
            ),
            budget_governor=budget,
            execution_service=execution,
            stream_name=STREAM,
        )
        with pytest.raises(ValueError, match="capability scope exceeds parent"):
            await adapter.delegate_enrichment(
                parent_run_id=parent_run_id,
                request=EnrichmentDelegationRequest(
                    delegation_id="bad-scope",
                    target_object_id=object_id,
                    cve_id="CVE-2026-71717",
                    required_dimensions=["fix_remediation"],
                    reason="test",
                ),
            )
    finally:
        await engine.dispose()
