from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from packages.enrichment.processors.osv import OSVMapper
from packages.intelligence.documents.parsers import PlainTextDocumentParser
from packages.intelligence.documents.service import ManagedDocumentService
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.knowledge.contracts import EvidenceAnchor
from packages.intelligence.knowledge.read import get_vulnerability_by_cve
from packages.intelligence.knowledge.write import EvidenceBackedKnowledgeWriter
from packages.intelligence.normalization.nvd_durable import NVDCanonicalNormalizer
from packages.intelligence.projections.service import (
    CurrentProjectionService,
    get_current_projection,
)
from packages.intelligence.retrieval.contracts import EmbeddingBatch
from packages.intelligence.retrieval.indexing import DocumentIndexService
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.document_models import DocumentChunkModel
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("SECFUSION_RUN_INTEGRATION") != "1",
        reason="set SECFUSION_RUN_INTEGRATION=1 to run local infrastructure tests",
    ),
]

NOW = datetime(2026, 9, 26, 13, 0, tzinfo=UTC)
SOURCES = {item.source_id: item for item in load_source_definitions(Path("config/sources"))}
NVD = SOURCES["nvd-cves-2"]
OSV = SOURCES["osv-vulnerabilities"]
MANAGED = SOURCES["trailofbits-research"]
NVD_PAYLOAD = json.loads(Path("tests/fixtures/nvd_cve_page.json").read_text())["vulnerabilities"][0]
OSV_PAYLOAD = json.loads(Path("tests/fixtures/osv_cve.json").read_text())
CVE_ID = "CVE-2026-42424"


class FixedEmbeddingProvider:
    async def embed(self, texts: list[str]) -> EmbeddingBatch:
        return EmbeddingBatch(
            model="m3-handoff-fixed",
            version="1",
            dimensions=3,
            vectors=[[1.0, float(index), 0.5] for index, _ in enumerate(texts)],
        )


@pytest.mark.asyncio
async def test_m3_handoff_is_projection_relation_retrieval_and_evidence_ready() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    store = MemoryArtifactStore()
    ingress = EvidenceIngress(store, now=lambda: NOW)
    writer = EvidenceBackedKnowledgeWriter(now=lambda: NOW)
    nvd_run = str(uuid4())
    osv_run = str(uuid4())
    document_run = str(uuid4())

    try:
        async with factory() as session:
            await session.begin()
            try:
                await sync_source_definitions(session, [NVD, OSV, MANAGED])
                session.add_all(
                    [
                        _run(nvd_run, NVD.source_id),
                        _run(osv_run, OSV.source_id),
                        _run(document_run, MANAGED.source_id),
                    ]
                )
                await session.flush()

                nvd_envelope = IngestEnvelope.for_json_payload(
                    acquisition_run_id=nvd_run,
                    trigger=AcquisitionTrigger.SCHEDULED,
                    source_id=NVD.source_id,
                    external_object_id=CVE_ID,
                    payload=NVD_PAYLOAD,
                    canonical_url=f"https://nvd.nist.gov/vuln/detail/{CVE_ID}",
                    published_at=NOW,
                    updated_at=NOW,
                    external_revision="nvd-handoff-v1",
                    observed_at=NOW,
                )
                nvd_observation = await ingress.accept(session, NVD, nvd_envelope)
                nvd_result = await NVDCanonicalNormalizer(now=lambda: NOW).normalize(
                    session,
                    NVD,
                    nvd_envelope,
                    nvd_observation,
                )
                root_id = nvd_result.object_ids[0]

                osv_envelope = IngestEnvelope.for_json_payload(
                    acquisition_run_id=osv_run,
                    trigger=AcquisitionTrigger.ON_DEMAND,
                    source_id=OSV.source_id,
                    external_object_id=CVE_ID,
                    payload=OSV_PAYLOAD,
                    canonical_url=f"https://api.osv.dev/v1/vulns/{CVE_ID}",
                    published_at=NOW,
                    updated_at=NOW,
                    external_revision="osv-handoff-v1",
                    observed_at=NOW,
                )
                osv_observation = await ingress.accept(session, OSV, osv_envelope)
                osv_result = await writer.apply(
                    session,
                    root_object_id=root_id,
                    source=OSV,
                    observation=EvidenceAnchor(
                        observation_id=osv_observation.observation_id,
                        artifact_id=osv_observation.artifact_id,
                    ),
                    candidate=OSVMapper().map(osv_envelope),
                    processor_name=OSVMapper.PROCESSOR_NAME,
                    processor_version=OSVMapper.PROCESSOR_VERSION,
                )

                upstream_revision = max(
                    nvd_result.knowledge_revision,
                    osv_result.knowledge_revision,
                )
                await CurrentProjectionService(now=lambda: NOW).rebuild_knowledge_object_views(
                    session,
                    object_id=root_id,
                    upstream_revision=upstream_revision,
                )

                document_envelope = IngestEnvelope.for_binary_payload(
                    acquisition_run_id=document_run,
                    trigger=AcquisitionTrigger.SCHEDULED,
                    source_id=MANAGED.source_id,
                    external_object_id=f"handoff-{uuid4()}",
                    body=(
                        f"Independent analysis of {CVE_ID}. The affected vLLM package "
                        "requires a patched release. Root cause evidence remains source-bound."
                    ).encode(),
                    media_type="text/plain",
                    canonical_url="https://example.invalid/m3-handoff",
                    published_at=NOW,
                    updated_at=NOW,
                    external_revision="article-v1",
                    request_metadata={"title": "M3 handoff probe"},
                    observed_at=NOW,
                )
                managed = await ManagedDocumentService(
                    ingress,
                    {"text/plain": PlainTextDocumentParser()},
                    now=lambda: NOW,
                ).ingest(session, MANAGED, document_envelope)
                indexer = DocumentIndexService()
                await indexer.build_lexical_index(
                    session,
                    document_revision_id=managed.document_revision_id,
                )
                await indexer.build_dense_index(
                    session,
                    document_revision_id=managed.document_revision_id,
                    provider=FixedEmbeddingProvider(),
                )

                view = await get_vulnerability_by_cve(session, CVE_ID)
                assert view is not None
                assert view.claims
                assert any(item.relation_type == "affects-package" for item in view.relations)
                assert all(item.evidence for item in view.claims)
                assert all(item.evidence for item in view.relations)
                evidence_refs = [evidence for item in view.claims for evidence in item.evidence] + [
                    evidence for item in view.relations for evidence in item.evidence
                ]
                for evidence in evidence_refs:
                    assert evidence.observation_id
                    assert evidence.artifact_id
                    assert evidence.external_revision
                    assert evidence.locator

                vulnerability = await get_current_projection(
                    session,
                    projection_type="current_vulnerability_view",
                    projection_key=CVE_ID,
                )
                affected = await get_current_projection(
                    session,
                    projection_type="current_affected_versions",
                    projection_key=CVE_ID,
                )
                fix = await get_current_projection(
                    session,
                    projection_type="current_fix_status",
                    projection_key=CVE_ID,
                )
                assert vulnerability is not None
                assert affected is not None
                assert fix is not None
                assert affected.data["affected_entries"]
                assert fix.data["status"] == "known"
                fixed_commits = fix.data["fixed_commits"]
                assert isinstance(fixed_commits, list)
                # Raw OSV GIT boundaries may be visible as candidates, but M3
                # must not claim they are confirmed until the deterministic
                # commit verifier has produced an explicit fixed-by relation.
                assert fixed_commits
                assert all(
                    not bool(item.get("confirmed"))
                    for item in fixed_commits
                    if isinstance(item, dict)
                )

                chunks = list(
                    await session.scalars(
                        select(DocumentChunkModel).where(
                            DocumentChunkModel.document_revision_id == managed.document_revision_id
                        )
                    )
                )
                assert chunks
                assert {chunk.index_status for chunk in chunks} == {"retrieval_ready"}
                assert all(chunk.embedding is not None for chunk in chunks)
                lexical_matches = await session.scalar(
                    text(
                        "SELECT count(*) FROM document_chunks "
                        "WHERE document_revision_id = :revision_id "
                        "AND to_tsvector('simple', coalesce(text, '')) "
                        "@@ plainto_tsquery('simple', :query)"
                    ),
                    {
                        "revision_id": managed.document_revision_id,
                        "query": CVE_ID,
                    },
                )
                assert int(lexical_matches or 0) >= 1
            finally:
                await session.rollback()
    finally:
        await engine.dispose()


def _run(run_id: str, source_id: str) -> AcquisitionRunModel:
    return AcquisitionRunModel(
        run_id=run_id,
        source_id=source_id,
        trigger="scheduled",
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
