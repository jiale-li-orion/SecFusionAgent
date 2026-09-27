from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete, select

from apps.runtime_models import register_runtime_models
from apps.task_admission import create_task_contract_service
from packages.enrichment.runtime.executor import EnrichmentOperatorExecution
from packages.enrichment.runtime.role import EnrichmentRoleRuntime
from packages.enrichment.runtime.state import (
    EnrichmentAttemptStatus,
    EnrichmentSemanticOutcome,
    EnrichmentStatus,
)
from packages.enrichment.runtime.state_models import (
    EnrichmentAttemptModel,
    EnrichmentDimensionStateModel,
)
from packages.enrichment.runtime.tasks import (
    build_vulnerability_enrichment_contract,
    ensure_background_vulnerability_enrichment_run,
)
from packages.intelligence.knowledge.vocabulary import EnrichmentDimension
from packages.intelligence.storage.knowledge_models import (
    ExternalIdentifierModel,
    KnowledgeRevisionModel,
    ObjectModel,
)
from packages.runtime.policy.loader import load_runtime_policy
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.task_runtime.contracts.models import ContextManifest, TaskRunStatus
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

NOW = datetime(2026, 9, 27, 3, 0, tzinfo=UTC)


class _UnknownExecutor:
    async def execute(self, plan, *, cve_id: str, parent_run_id: str):
        del cve_id, parent_run_id
        return EnrichmentOperatorExecution(
            operator_id=plan.operator_id,
            status=EnrichmentAttemptStatus.SUCCEEDED,
            semantic_outcomes={
                EnrichmentDimension.EXPLOIT_STATE: EnrichmentSemanticOutcome.UNKNOWN
            },
        )


@pytest.mark.asyncio
async def test_real_pg_enrichment_task_state_and_background_replay() -> None:
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    redis = Redis.from_url(settings.redis_task_bus_url, decode_responses=True)
    suffix = uuid4().hex
    cve_id = f"CVE-2026-{int(suffix[:6], 16) % 90000 + 10000}"
    object_id = str(uuid4())
    trigger_ref = str(uuid4())
    role_run_id = str(uuid4())
    role_task_id = f"integration-enrichment:{suffix}"
    role_context_id = f"context:integration-enrichment:{suffix}"
    stream = f"{settings.task_event_stream_name}:enrichment:{suffix}"
    task_admission = create_task_contract_service(
        load_runtime_policy(Path(settings.runtime_policy_path))
    )
    background_run_id: str | None = None
    background_task_id: str | None = None
    background_context_id: str | None = None
    revision_id: int | None = None
    run_ids: list[str] = []

    try:
        await redis.delete(stream)
        async with factory() as session, session.begin():
            revision = KnowledgeRevisionModel(
                cause_processing_run_id=trigger_ref,
                committed_at=NOW,
            )
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
            contract = build_vulnerability_enrichment_contract(
                task_contract_id=role_task_id,
                principal="integration:user",
                target_object_id=object_id,
                cve_id=cve_id,
                required_dimensions=[EnrichmentDimension.EXPLOIT_STATE],
                policy_revision="policy-v1",
            )
            manifest = ContextManifest(
                context_id=role_context_id,
                context_revision=1,
                task_contract_ref=f"{role_task_id}@1",
                role_ref="EnrichmentRole@1",
                knowledge_revision=revision.revision,
                object_refs=[object_id],
                policy_context_ref="policy-context:v1",
                capability_envelope_ref="capability:enrichment:v1",
                budget_ref=f"budget:{role_run_id}",
            )
            await create_task_run(
                session,
                contract=contract,
                manifest=manifest,
                role=canonical_roles()["EnrichmentRole"],
                execution_envelope_ref=f"execution:{role_run_id}",
                stream_name=stream,
                run_id=role_run_id,
                now=NOW,
            )
            run_ids.append(role_run_id)

        outcome = await EnrichmentRoleRuntime(
            factory,
            _UnknownExecutor(),
            stream_name=stream,
            now=lambda: NOW,
        ).run(role_run_id)
        assert outcome.run_status is TaskRunStatus.COMPLETED
        assert (
            outcome.result.dimension_status[EnrichmentDimension.EXPLOIT_STATE]
            is EnrichmentStatus.UNKNOWN
        )

        async with factory() as session, session.begin():
            background_run_id = await ensure_background_vulnerability_enrichment_run(
                session,
                object_id=object_id,
                cve_id=cve_id,
                trigger_ref=trigger_ref,
                stream_name=stream,
                task_contract_service=task_admission,
            )
            background = await session.get(TaskRunModel, background_run_id)
            assert background is not None
            background_task_id = background.task_contract_id
            background_context_id = background.context_id
            run_ids.append(background_run_id)

        async with factory() as session, session.begin():
            replay_run_id = await ensure_background_vulnerability_enrichment_run(
                session,
                object_id=object_id,
                cve_id=cve_id,
                trigger_ref=trigger_ref,
                stream_name=stream,
                task_contract_service=task_admission,
            )
            assert replay_run_id == background_run_id
            matching_runs = list(
                await session.scalars(
                    select(TaskRunModel).where(TaskRunModel.run_id == background_run_id)
                )
            )
            assert len(matching_runs) == 1

        async with factory() as session, session.begin():
            await dispatch_pending_task_events(session, redis, now=NOW + timedelta(days=1))

        messages = await redis.xrange(stream)
        role_messages = [fields for _, fields in messages if fields["task_run_id"] == role_run_id]
        assert [int(fields["seq"]) for fields in role_messages] == list(
            range(1, len(role_messages) + 1)
        )
        assert role_messages[-1]["event_type"] == "TaskCompleted"

        async with factory() as session:
            role_run = await session.get(TaskRunModel, role_run_id)
            assert role_run is not None and role_run.status == TaskRunStatus.COMPLETED.value
            attempts = list(
                await session.scalars(
                    select(EnrichmentAttemptModel).where(
                        EnrichmentAttemptModel.task_run_id == role_run_id
                    )
                )
            )
            assert len(attempts) == 1
            states = list(
                await session.scalars(
                    select(EnrichmentDimensionStateModel).where(
                        EnrichmentDimensionStateModel.target_object_id == object_id,
                        EnrichmentDimensionStateModel.dimension
                        == EnrichmentDimension.EXPLOIT_STATE.value,
                    )
                )
            )
            assert len(states) == 1
            assert states[0].status == EnrichmentStatus.UNKNOWN.value
    finally:
        if run_ids:
            async with factory() as session, session.begin():
                event_ids = list(
                    await session.scalars(
                        select(TaskEventModel.event_id).where(
                            TaskEventModel.task_run_id.in_(run_ids)
                        )
                    )
                )
                if event_ids:
                    await session.execute(
                        delete(TaskEventDeliveryModel).where(
                            TaskEventDeliveryModel.event_id.in_(event_ids)
                        )
                    )
                    await session.execute(
                        delete(TaskEventModel).where(TaskEventModel.event_id.in_(event_ids))
                    )
                await session.execute(
                    delete(EnrichmentAttemptModel).where(
                        EnrichmentAttemptModel.task_run_id.in_(run_ids)
                    )
                )
                await session.execute(
                    delete(EnrichmentDimensionStateModel).where(
                        EnrichmentDimensionStateModel.target_object_id == object_id
                    )
                )
                await session.execute(delete(TaskRunModel).where(TaskRunModel.run_id.in_(run_ids)))
                context_ids = [role_context_id]
                if background_context_id:
                    context_ids.append(background_context_id)
                await session.execute(
                    delete(ContextManifestVersionModel).where(
                        ContextManifestVersionModel.context_id.in_(context_ids)
                    )
                )
                task_ids = [role_task_id]
                if background_task_id:
                    task_ids.append(background_task_id)
                await session.execute(
                    delete(TaskContractVersionModel).where(
                        TaskContractVersionModel.task_contract_id.in_(task_ids)
                    )
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
        await redis.delete(stream)
        await redis.aclose()
        await engine.dispose()
