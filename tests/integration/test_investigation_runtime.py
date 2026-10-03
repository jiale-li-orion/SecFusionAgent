from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete, select

from apps.runtime_models import register_runtime_models
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import (
    EvidenceLinkModel,
    ExternalIdentifierModel,
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
    InvestigationFrame,
    PerceptionAction,
    StatePatchAction,
)
from packages.investigation.runtime.role import InvestigationRoleRuntime
from packages.investigation.runtime.tasks import build_investigation_contract
from packages.investigation.state.contracts import (
    EvidenceNeedContract,
    ProposedState,
    StatePatch,
    StatePatchOperation,
)
from packages.investigation.state.service import InvestigationStateService
from packages.investigation.storage.models import InvestigationCaseModel
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.sources.storage.models import SourceModel
from packages.task_runtime.contracts.models import ContextManifest, TaskKind, TaskRunStatus
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.events.redis_stream import dispatch_pending_task_events
from packages.task_runtime.storage.models import (
    ContextManifestVersionModel,
    TaskContractVersionModel,
    TaskEventDeliveryModel,
    TaskEventModel,
    TaskRunModel,
)
from packages.task_runtime.storage.service import create_task_run

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("SECFUSION_RUN_INTEGRATION") != "1",
        reason="set SECFUSION_RUN_INTEGRATION=1 to run local infrastructure tests",
    ),
]


class _VerifyEvidencePlanner:
    async def next_action(self, frame: InvestigationFrame):
        assert frame.selected_need is not None
        object_id = frame.selected_need.target_objects[0]
        if frame.last_percept is None:
            return PerceptionAction(
                request=PerceptionRequest(
                    request_id=f"verify-evidence:{frame.task_contract.task_contract_id}",
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
        assert frame.last_percept.source_roles == ["primary"]
        assert frame.last_percept.unresolved == []
        return StatePatchAction(
            patch=StatePatch(
                patch_id=f"verify-patch:{frame.task_contract.task_contract_id}",
                case_id=frame.state.case_id,
                base_case_revision=frame.state.case_revision,
                producer="integration:InvestigationRole",
                operations=[
                    StatePatchOperation(
                        proposition=frame.selected_need.proposition_or_question,
                        target_ref=f"object:{object_id}",
                        proposed_state=ProposedState.CONFIRMED,
                        evidence_refs=list(frame.last_percept.evidence_handles),
                        resolves_need_id=frame.selected_need.need_id,
                    )
                ],
            )
        )


@pytest.mark.asyncio
async def test_real_pg_investigation_role_state_gate_and_task_event_roundtrip() -> None:
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    redis = Redis.from_url(settings.redis_task_bus_url, decode_responses=True)
    now = datetime.now(UTC)
    suffix = uuid4().hex
    object_id = str(uuid4())
    cve_id = f"CVE-2026-{int(suffix[:6], 16) % 90000 + 10000}"
    observation_id = str(uuid4())
    evidence_id = str(uuid4())
    need_id = str(uuid4())
    run_id = str(uuid4())
    task_contract_id = f"integration-verify:{suffix}"
    context_id = f"context:integration-verify:{suffix}"
    stream = f"{settings.task_event_stream_name}:investigation:{suffix}"
    case_id: str | None = None
    revision_id: int | None = None

    try:
        await redis.delete(stream)
        async with factory() as session, session.begin():
            source = await session.get(SourceModel, "openai-safety")
            assert source is not None
            assert source.source_role == "primary"

            revision = KnowledgeRevisionModel(committed_at=now)
            session.add(revision)
            await session.flush()
            revision_id = revision.revision
            session.add(
                ObjectModel(
                    object_id=object_id,
                    object_type="Vulnerability",
                    canonical_key=f"cve:{cve_id}",
                    properties={"display_name": cve_id},
                    created_revision=revision.revision,
                )
            )
            await session.flush()
            session.add(
                ExternalIdentifierModel(
                    external_identifier_id=str(uuid4()),
                    namespace="cve",
                    value=cve_id,
                    object_id=object_id,
                )
            )
            session.add(
                ObservationModel(
                    observation_id=observation_id,
                    source_id="openai-safety",
                    acquisition_run_id=None,
                    acquisition_trigger="replay",
                    external_object_id=f"integration-advisory:{suffix}",
                    external_revision="v1",
                    canonical_url=f"https://example.invalid/{suffix}",
                    published_at=now,
                    updated_at=now,
                    observed_at=now,
                    content_hash=uuid4().hex + uuid4().hex,
                    request_metadata={},
                    request_metadata_captured=True,
                    idempotency_key=uuid4().hex + uuid4().hex,
                    created_at=now,
                )
            )
            await session.flush()
            session.add(
                EvidenceLinkModel(
                    evidence_link_id=evidence_id,
                    target_kind="object",
                    target_id=object_id,
                    observation_id=observation_id,
                    artifact_id=None,
                    locator={"kind": "integration", "field": "fixed_release"},
                    locator_hash=uuid4().hex + uuid4().hex,
                )
            )
            case = await CaseService(now=lambda: now).create(
                session,
                task_signature="verify-fix-boundary",
                target_object_ids=[object_id],
                goal="Verify the fixed release from durable primary evidence.",
                initial_knowledge_revision=revision.revision,
            )
            case_id = case.case_id
            opened = await InvestigationStateService(now=lambda: now).open_evidence_need(
                session,
                case_id=case.case_id,
                base_case_revision=0,
                need_id=need_id,
                proposition_or_question="Primary evidence establishes fixed release v0.22.0",
                purpose="verify_fix_release",
                target_objects=[object_id],
                evidence_contract=EvidenceNeedContract(
                    required_source_roles=["primary"],
                    min_independent_sources=1,
                ),
            )
            assert opened.state.case_revision == 1

            contract = build_investigation_contract(
                task_contract_id=task_contract_id,
                principal="integration:user",
                task_kind=TaskKind.VERIFY_VERSION_FIX,
                case_id=case.case_id,
                target_object_ids=[object_id],
                required_need_ids=[need_id],
                policy_revision="policy-v1",
            )
            manifest = ContextManifest(
                context_id=context_id,
                context_revision=1,
                task_contract_ref=f"{task_contract_id}@1",
                role_ref="InvestigationRole@1",
                case_ref=case.case_id,
                knowledge_revision=revision.revision,
                investigation_state_ref=f"case:{case.case_id}@1",
                object_refs=[object_id],
                evidence_refs=[evidence_id],
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
                stream_name=stream,
                case_id=case.case_id,
                run_id=run_id,
                now=now,
            )

        outcome = await InvestigationRoleRuntime(
            factory,
            _VerifyEvidencePlanner(),
            stream_name=stream,
            now=lambda: now,
        ).run(run_id)
        assert outcome.run_status is TaskRunStatus.COMPLETED
        assert outcome.result.resolved_need_ids == [need_id]
        assert outcome.result.final_case_revision == 4

        async with factory() as session, session.begin():
            await dispatch_pending_task_events(
                session,
                redis,
                now=now + timedelta(minutes=1),
            )
            delivery_statuses = list(
                await session.scalars(
                    select(TaskEventDeliveryModel.status)
                    .join(
                        TaskEventModel,
                        TaskEventModel.event_id == TaskEventDeliveryModel.event_id,
                    )
                    .where(TaskEventModel.task_run_id == run_id)
                    .order_by(TaskEventModel.seq)
                )
            )
            assert delivery_statuses == ["delivered"] * 8

        messages = [
            fields for _, fields in await redis.xrange(stream) if fields["task_run_id"] == run_id
        ]
        assert [int(item["seq"]) for item in messages] == list(range(1, len(messages) + 1))
        assert [item["event_type"] for item in messages] == [
            "TaskCreated",
            "TaskPatched",
            "TaskStarted",
            "EvidenceFound",
            "ContextUpdated",
            "InvestigationStateChanged",
            "ContextUpdated",
            "TaskCompleted",
        ]

        async with factory() as session:
            state = await InvestigationStateService().get_state(session, case_id)
            assert state.case_revision == 4
            assert len(state.confirmed) == 1
            assert state.confirmed[0].evidence_refs == [evidence_id]
            run = await session.get(TaskRunModel, run_id)
            assert run is not None and run.status == TaskRunStatus.COMPLETED.value
    finally:
        async with factory() as session, session.begin():
            event_ids = list(
                await session.scalars(
                    select(TaskEventModel.event_id).where(TaskEventModel.task_run_id == run_id)
                )
            )
            await session.execute(delete(TaskRunModel).where(TaskRunModel.run_id == run_id))
            await session.execute(
                delete(ContextManifestVersionModel).where(
                    ContextManifestVersionModel.context_id == context_id
                )
            )
            await session.execute(
                delete(TaskContractVersionModel).where(
                    TaskContractVersionModel.task_contract_id == task_contract_id
                )
            )
            if case_id is not None:
                await session.execute(
                    delete(InvestigationCaseModel).where(InvestigationCaseModel.case_id == case_id)
                )
            await session.execute(
                delete(EvidenceLinkModel).where(EvidenceLinkModel.evidence_link_id == evidence_id)
            )
            await session.execute(
                delete(ObservationModel).where(ObservationModel.observation_id == observation_id)
            )
            await session.execute(
                delete(ExternalIdentifierModel).where(
                    ExternalIdentifierModel.object_id == object_id
                )
            )
            await session.execute(delete(ObjectModel).where(ObjectModel.object_id == object_id))
            if revision_id is not None:
                await session.execute(
                    delete(KnowledgeRevisionModel).where(
                        KnowledgeRevisionModel.revision == revision_id
                    )
                )
            del event_ids
        await redis.delete(stream)
        await redis.aclose()
        await engine.dispose()
