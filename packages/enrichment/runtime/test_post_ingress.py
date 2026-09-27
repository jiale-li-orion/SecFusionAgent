from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.enrichment.runtime.post_ingress import (
    ObservationProcessingRuntime,
    PostIngressStatus,
)
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.document_models import DocumentRevisionModel
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import ClaimModel, ObjectModel, RelationModel
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.db import Base
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope, SourceDefinition
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

NOW = datetime(2026, 9, 27, 2, 0, tzinfo=UTC)
FIXTURES = Path("tests/fixtures")
SOURCES = {item.source_id: item for item in load_source_definitions(Path("config/sources"))}


async def _factory_for(*sources: SourceDefinition):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        await sync_source_definitions(session, list(sources))
    return engine, factory


async def _add_run(factory, source: SourceDefinition, run_id: str) -> None:
    async with factory() as session, session.begin():
        session.add(
            AcquisitionRunModel(
                run_id=run_id,
                source_id=source.source_id,
                trigger="investigation",
                parent_run_id=None,
                query_spec={},
                status="success",
                cursor_in={},
                cursor_out={},
                attempt=1,
                created_at=NOW,
                started_at=NOW,
                finished_at=NOW,
            )
        )


async def _seed_observation(factory, store, source, envelope) -> str:
    async with factory() as session, session.begin():
        ack = await EvidenceIngress(store, now=lambda: NOW).accept(session, source, envelope)
    return ack.observation_id


@pytest.mark.asyncio
async def test_managed_document_backfill_processes_existing_observation_idempotently() -> None:
    source = SOURCES["anthropic-research"]
    engine, factory = await _factory_for(source)
    store = MemoryArtifactStore()
    run_id = "00000000-0000-0000-0000-000000001101"
    try:
        await _add_run(factory, source, run_id)
        envelope = IngestEnvelope.for_binary_payload(
            acquisition_run_id=run_id,
            trigger=AcquisitionTrigger.INVESTIGATION,
            source_id=source.source_id,
            external_object_id="managed-report-1",
            body=("agent security report " * 120).encode(),
            media_type="text/plain",
            canonical_url="https://example.invalid/report",
            published_at=NOW,
            updated_at=NOW,
            external_revision="v1",
            request_metadata={"title": "Managed report"},
            observed_at=NOW,
        )
        observation_id = await _seed_observation(factory, store, source, envelope)
        runtime = ObservationProcessingRuntime(store)
        async with factory() as session, session.begin():
            first = await runtime.process(session, source, observation_id)
        assert first.status is PostIngressStatus.PROCESSED
        assert first.handler == "managed_document"
        assert first.output_refs["chunk_count"]
        async with factory() as session, session.begin():
            second = await runtime.process(session, source, observation_id)
        assert second.status is PostIngressStatus.REPLAY
        async with factory() as session:
            assert (
                await session.scalar(select(func.count()).select_from(DocumentRevisionModel)) == 1
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_nvd_backfill_builds_canonical_vulnerability_from_existing_observation() -> None:
    source = SOURCES["nvd-cves-2"]
    engine, factory = await _factory_for(source)
    store = MemoryArtifactStore()
    run_id = "00000000-0000-0000-0000-000000001102"
    try:
        await _add_run(factory, source, run_id)
        payload = json.loads((FIXTURES / "nvd_cve_page.json").read_text())["vulnerabilities"][0]
        envelope = IngestEnvelope.for_json_payload(
            acquisition_run_id=run_id,
            trigger=AcquisitionTrigger.INVESTIGATION,
            source_id=source.source_id,
            external_object_id="CVE-2026-42424",
            payload=payload,
            canonical_url="https://nvd.nist.gov/vuln/detail/CVE-2026-42424",
            published_at=NOW,
            updated_at=NOW,
            external_revision="nvd-v1",
            observed_at=NOW,
        )
        observation_id = await _seed_observation(factory, store, source, envelope)
        runtime = ObservationProcessingRuntime(store)
        async with factory() as session, session.begin():
            result = await runtime.process(session, source, observation_id)
        assert result.status is PostIngressStatus.PROCESSED
        assert result.handler == "canonical_bug"
        async with factory() as session:
            objects = list(
                await session.scalars(
                    select(ObjectModel).where(ObjectModel.object_type == "Vulnerability")
                )
            )
            assert len(objects) == 1
            claims = list(await session.scalars(select(ClaimModel)))
            assert {claim.predicate for claim in claims} >= {"cvss_score", "references"}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_osv_backfill_builds_package_relation_from_existing_observation() -> None:
    nvd_source = SOURCES["nvd-cves-2"]
    source = SOURCES["osv-vulnerabilities"]
    engine, factory = await _factory_for(nvd_source, source)
    store = MemoryArtifactStore()
    nvd_run_id = "00000000-0000-0000-0000-000000001102"
    run_id = "00000000-0000-0000-0000-000000001103"
    try:
        await _add_run(factory, nvd_source, nvd_run_id)
        await _add_run(factory, source, run_id)
        runtime = ObservationProcessingRuntime(store)

        nvd_payload = json.loads((FIXTURES / "nvd_cve_page.json").read_text())["vulnerabilities"][0]
        nvd_envelope = IngestEnvelope.for_json_payload(
            acquisition_run_id=nvd_run_id,
            trigger=AcquisitionTrigger.INVESTIGATION,
            source_id=nvd_source.source_id,
            external_object_id="CVE-2026-42424",
            payload=nvd_payload,
            canonical_url="https://nvd.nist.gov/vuln/detail/CVE-2026-42424",
            published_at=NOW,
            updated_at=NOW,
            external_revision="nvd-v1",
            observed_at=NOW,
        )
        nvd_observation_id = await _seed_observation(factory, store, nvd_source, nvd_envelope)
        async with factory() as session, session.begin():
            nvd_result = await runtime.process(session, nvd_source, nvd_observation_id)
        assert nvd_result.status is PostIngressStatus.PROCESSED

        payload = json.loads((FIXTURES / "osv_cve.json").read_text())
        envelope = IngestEnvelope.for_json_payload(
            acquisition_run_id=run_id,
            trigger=AcquisitionTrigger.INVESTIGATION,
            source_id=source.source_id,
            external_object_id="CVE-2026-42424",
            payload=payload,
            canonical_url="https://api.osv.dev/v1/vulns/CVE-2026-42424",
            published_at=NOW,
            updated_at=NOW,
            external_revision="osv-v1",
            observed_at=NOW,
        )
        observation_id = await _seed_observation(factory, store, source, envelope)
        async with factory() as session, session.begin():
            result = await runtime.process(session, source, observation_id)
        assert result.status is PostIngressStatus.PROCESSED
        assert result.handler == "time_bounded_enrichment"
        async with factory() as session:
            relations = list(await session.scalars(select(RelationModel)))
            assert {relation.relation_type for relation in relations} == {"affects-package"}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_asset_backfill_preserves_context_without_promoting_affectedness() -> None:
    source = SOURCES["shodan-assets"]
    engine, factory = await _factory_for(source)
    store = MemoryArtifactStore()
    run_id = "00000000-0000-0000-0000-000000001104"
    try:
        await _add_run(factory, source, run_id)
        envelope = IngestEnvelope.for_json_payload(
            acquisition_run_id=run_id,
            trigger=AcquisitionTrigger.INVESTIGATION,
            source_id=source.source_id,
            external_object_id="18.165.98.58:80/tcp",
            payload={
                "ip": "18.165.98.58",
                "port": 80,
                "transport": "tcp",
                "product": "Amazon CloudFront",
                "version": None,
                "hostnames": ["server-18-165-98-58.iad55.r.cloudfront.net"],
                "cpe": ["cpe:/a:amazon:amazon_cloudfront"],
            },
            canonical_url=None,
            published_at=None,
            updated_at=NOW,
            external_revision=NOW.isoformat(),
            request_metadata={
                "provider": "shodan-internetdb",
                "query": "ip=18.165.98.58",
                "discovery_context": {
                    "hostname": "datasets-server.huggingface.co",
                    "shared_edge": True,
                },
                "relation_context": {
                    "type": "public-service-asset-observation",
                    "strength": "context-only",
                },
            },
            observed_at=NOW,
        )
        observation_id = await _seed_observation(factory, store, source, envelope)
        runtime = ObservationProcessingRuntime(store)
        async with factory() as session, session.begin():
            result = await runtime.process(session, source, observation_id)
        assert result.status is PostIngressStatus.PROCESSED
        assert result.handler == "asset_observation"
        assert result.output_refs["relation_context"] == {
            "type": "public-service-asset-observation",
            "strength": "context-only",
        }
        async with factory() as session:
            assert await session.scalar(select(func.count()).select_from(ObjectModel)) == 0
            assert await session.scalar(select(func.count()).select_from(RelationModel)) == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_legacy_github_pull_request_blocks_when_request_metadata_was_not_preserved() -> None:
    source = SOURCES["github-target-repos"]
    engine, factory = await _factory_for(source)
    store = MemoryArtifactStore()
    run_id = "00000000-0000-0000-0000-000000001105"
    try:
        await _add_run(factory, source, run_id)
        payload = json.loads((FIXTURES / "github_pull_request.json").read_text())
        envelope = IngestEnvelope.for_json_payload(
            acquisition_run_id=run_id,
            trigger=AcquisitionTrigger.INVESTIGATION,
            source_id=source.source_id,
            external_object_id="vllm-project/vllm:pull_request:9123",
            payload=payload,
            canonical_url="https://github.com/vllm-project/vllm/pull/9123",
            published_at=NOW,
            updated_at=NOW,
            external_revision="pr-v1",
            request_metadata={
                "object_type": "pull_request",
                "repo_full_name": "vllm-project/vllm",
            },
            observed_at=NOW,
        )
        observation_id = await _seed_observation(factory, store, source, envelope)
        async with factory() as session, session.begin():
            row = await session.get(ObservationModel, observation_id)
            assert row is not None
            row.request_metadata = {}
            row.request_metadata_captured = False
        runtime = ObservationProcessingRuntime(store)
        async with factory() as session, session.begin():
            result = await runtime.process(session, source, observation_id)
        assert result.status is PostIngressStatus.BLOCKED
        assert result.detail is not None
        assert "historical request metadata missing" in result.detail
        async with factory() as session:
            assert await session.scalar(select(func.count()).select_from(RelationModel)) == 0
    finally:
        await engine.dispose()
