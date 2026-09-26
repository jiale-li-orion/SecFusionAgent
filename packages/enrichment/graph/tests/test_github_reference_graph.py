import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.enrichment.graph.github_references import (
    GitHubReferenceGraphService,
    parse_github_development_reference,
)
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.knowledge.read import get_vulnerability_by_cve
from packages.intelligence.knowledge.write import EvidenceBackedKnowledgeWriter
from packages.intelligence.normalization.nvd_durable import NVDCanonicalNormalizer
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.knowledge_models import RelationModel
from packages.monitoring.acquisition.service import AcquisitionService
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.db import Base
from packages.sources.adapters.github_repo import GitHubRepoAdapter
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

NVD_PAGE = json.loads(Path("tests/fixtures/nvd_cve_page.json").read_text())
PR_PAYLOAD = json.loads(Path("tests/fixtures/github_pull_request.json").read_text())

NOW = datetime(2026, 9, 26, 1, 0, tzinfo=UTC)
SOURCES = {item.source_id: item for item in load_source_definitions(Path("config/sources"))}
NVD = SOURCES["nvd-cves-2"]
GITHUB = SOURCES["github-target-repos"].model_copy(
    update={
        "discovery_method": {
            **SOURCES["github-target-repos"].discovery_method,
            "base_url": "https://api.github.test",
        }
    }
)


def test_parse_github_development_reference() -> None:
    pull = parse_github_development_reference(
        "https://github.com/vllm-project/vllm/pull/9123?diff=split"
    )
    assert pull is not None
    assert pull.repo_full_name == "vllm-project/vllm"
    assert pull.filters["pull_number"] == 9123

    release = parse_github_development_reference(
        "https://github.com/vllm-project/vllm/releases/tag/release%2F0.11.1"
    )
    assert release is not None
    assert release.filters["tag"] == "release/0.11.1"

    assert parse_github_development_reference("https://example.test/fix") is None


@pytest.mark.asyncio
async def test_reference_graph_reenters_github_and_keeps_original_evidence() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    store = MemoryArtifactStore()
    ingress = EvidenceIngress(store, now=lambda: NOW)
    writer = EvidenceBackedKnowledgeWriter(now=lambda: NOW)

    payload = json.loads(json.dumps(NVD_PAGE["vulnerabilities"][0]))
    payload["cve"]["references"] = [
        {
            "url": "https://github.com/vllm-project/vllm/pull/9123",
            "source": "nvd@nist.gov",
        },
        {
            "url": "https://github.com/untracked/example/pull/7",
            "source": "nvd@nist.gov",
        },
    ]
    envelope = IngestEnvelope.for_json_payload(
        acquisition_run_id="nvd-root-run",
        trigger=AcquisitionTrigger.SCHEDULED,
        source_id=NVD.source_id,
        external_object_id="CVE-2026-42424",
        payload=payload,
        canonical_url="https://nvd.nist.gov/vuln/detail/CVE-2026-42424",
        published_at=NOW,
        updated_at=NOW,
        external_revision="2026-09-25T01:45:00+00:00",
        observed_at=NOW,
    )

    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, [NVD, GITHUB])
            session.add(
                AcquisitionRunModel(
                    run_id="nvd-root-run",
                    source_id=NVD.source_id,
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
            )
            observation = await ingress.accept(session, NVD, envelope)
            await NVDCanonicalNormalizer(now=lambda: NOW).normalize(
                session, NVD, envelope, observation
            )
            nvd_observation_id = observation.observation_id

        pr_payload = PR_PAYLOAD

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/repos/vllm-project/vllm/pulls/9123":
                return httpx.Response(200, json=pr_payload, request=request)
            return httpx.Response(404, request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            graph = GitHubReferenceGraphService(
                factory,
                AcquisitionService(factory, now=lambda: NOW),
                ingress,
                writer,
                {NVD.source_id: NVD, GITHUB.source_id: GITHUB},
                {GITHUB.source_id: GitHubRepoAdapter(client)},
            )
            results = await graph.enrich_cve("CVE-2026-42424")
            assert len(results) == 1
            replay = await graph.enrich_cve("CVE-2026-42424")
            assert len(replay) == 1

        async with factory() as session:
            view = await get_vulnerability_by_cve(session, "CVE-2026-42424")
            assert view is not None
            refs = [
                item
                for item in view.relations
                if item.relation_type == "references-development-object"
            ]
            assert len(refs) == 1
            relation = refs[0]
            assert relation.origin == "deterministic_derived"
            assert relation.target.object_type == "PullRequest"
            assert relation.target.external_identifiers["github_pull_request"] == [
                "vllm-project/vllm#9123"
            ]
            assert relation.evidence[0].source_id == NVD.source_id
            assert relation.evidence[0].observation_id == nvd_observation_id
            assert relation.qualifier["reference_kind"] == "pull_request"

            active = list(
                await session.scalars(
                    select(RelationModel).where(
                        RelationModel.relation_type == "references-development-object",
                        RelationModel.superseded_revision.is_(None),
                    )
                )
            )
            assert len(active) == 1
    finally:
        await engine.dispose()
