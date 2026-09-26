import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.enrichment.graph.fix_boundary import DeterministicFixBoundaryService
from packages.enrichment.processors.osv import OSVMapper
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.knowledge.contracts import EvidenceAnchor
from packages.intelligence.knowledge.read import get_vulnerability_by_cve
from packages.intelligence.knowledge.write import EvidenceBackedKnowledgeWriter
from packages.intelligence.normalization.nvd_durable import NVDCanonicalNormalizer
from packages.intelligence.projections.service import (
    CurrentProjectionService,
    get_current_projection,
)
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.monitoring.acquisition.service import AcquisitionService
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.db import Base
from packages.sources.adapters.github_repo import GitHubRepoAdapter
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

NVD_PAGE = json.loads(Path("tests/fixtures/nvd_cve_page.json").read_text())
OSV_PAYLOAD = json.loads(Path("tests/fixtures/osv_cve.json").read_text())
COMMIT_PAYLOAD = json.loads(Path("tests/fixtures/github_commit.json").read_text())

NOW = datetime(2026, 9, 26, 4, 0, tzinfo=UTC)
SOURCES = {item.source_id: item for item in load_source_definitions(Path("config/sources"))}
NVD = SOURCES["nvd-cves-2"]
OSV = SOURCES["osv-vulnerabilities"]
GITHUB = SOURCES["github-target-repos"].model_copy(
    update={
        "discovery_method": {
            **SOURCES["github-target-repos"].discovery_method,
            "base_url": "https://api.github.test",
        }
    }
)


@pytest.mark.asyncio
async def test_osv_git_boundary_confirms_fix_commit_without_treating_sha_as_version() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    store = MemoryArtifactStore()
    ingress = EvidenceIngress(store, now=lambda: NOW)
    writer = EvidenceBackedKnowledgeWriter(now=lambda: NOW)
    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, [NVD, OSV, GITHUB])
            session.add_all(
                [
                    _run("nvd-root-run", NVD.source_id),
                    _run("osv-fix-run", OSV.source_id),
                ]
            )

        nvd_payload = json.loads(json.dumps(NVD_PAGE["vulnerabilities"][0]))
        nvd_envelope = IngestEnvelope.for_json_payload(
            acquisition_run_id="nvd-root-run",
            trigger=AcquisitionTrigger.SCHEDULED,
            source_id=NVD.source_id,
            external_object_id="CVE-2026-42424",
            payload=nvd_payload,
            canonical_url="https://nvd.nist.gov/vuln/detail/CVE-2026-42424",
            published_at=NOW,
            updated_at=NOW,
            external_revision="nvd-v1",
            observed_at=NOW,
        )
        async with factory() as session, session.begin():
            observation = await ingress.accept(session, NVD, nvd_envelope)
            await NVDCanonicalNormalizer(now=lambda: NOW).normalize(
                session, NVD, nvd_envelope, observation
            )

        async with factory() as session:
            root = await get_vulnerability_by_cve(session, "CVE-2026-42424")
            assert root is not None
            root_id = root.object_id

        osv_envelope = IngestEnvelope.for_json_payload(
            acquisition_run_id="osv-fix-run",
            trigger=AcquisitionTrigger.ON_DEMAND,
            source_id=OSV.source_id,
            external_object_id="CVE-2026-42424",
            payload=OSV_PAYLOAD,
            canonical_url="https://api.osv.dev/v1/vulns/CVE-2026-42424",
            published_at=NOW,
            updated_at=NOW,
            external_revision="osv-v1",
            observed_at=NOW,
        )
        async with factory() as session, session.begin():
            osv_observation = await ingress.accept(session, OSV, osv_envelope)
            await writer.apply(
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
            osv_observation_id = osv_observation.observation_id

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == (
                "/repos/vllm-project/vllm/commits/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            ):
                return httpx.Response(200, json=COMMIT_PAYLOAD, request=request)
            return httpx.Response(404, request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            verifier = DeterministicFixBoundaryService(
                factory,
                AcquisitionService(factory, now=lambda: NOW),
                ingress,
                writer,
                {OSV.source_id: OSV, GITHUB.source_id: GITHUB},
                {GITHUB.source_id: GitHubRepoAdapter(client)},
            )
            results = await verifier.enrich_cve("CVE-2026-42424")
            assert len(results) == 1
            replay = await verifier.enrich_cve("CVE-2026-42424")
            assert len(replay) == 1

        async with factory() as session:
            view = await get_vulnerability_by_cve(session, "CVE-2026-42424")
            assert view is not None
            fixed = [item for item in view.relations if item.relation_type == "fixed-by"]
            assert len(fixed) == 1
            relation = fixed[0]
            assert relation.origin == "deterministic_derived"
            assert relation.target.object_type == "Commit"
            assert relation.target.external_identifiers["git_commit_sha"] == [
                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            ]
            assert relation.qualifier["repo_full_name"] == "vllm-project/vllm"
            assert relation.evidence[0].source_id == OSV.source_id
            assert relation.evidence[0].observation_id == osv_observation_id
            assert relation.evidence[0].locator["path"] == (
                "$.affected[0].ranges[1].events[1].fixed"
            )

            max_revision = max(
                item.created_revision
                for item in view.relations
                if item.relation_type in {"affects-package", "fixed-by"}
            )

        async with factory() as session, session.begin():
            await CurrentProjectionService(now=lambda: NOW).rebuild_knowledge_object_views(
                session,
                object_id=root_id,
                upstream_revision=max_revision,
            )

        async with factory() as session:
            projection = await get_current_projection(
                session,
                projection_type="current_fix_status",
                projection_key="CVE-2026-42424",
            )
            assert projection is not None
            versions = projection.data["fixed_versions"]
            assert isinstance(versions, list)
            assert {item["version"] for item in versions if isinstance(item, dict)} == {"0.11.1"}
            commits = projection.data["fixed_commits"]
            assert isinstance(commits, list)
            assert len(commits) == 1
            assert commits[0]["sha"] == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            assert commits[0]["confirmed"] is True
    finally:
        await engine.dispose()


def _run(run_id: str, source_id: str) -> AcquisitionRunModel:
    return AcquisitionRunModel(
        run_id=run_id,
        source_id=source_id,
        trigger="on_demand",
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
