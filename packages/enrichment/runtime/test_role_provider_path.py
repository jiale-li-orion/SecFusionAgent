from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.enrichment.graph.fix_boundary import DeterministicFixBoundaryService
from packages.enrichment.graph.github_references import GitHubReferenceGraphService
from packages.enrichment.planner import VulnerabilityEnrichmentPlanner
from packages.enrichment.runtime.executor import DefaultEnrichmentOperatorExecutor
from packages.enrichment.runtime.role import EnrichmentRoleRuntime
from packages.enrichment.runtime.tasks import build_vulnerability_enrichment_contract
from packages.enrichment.service import VulnerabilityEnrichmentService
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.knowledge.vocabulary import EnrichmentDimension
from packages.intelligence.knowledge.write import EvidenceBackedKnowledgeWriter
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    ExternalIdentifierModel,
    KnowledgeRevisionModel,
    ObjectModel,
)
from packages.monitoring.acquisition.service import AcquisitionService
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.db import Base
from packages.sources.adapters.cisa_kev import CISAKEVAdapter
from packages.sources.contracts import SourceAdapter
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions
from packages.task_runtime.contracts.models import ContextManifest, TaskRunStatus
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.service import create_task_run

FIXTURES = Path("tests/fixtures")
NOW = datetime(2026, 9, 27, 2, 45, tzinfo=UTC)
STREAM = "secfusion:task-events:provider-path"


@pytest.mark.asyncio
async def test_real_provider_path_flows_back_through_evidence_and_knowledge_gate() -> None:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    sources = {item.source_id: item for item in load_source_definitions(Path("config/sources"))}
    payload = json.loads((FIXTURES / "cisa_kev.json").read_text())
    cve_id = "CVE-2026-42424"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    artifact_store = MemoryArtifactStore()
    ingress = EvidenceIngress(artifact_store, now=lambda: NOW)
    writer = EvidenceBackedKnowledgeWriter(now=lambda: NOW)
    acquisition = AcquisitionService(factory, now=lambda: NOW)
    adapters: dict[str, SourceAdapter] = {"cisa-kev": CISAKEVAdapter(client)}

    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, list(sources.values()))
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
            contract = build_vulnerability_enrichment_contract(
                task_contract_id=f"enrichment:{cve_id}",
                principal="system:background-enrichment",
                target_object_id=object_id,
                cve_id=cve_id,
                required_dimensions=[EnrichmentDimension.EXPLOIT_STATE],
                policy_revision="policy-v1",
            )
            manifest = ContextManifest(
                context_id=f"context:{cve_id}",
                context_revision=1,
                task_contract_ref=f"{contract.task_contract_id}@1",
                role_ref="EnrichmentRole@1",
                knowledge_revision=revision.revision,
                object_refs=[object_id],
                policy_context_ref="policy-context:v1",
                capability_envelope_ref="capability:enrichment:v1",
                budget_ref=f"budget:{cve_id}",
            )
            task_run = await create_task_run(
                session,
                contract=contract,
                manifest=manifest,
                role=canonical_roles()["EnrichmentRole"],
                execution_envelope_ref=f"execution:{cve_id}",
                stream_name=STREAM,
                run_id=str(uuid4()),
                now=NOW,
            )

        provider_service = VulnerabilityEnrichmentService(
            factory,
            acquisition,
            ingress,
            writer,
            VulnerabilityEnrichmentPlanner(),
            sources,
            adapters,
        )
        executor = DefaultEnrichmentOperatorExecutor(
            provider_service,
            GitHubReferenceGraphService(factory, acquisition, ingress, writer, sources, adapters),
            DeterministicFixBoundaryService(
                factory, acquisition, ingress, writer, sources, adapters
            ),
        )
        outcome = await EnrichmentRoleRuntime(
            factory,
            executor,
            stream_name=STREAM,
            now=lambda: NOW,
        ).run(task_run.run_id)

        assert outcome.run_status is TaskRunStatus.COMPLETED
        assert (
            outcome.result.dimension_status[EnrichmentDimension.EXPLOIT_STATE].value == "resolved"
        )

        async with factory() as session:
            known_exploited = list(
                await session.scalars(
                    select(ClaimModel).where(
                        ClaimModel.subject_id == object_id,
                        ClaimModel.predicate == "known_exploited",
                        ClaimModel.superseded_revision.is_(None),
                    )
                )
            )
            observations = list(await session.scalars(select(ObservationModel)))
            acquisition_runs = list(
                await session.scalars(
                    select(AcquisitionRunModel).where(
                        AcquisitionRunModel.parent_run_id == task_run.run_id
                    )
                )
            )
        assert len(known_exploited) == 1
        assert known_exploited[0].value is True
        assert len(observations) == 1
        assert observations[0].source_id == "cisa-kev"
        assert len(acquisition_runs) == 1
        assert acquisition_runs[0].status == "success"
        assert acquisition_runs[0].query_spec == {"filters": {"cve_id": cve_id}}
    finally:
        await client.aclose()
        await engine.dispose()
