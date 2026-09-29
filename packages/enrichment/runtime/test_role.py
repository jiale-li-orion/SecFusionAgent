from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.enrichment.runtime.executor import EnrichmentOperatorExecution
from packages.enrichment.runtime.role import EnrichmentRoleRuntime
from packages.enrichment.runtime.state import (
    EnrichmentAttemptStatus,
    EnrichmentSemanticOutcome,
    EnrichmentStatus,
)
from packages.enrichment.runtime.state_models import EnrichmentAttemptModel
from packages.enrichment.runtime.tasks import build_vulnerability_enrichment_contract
from packages.intelligence.knowledge.vocabulary import VOCABULARY_REVISION, EnrichmentDimension
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    ExternalIdentifierModel,
    KnowledgeRevisionModel,
    ObjectModel,
    RelationModel,
)
from packages.shared.db import Base
from packages.task_runtime.contracts.models import (
    ContextManifest,
    DelegationCeiling,
    EffectCeiling,
    TaskContract,
    TaskEventType,
    TaskKind,
    TaskRunStatus,
)
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.models import TaskRunModel
from packages.task_runtime.storage.service import (
    create_task_run,
    list_task_events,
    transition_task_run,
)

NOW = datetime(2026, 9, 27, 2, 30, tzinfo=UTC)
STREAM = "secfusion:task-events:enrichment-role-test"


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed_vulnerability(
    session: AsyncSession,
    *,
    cve_id: str = "CVE-2026-42424",
) -> tuple[str, int]:
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
    return object_id, revision.revision


async def _create_enrichment_run(
    session: AsyncSession,
    *,
    object_id: str,
    cve_id: str = "CVE-2026-42424",
    parent_run_id: str | None = None,
    run_id: str | None = None,
    required_dimensions: list[EnrichmentDimension] | None = None,
) -> str:
    resolved_run_id = run_id or str(uuid4())
    contract = build_vulnerability_enrichment_contract(
        task_contract_id=f"enrichment:{resolved_run_id}",
        principal="user:alice",
        target_object_id=object_id,
        cve_id=cve_id,
        required_dimensions=required_dimensions or [EnrichmentDimension.EXPLOIT_STATE],
        policy_revision="policy-v1",
    )
    manifest = ContextManifest(
        context_id=f"context:{resolved_run_id}",
        context_revision=1,
        task_contract_ref=f"{contract.task_contract_id}@{contract.contract_revision}",
        role_ref="EnrichmentRole@1",
        knowledge_revision=1,
        object_refs=[object_id],
        policy_context_ref="policy-context:v1",
        capability_envelope_ref="capability:enrichment:v1",
        budget_ref=f"budget:{resolved_run_id}",
    )
    await create_task_run(
        session,
        contract=contract,
        manifest=manifest,
        role=canonical_roles()["EnrichmentRole"],
        execution_envelope_ref=f"execution:{resolved_run_id}",
        stream_name=STREAM,
        parent_run_id=parent_run_id,
        run_id=resolved_run_id,
        now=NOW,
    )
    return resolved_run_id


class _ResolvingExecutor:
    def __init__(self, factory: async_sessionmaker[AsyncSession], object_id: str) -> None:
        self._factory = factory
        self._object_id = object_id
        self.calls: list[str] = []

    async def execute(self, plan, *, cve_id: str, parent_run_id: str):
        del cve_id, parent_run_id
        self.calls.append(plan.operator_id)
        async with self._factory() as session, session.begin():
            revision = KnowledgeRevisionModel(committed_at=NOW + timedelta(seconds=1))
            session.add(revision)
            await session.flush()
            claim_id = str(uuid4())
            session.add(
                ClaimModel(
                    claim_id=claim_id,
                    subject_id=self._object_id,
                    predicate="known_exploited",
                    value=True,
                    qualifier={
                        "source_id": "cisa-kev",
                        "vocabulary_revision": VOCABULARY_REVISION,
                        "vocabulary_scope": "canonical",
                    },
                    origin="source_asserted",
                    lifecycle="accepted",
                    processing_run_id=None,
                    created_revision=revision.revision,
                )
            )
        return EnrichmentOperatorExecution(
            operator_id=plan.operator_id,
            status=EnrichmentAttemptStatus.SUCCEEDED,
            semantic_outcomes={
                EnrichmentDimension.EXPLOIT_STATE: EnrichmentSemanticOutcome.RESOLVED
            },
            output_refs=["claim:known_exploited"],
        )


class _UnknownExecutor:
    calls: list[str]

    def __init__(self) -> None:
        self.calls = []

    async def execute(self, plan, *, cve_id: str, parent_run_id: str):
        del cve_id, parent_run_id
        self.calls.append(plan.operator_id)
        return EnrichmentOperatorExecution(
            operator_id=plan.operator_id,
            status=EnrichmentAttemptStatus.SUCCEEDED,
            semantic_outcomes={
                EnrichmentDimension.EXPLOIT_STATE: EnrichmentSemanticOutcome.UNKNOWN
            },
        )


class _BlockedExecutor:
    calls: list[str]

    def __init__(self) -> None:
        self.calls = []

    async def execute(self, plan, *, cve_id: str, parent_run_id: str):
        del cve_id, parent_run_id
        self.calls.append(plan.operator_id)
        return EnrichmentOperatorExecution(
            operator_id=plan.operator_id,
            status=EnrichmentAttemptStatus.BLOCKED,
            blocked_reason="SourceFetchFailed",
        )


class _SupplementalReferenceExecutor:
    def __init__(self, factory: async_sessionmaker[AsyncSession], object_id: str) -> None:
        self._factory = factory
        self._object_id = object_id
        self.calls: list[str] = []

    async def execute(self, plan, *, cve_id: str, parent_run_id: str):
        del cve_id, parent_run_id
        self.calls.append(plan.operator_id)
        async with self._factory() as session, session.begin():
            revision = KnowledgeRevisionModel(committed_at=NOW + timedelta(seconds=1))
            session.add(revision)
            await session.flush()
            pr_id = str(uuid4())
            session.add(
                ObjectModel(
                    object_id=pr_id,
                    object_type="PullRequest",
                    canonical_key="github:vllm-project/vllm:pull:43426",
                    properties={"number": 43426},
                    created_revision=revision.revision,
                )
            )
            session.add(
                RelationModel(
                    relation_id=str(uuid4()),
                    source_object_id=self._object_id,
                    relation_type="references-development-object",
                    target_object_id=pr_id,
                    qualifier={
                        "reference_url": "https://github.com/vllm-project/vllm/pull/43426",
                        "reference_kind": "pull_request",
                        "vocabulary_revision": VOCABULARY_REVISION,
                        "vocabulary_scope": "canonical",
                    },
                    origin="deterministic_derived",
                    lifecycle="accepted",
                    processing_run_id=None,
                    created_revision=revision.revision,
                )
            )
        return EnrichmentOperatorExecution(
            operator_id=plan.operator_id,
            status=EnrichmentAttemptStatus.SUCCEEDED,
            semantic_outcomes={
                EnrichmentDimension.FIX_REMEDIATION: EnrichmentSemanticOutcome.RESOLVED
            },
            output_refs=["relation:references-development-object"],
        )


@pytest.mark.asyncio
async def test_background_enrichment_task_reaches_fixed_point_through_canonical_world() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            object_id, _ = await _seed_vulnerability(session)
            run_id = await _create_enrichment_run(session, object_id=object_id)

        executor = _ResolvingExecutor(factory, object_id)
        runtime = EnrichmentRoleRuntime(factory, executor, stream_name=STREAM, now=lambda: NOW)
        outcome = await runtime.run(run_id)

        assert outcome.run_status is TaskRunStatus.COMPLETED
        assert outcome.result.dimension_status == {
            EnrichmentDimension.EXPLOIT_STATE: EnrichmentStatus.RESOLVED
        }
        assert outcome.result.stop_reason == "enrichment_goal_satisfied"
        assert executor.calls == ["provider.cisa_kev"]

        async with factory() as session:
            run = await session.get(TaskRunModel, run_id)
            assert run is not None and run.status == TaskRunStatus.COMPLETED.value
            attempts = list(
                await session.scalars(
                    select(EnrichmentAttemptModel).where(
                        EnrichmentAttemptModel.task_run_id == run_id
                    )
                )
            )
            assert len(attempts) == 1
            assert attempts[0].world_revision_after is not None
            events = await list_task_events(session, run_id)
        assert [event.event_type for event in events] == [
            TaskEventType.TASK_CREATED,
            TaskEventType.TASK_PATCHED,
            TaskEventType.TASK_STARTED,
            TaskEventType.PROGRESS,
            TaskEventType.ENRICHMENT_STATE_CHANGED,
            TaskEventType.TASK_COMPLETED,
        ]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_resolved_dimension_still_executes_pending_supplemental_graph_plan() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            object_id, revision = await _seed_vulnerability(
                session,
                cve_id="CVE-2026-48746",
            )
            session.add(
                ClaimModel(
                    claim_id=str(uuid4()),
                    subject_id=object_id,
                    predicate="github_references",
                    value=["https://github.com/vllm-project/vllm/pull/43426"],
                    qualifier={
                        "source_id": "github-global-advisories",
                        "vocabulary_revision": VOCABULARY_REVISION,
                        "vocabulary_scope": "source_specific",
                    },
                    origin="source_asserted",
                    lifecycle="accepted",
                    processing_run_id=None,
                    created_revision=revision,
                )
            )
            version_id = str(uuid4())
            session.add(
                ObjectModel(
                    object_id=version_id,
                    object_type="SoftwareVersion",
                    canonical_key="software-version:pip:vllm:0.22.0",
                    properties={"version": "0.22.0"},
                    created_revision=revision,
                )
            )
            session.add(
                RelationModel(
                    relation_id=str(uuid4()),
                    source_object_id=object_id,
                    relation_type="fixed-version",
                    target_object_id=version_id,
                    qualifier={
                        "source_id": "github-global-advisories",
                        "vocabulary_revision": VOCABULARY_REVISION,
                        "vocabulary_scope": "canonical",
                    },
                    origin="source_asserted",
                    lifecycle="accepted",
                    processing_run_id=None,
                    created_revision=revision,
                )
            )
            run_id = await _create_enrichment_run(
                session,
                object_id=object_id,
                cve_id="CVE-2026-48746",
                required_dimensions=[EnrichmentDimension.FIX_REMEDIATION],
            )

        executor = _SupplementalReferenceExecutor(factory, object_id)
        outcome = await EnrichmentRoleRuntime(
            factory,
            executor,
            stream_name=STREAM,
            now=lambda: NOW,
        ).run(run_id)

        assert outcome.run_status is TaskRunStatus.COMPLETED
        assert outcome.result.dimension_status[EnrichmentDimension.FIX_REMEDIATION] is (
            EnrichmentStatus.RESOLVED
        )
        assert executor.calls == ["graph.github_references"]
        assert outcome.result.attempted_operators == ["graph.github_references"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_successful_authority_lookup_can_close_dimension_as_explicit_unknown() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            object_id, _ = await _seed_vulnerability(session)
            run_id = await _create_enrichment_run(session, object_id=object_id)

        executor = _UnknownExecutor()
        outcome = await EnrichmentRoleRuntime(
            factory, executor, stream_name=STREAM, now=lambda: NOW
        ).run(run_id)

        assert outcome.run_status is TaskRunStatus.COMPLETED
        assert (
            outcome.result.dimension_status[EnrichmentDimension.EXPLOIT_STATE]
            is EnrichmentStatus.UNKNOWN
        )
        assert executor.calls == ["provider.cisa_kev"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_provider_block_is_execution_state_and_missing_dimension_blocks_task() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            object_id, _ = await _seed_vulnerability(session)
            run_id = await _create_enrichment_run(session, object_id=object_id)

        executor = _BlockedExecutor()
        outcome = await EnrichmentRoleRuntime(
            factory, executor, stream_name=STREAM, now=lambda: NOW
        ).run(run_id)

        assert outcome.run_status is TaskRunStatus.BLOCKED
        assert (
            outcome.result.dimension_status[EnrichmentDimension.EXPLOIT_STATE]
            is EnrichmentStatus.MISSING
        )
        assert outcome.result.blocked_dimensions == [EnrichmentDimension.EXPLOIT_STATE]
        assert outcome.result.stop_reason == "no_eligible_enrichment_operator"
        assert outcome.result.attempted_operators == ["provider.cisa_kev"]
        assert executor.calls == ["provider.cisa_kev"]

        async with factory() as session:
            events = await list_task_events(session, run_id)
        assert TaskEventType.ENRICHMENT_STATE_CHANGED not in {event.event_type for event in events}
        assert events[-1].event_type is TaskEventType.TASK_BLOCKED
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_delegated_enrichment_child_uses_same_runtime_and_state_path() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            object_id, _ = await _seed_vulnerability(session)
            parent_contract = TaskContract(
                task_contract_id="parent-investigation",
                contract_revision=1,
                principal="user:alice",
                task_kind=TaskKind.INVESTIGATE_INCIDENT,
                target_resources=[f"object:{object_id}"],
                desired_state={"goal": "verify exploitation"},
                evidence_contract={},
                output_contract={},
                temporal_contract={"scope": "current"},
                effect_ceiling=EffectCeiling.INTERNAL_STATE,
                delegation_ceiling=DelegationCeiling(
                    allowed=True,
                    max_depth=1,
                    allowed_task_kinds=[TaskKind.ENRICHMENT],
                    child_effect_ceiling=EffectCeiling.INTERNAL_STATE,
                ),
                completion_predicate={"type": "evidence_sufficient_or_blocked"},
                policy_revision="policy-v1",
            )
            parent_manifest = ContextManifest(
                context_id="context:parent",
                context_revision=1,
                task_contract_ref="parent-investigation@1",
                role_ref="InvestigationRole@1",
                knowledge_revision=1,
                object_refs=[object_id],
                policy_context_ref="policy-context:v1",
                capability_envelope_ref="capability:investigation:v1",
                budget_ref="budget:parent",
            )
            parent = await create_task_run(
                session,
                contract=parent_contract,
                manifest=parent_manifest,
                role=canonical_roles()["InvestigationRole"],
                execution_envelope_ref="execution:parent",
                stream_name=STREAM,
                run_id=str(uuid4()),
                now=NOW,
            )
            await transition_task_run(
                session,
                run_id=parent.run_id,
                target=TaskRunStatus.QUEUED,
                payload_ref="queue:investigation",
                idempotency_key="parent:queued",
                stream_name=STREAM,
                now=NOW,
            )
            await transition_task_run(
                session,
                run_id=parent.run_id,
                target=TaskRunStatus.RUNNING,
                payload_ref="role:InvestigationRole",
                idempotency_key="parent:started",
                stream_name=STREAM,
                now=NOW,
            )
            child_run_id = await _create_enrichment_run(
                session,
                object_id=object_id,
                parent_run_id=parent.run_id,
            )

        outcome = await EnrichmentRoleRuntime(
            factory,
            _UnknownExecutor(),
            stream_name=STREAM,
            now=lambda: NOW,
        ).run(child_run_id)
        assert outcome.run_status is TaskRunStatus.COMPLETED

        async with factory() as session:
            child = await session.get(TaskRunModel, child_run_id)
            assert child is not None
            assert child.parent_run_id == parent.run_id
            attempts = list(
                await session.scalars(
                    select(EnrichmentAttemptModel).where(
                        EnrichmentAttemptModel.task_run_id == child_run_id
                    )
                )
            )
            assert len(attempts) == 1
            assert attempts[0].target_object_id == object_id
    finally:
        await engine.dispose()
