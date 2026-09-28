import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from fakeredis.aioredis import FakeRedis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from packages.enrichment.runtime.state import EnrichmentStateBuilder, EnrichmentStatus
from packages.intelligence.hot_cache.redis import RedisHotBugCache
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.knowledge.read import get_vulnerability_by_cve
from packages.intelligence.knowledge.vocabulary import EnrichmentDimension
from packages.intelligence.normalization.cvelist_v5 import CVEListV5HotBugNormalizer
from packages.intelligence.normalization.cvelist_v5_durable import CVEListV5CanonicalNormalizer
from packages.intelligence.normalization.hot_bug import HotBugIngress
from packages.intelligence.normalization.nvd import NVDHotBugNormalizer
from packages.intelligence.normalization.nvd_durable import NVDCanonicalNormalizer
from packages.intelligence.promotion.service import PromotionService
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.evidence_models import EvidenceArtifactModel, ObservationModel
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    EvidenceLinkModel,
    ExternalIdentifierModel,
    KnowledgeChangeModel,
    KnowledgeRevisionModel,
    ObjectModel,
    RelationModel,
)
from packages.intelligence.storage.models import ProcessingRunModel
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.db import Base
from packages.shared.storage.models import OutboxEventModel
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

NVD_FIXTURE = json.loads(Path("tests/fixtures/nvd_cve_page.json").read_text())["vulnerabilities"][0]
CVELIST_FIXTURE = {
    "dataType": "CVE_RECORD",
    "dataVersion": "5.2",
    "cveMetadata": {
        "cveId": "CVE-2026-42425",
        "state": "PUBLISHED",
        "assignerShortName": "example-cna",
        "datePublished": "2026-09-25T00:00:00Z",
        "dateUpdated": "2026-09-26T00:00:00Z",
    },
    "containers": {
        "cna": {
            "title": "Example inference server issue",
            "descriptions": [{"lang": "en", "value": "Example security issue."}],
            "affected": [
                {
                    "vendor": "Example",
                    "product": "Inference Server",
                    "defaultStatus": "unaffected",
                    "versions": [
                        {"version": "1.0.0", "status": "affected"},
                        {
                            "version": "1.1.0",
                            "lessThan": "2.0.0",
                            "versionType": "semver",
                            "status": "affected",
                        },
                        {"version": "2.0.0", "status": "unaffected"},
                    ],
                }
            ],
            "references": [{"url": "https://example.invalid/advisory"}],
        }
    },
}


@pytest.mark.asyncio
async def test_hot_bug_promotion_is_durable_traceable_and_idempotent() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    source = next(
        item
        for item in load_source_definitions(Path("config/sources"))
        if item.source_id == "nvd-cves-2"
    )
    payload = NVD_FIXTURE
    now = datetime(2026, 9, 25, 6, 0, tzinfo=UTC)

    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, [source])
            session.add(
                AcquisitionRunModel(
                    run_id="promotion-run",
                    source_id=source.source_id,
                    trigger="scheduled",
                    parent_run_id=None,
                    query_spec={},
                    status="success",
                    cursor_in={},
                    cursor_out={},
                    attempt=1,
                    created_at=now,
                    started_at=now,
                    finished_at=now,
                )
            )

        envelope = IngestEnvelope.for_json_payload(
            acquisition_run_id="promotion-run",
            trigger=AcquisitionTrigger.SCHEDULED,
            source_id=source.source_id,
            external_object_id="CVE-2026-42424",
            payload=payload,
            canonical_url="https://nvd.nist.gov/vuln/detail/CVE-2026-42424",
            published_at=now,
            updated_at=now,
            external_revision="2026-09-25T06:00:00+00:00",
            observed_at=now,
        )
        redis_client = FakeRedis()
        cache = RedisHotBugCache(cast(Any, redis_client))
        hot_ingress = HotBugIngress(
            cache,
            {"nvd": NVDHotBugNormalizer()},
            ttl_seconds=3600,
            now=lambda: now,
        )
        await hot_ingress.accept(source, envelope)

        artifact_store = MemoryArtifactStore()
        promotion = PromotionService(
            cache,
            EvidenceIngress(artifact_store, now=lambda: now),
            {"nvd": NVDCanonicalNormalizer(now=lambda: now)},
        )
        async with factory() as session, session.begin():
            first = await promotion.promote_hot_bug(session, source, "CVE-2026-42424")
        assert first.observation.replay is False
        assert first.normalization.knowledge_revision == 1

        async with factory() as session:
            assert await _count(session, ObservationModel) == 1
            assert await _count(session, EvidenceArtifactModel) == 1
            assert await _count(session, KnowledgeRevisionModel) == 1
            assert await _count(session, ObjectModel) == 5
            assert await _count(session, ExternalIdentifierModel) == 2
            assert await _count(session, ClaimModel) > 0
            assert await _count(session, RelationModel) == 4
            assert await _count(session, EvidenceLinkModel) == (
                await _count(session, ClaimModel) + await _count(session, RelationModel)
            )
            assert await _count(session, KnowledgeChangeModel) == 1
            assert await _count(session, OutboxEventModel) == 2
            topics = set(await session.scalars(select(OutboxEventModel.topic)))
            assert topics == {"knowledge.changed", "enrichment.requested"}
            view = await get_vulnerability_by_cve(session, "cve-2026-42424")
            assert view is not None
            assert view.object_type == "Vulnerability"
            assert view.external_identifiers == {"cve": ["CVE-2026-42424"]}
            cvss = next(claim for claim in view.claims if claim.predicate == "cvss_score")
            assert cvss.value == 9.8
            assert cvss.qualifier["vocabulary_revision"] == "enrichment-v1"
            assert cvss.qualifier["vocabulary_scope"] == "canonical"
            assert cvss.evidence[0].source_id == source.source_id
            assert cvss.evidence[0].locator["kind"] == "jsonpath"
            cvss_version = next(
                claim for claim in view.claims if claim.predicate == "cvss_version"
            )
            assert cvss_version.value == "3.1"
            weakness = next(
                relation for relation in view.relations if relation.relation_type == "has-weakness"
            )
            assert weakness.target.object_type == "Weakness"
            assert weakness.target.canonical_key == "weakness:CWE-306"
            assert weakness.target.external_identifiers == {"cwe": ["CWE-306"]}
            assert weakness.evidence[0].source_id == source.source_id
            poc = next(
                relation for relation in view.relations if relation.relation_type == "has-poc"
            )
            assert poc.target.object_type == "ExploitArtifact"
            assert poc.target.properties["url"] == (
                "https://example.test/exploits/CVE-2026-42424-poc"
            )
            assert poc.evidence[0].source_id == source.source_id
            assert poc.evidence[0].locator["path"] == "$.cve.references[1]"
            vendor_advisory = next(
                relation
                for relation in view.relations
                if relation.relation_type == "vendor-advisory"
            )
            assert vendor_advisory.target.object_type == "Document"
            assert vendor_advisory.target.properties["url"] == (
                "https://example.test/advisories/CVE-2026-42424"
            )
            assert vendor_advisory.qualifier["source_semantics"] == (
                "nvd_vendor_advisory_tag"
            )
            assert vendor_advisory.evidence[0].locator["path"] == "$.cve.references[0]"
            applicability = next(
                relation
                for relation in view.relations
                if relation.relation_type == "applicability-status"
            )
            assert applicability.target.object_type == "Product"
            assert applicability.target.properties == {
                "identity_scheme": "cpe23_product",
                "cpe_part": "a",
                "vendor": "example",
                "product": "vllm",
            }
            assert applicability.qualifier["state"] == "affected"
            assert applicability.qualifier["source_semantics"] == "nvd_cpe"
            assert applicability.qualifier["platform"] == (
                "cpe:2.3:a:example:vllm:*:*:*:*:*:*:*:*"
            )
            assert applicability.qualifier["version_range"] == {
                "versionEndExcluding": "0.11.1"
            }
            configuration = applicability.qualifier["configuration"]
            assert isinstance(configuration, dict)
            assert configuration["root_operator"] == "AND"
            assert configuration["node_path"] == [0]
            root_snapshot = configuration["root_snapshot"]
            assert isinstance(root_snapshot, dict)
            nodes = root_snapshot["nodes"]
            assert isinstance(nodes, list)
            companion = nodes[1]
            assert isinstance(companion, dict)
            cpe_matches = companion["cpeMatch"]
            assert isinstance(cpe_matches, list)
            hardware = cpe_matches[0]
            assert isinstance(hardware, dict)
            assert hardware["vulnerable"] is False
            assert applicability.evidence[0].locator["path"] == (
                "$.cve.configurations[0].nodes[0].cpeMatch[0]"
            )

        async with factory() as session, session.begin():
            replay = await promotion.promote_hot_bug(session, source, "CVE-2026-42424")
        assert replay.observation.replay is True
        assert replay.normalization.knowledge_revision == first.normalization.knowledge_revision

        async with factory() as session:
            assert await _count(session, ObservationModel) == 1
            assert await _count(session, KnowledgeRevisionModel) == 1
            assert await _count(session, KnowledgeChangeModel) == 1
            assert await _count(session, ProcessingRunModel) == 1
            assert await _count(session, RelationModel) == 4
        await redis_client.aclose()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_cvelist_hot_bug_can_promote_into_same_canonical_vulnerability_layer() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    source = next(
        item
        for item in load_source_definitions(Path("config/sources"))
        if item.source_id == "cve-program-cvelist-v5"
    )
    now = datetime(2026, 9, 26, 6, 0, tzinfo=UTC)
    cve_id = "CVE-2026-42425"

    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, [source])
            session.add(
                AcquisitionRunModel(
                    run_id="cvelist-promotion-run",
                    source_id=source.source_id,
                    trigger="scheduled",
                    parent_run_id=None,
                    query_spec={},
                    status="success",
                    cursor_in={},
                    cursor_out={},
                    attempt=1,
                    created_at=now,
                    started_at=now,
                    finished_at=now,
                )
            )

        envelope = IngestEnvelope.for_json_payload(
            acquisition_run_id="cvelist-promotion-run",
            trigger=AcquisitionTrigger.SCHEDULED,
            source_id=source.source_id,
            external_object_id=cve_id,
            payload=CVELIST_FIXTURE,
            canonical_url=(
                "https://raw.githubusercontent.com/CVEProject/cvelistV5/main/"
                "cves/2026/42xxx/CVE-2026-42425.json"
            ),
            published_at=now,
            updated_at=now,
            external_revision="2026-09-26T00:00:00+00:00",
            observed_at=now,
        )
        redis_client = FakeRedis()
        cache = RedisHotBugCache(cast(Any, redis_client))
        await HotBugIngress(
            cache,
            {"cvelist_v5": CVEListV5HotBugNormalizer()},
            ttl_seconds=3600,
            now=lambda: now,
        ).accept(source, envelope)

        promotion = PromotionService(
            cache,
            EvidenceIngress(MemoryArtifactStore(), now=lambda: now),
            {"cvelist_v5": CVEListV5CanonicalNormalizer(now=lambda: now)},
        )
        async with factory() as session, session.begin():
            result = await promotion.promote_hot_bug(session, source, cve_id)
        assert result.observation.replay is False

        async with factory() as session:
            view = await get_vulnerability_by_cve(session, cve_id)
            assert view is not None
            title = next(claim for claim in view.claims if claim.predicate == "title")
            assert title.value == "Example inference server issue"
            assert title.qualifier["vocabulary_scope"] == "source_specific"
            assert title.qualifier["vocabulary_revision"] == "enrichment-v1"
            assert title.evidence[0].source_id == source.source_id
            affected = next(
                claim for claim in view.claims if claim.predicate == "affected_products"
            )
            assert affected.value == ["Example/Inference Server"]
            outgoing = [
                relation
                for relation in view.relations
                if relation.evidence and relation.evidence[0].source_id == source.source_id
            ]
            affects_product = next(
                relation for relation in outgoing if relation.relation_type == "affects-product"
            )
            assert affects_product.target.object_type == "Product"
            assert affects_product.target.properties["identity_scheme"] == "cve5_vendor_product"
            assert affects_product.target.properties["vendor"] == "Example"
            assert affects_product.target.properties["product"] == "Inference Server"
            assert affects_product.qualifier["source_semantics"] == "cve5_affected_entry"

            applicability = [
                relation
                for relation in outgoing
                if relation.relation_type == "applicability-status"
            ]
            assert len(applicability) == 4
            exact = next(
                relation
                for relation in applicability
                if relation.qualifier.get("scope") == {
                    "kind": "version_rule",
                    "version": "1.0.0",
                }
            )
            assert exact.qualifier["state"] == "affected"
            assert exact.qualifier["source_status"] == "affected"
            assert exact.evidence[0].locator["path"] == (
                "$.containers.cna.affected[0].versions[0]"
            )
            ranged = next(
                relation
                for relation in applicability
                if relation.qualifier.get("scope") == {
                    "kind": "version_rule",
                    "version": "1.1.0",
                    "version_type": "semver",
                    "less_than": "2.0.0",
                }
            )
            assert ranged.qualifier["state"] == "affected"
            unaffected = next(
                relation
                for relation in applicability
                if relation.qualifier.get("scope") == {
                    "kind": "version_rule",
                    "version": "2.0.0",
                }
            )
            assert unaffected.qualifier["state"] == "not_affected"
            default = next(
                relation
                for relation in applicability
                if relation.qualifier.get("scope") == {"kind": "default"}
            )
            assert default.qualifier["state"] == "not_affected"
            assert default.qualifier["source_status"] == "unaffected"

            enrichment_state = await EnrichmentStateBuilder().build(
                session,
                view.object_id,
                materialize=False,
            )
            version_state = enrichment_state.by_dimension()[
                EnrichmentDimension.VERSION_APPLICABILITY
            ]
            assert version_state.status is EnrichmentStatus.RESOLVED
            assert version_state.conflict_refs == []
            topics = set(await session.scalars(select(OutboxEventModel.topic)))
            assert topics == {"knowledge.changed", "enrichment.requested"}
        await redis_client.aclose()
    finally:
        await engine.dispose()


async def _count(session: AsyncSession, model: type[Any]) -> int:
    value = await session.scalar(select(func.count()).select_from(model))
    return int(value or 0)
