from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.application.commands.start_investigation import (
    StartInvestigationCommand,
    StartInvestigationUseCase,
)
from apps.nvd_observation import NVDObservationPort, nvd_capability_registry
from apps.runtime_models import register_runtime_models
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import (
    EvidenceLinkModel,
    ExternalIdentifierModel,
    KnowledgeRevisionModel,
    ObjectModel,
)
from packages.investigation.perception.contracts import (
    PerceptionOperation,
    PerceptionRequest,
    PerceptionTarget,
)
from packages.investigation.perception.planner import PerceptionPlanner
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.runtime.artifacts import MemoryRuntimeBlobStore, RuntimeArtifactService
from packages.runtime.budget import BudgetGovernor
from packages.runtime.policy.loader import load_runtime_policy
from packages.runtime.storage.models import CapabilityInvocationModel
from packages.shared.config import get_settings
from packages.shared.db import Base
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions
from packages.task_runtime.contracts.models import TaskKind
from packages.task_runtime.storage.models import TaskRunModel


@pytest.mark.asyncio
async def test_official_cve_read_promotes_one_audited_evidence_ref(tmp_path) -> None:
    register_runtime_models()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'nvd.sqlite'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = get_settings().model_copy(
        update={
            "artifact_store_backend": "filesystem",
            "artifact_root": tmp_path / "artifacts",
        }
    )
    cve_id = "CVE-2026-42424"
    object_id = "product-vuln-object"
    async with factory() as session, session.begin():
        source = next(
            item
            for item in load_source_definitions(settings.source_registry_path)
            if item.source_id == "nvd-cves-2"
        )
        await sync_source_definitions(session, [source])
        revision = KnowledgeRevisionModel(committed_at=datetime.now(UTC))
        session.add(revision)
        await session.flush()
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
                external_identifier_id="test-cve-id",
                namespace="cve",
                value=cve_id,
                object_id=object_id,
            )
        )
    async with factory() as session:
        result = await StartInvestigationUseCase(
            policy_path=settings.runtime_policy_path,
            task_event_stream_name=settings.task_event_stream_name,
        ).execute(
            session,
            StartInvestigationCommand(
                principal="user:test",
                request_id="nvd-investigation-request",
                cve_id=cve_id,
                goal="Check official CVE record",
                evidence_question="What does the official record say?",
                task_kind=TaskKind.VERIFY_VERSION_FIX,
            ),
        )
    case_id = result.investigation.case_id
    async with factory() as session:
        run = await session.scalar(select(TaskRunModel).where(TaskRunModel.case_id == case_id))
        assert run is not None
        run_id = run.run_id

    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.params["cveId"] == cve_id
        return httpx.Response(
            200,
            json={
                "vulnerabilities": [
                    {
                        "cve": {
                            "id": cve_id,
                            "published": "2026-10-01T00:00:00.000",
                            "lastModified": "2026-10-02T00:00:00.000",
                            "descriptions": [
                                {"lang": "en", "value": "A tested official description."}
                            ],
                        }
                    }
                ]
            },
        )

    request = PerceptionRequest(
        request_id="nvd-perception-request",
        case_id=case_id,
        operation=PerceptionOperation.OBSERVE_EXTERNAL,
        target=PerceptionTarget(object_id=object_id),
        desired_observation="Read current NVD CVE record",
    )
    step = PerceptionPlanner().plan(request).steps[0]
    policy = load_runtime_policy(settings.runtime_policy_path)
    registry = nvd_capability_registry()
    artifacts = RuntimeArtifactService(MemoryRuntimeBlobStore())
    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            port = NVDObservationPort(
                settings, factory, client, artifacts, registry, policy, BudgetGovernor()
            )
            first = await port.execute(task_run_id=run_id, request=request, step=step)
            replay = await port.execute(task_run_id=run_id, request=request, step=step)
            fresh_request = request.model_copy(update={"request_id": "nvd-fresh-request"})
            fresh = await port.execute(
                task_run_id=run_id,
                request=fresh_request,
                step=PerceptionPlanner().plan(fresh_request).steps[0],
            )
            escaped_request = request.model_copy(
                update={
                    "request_id": "nvd-outside-task",
                    "target": PerceptionTarget(object_id="another-vulnerability"),
                }
            )
            escaped = await port.execute(
                task_run_id=run_id,
                request=escaped_request,
                step=PerceptionPlanner().plan(escaped_request).steps[0],
            )
        assert calls == 2, first.unresolved
        assert len(first.observation_handles) == 1
        assert len(first.candidates) == 1
        assert first.candidates[0].evidence_ref is not None
        assert replay.candidates[0].evidence_ref == first.candidates[0].evidence_ref
        assert len(fresh.candidates) == 1
        assert first.observed_propositions[0].statement.startswith("NVD description:")
        assert escaped.candidates == []
        assert escaped.unresolved == ["capability_no_observation:failed:executor_exception"]
        async with factory() as session:
            assert await session.scalar(select(func.count()).select_from(AcquisitionRunModel)) == 2
            assert (
                await session.scalar(select(func.count()).select_from(CapabilityInvocationModel))
                == 3
            )
            assert await session.scalar(select(func.count()).select_from(ObservationModel)) == 1
            assert await session.scalar(select(func.count()).select_from(EvidenceLinkModel)) == 2
    finally:
        await engine.dispose()
