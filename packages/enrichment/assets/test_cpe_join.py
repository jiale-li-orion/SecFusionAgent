from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.enrichment.assets.cpe_join import (
    AssetCPEApplicabilityJoinService,
    configuration_matches,
    parse_cpe,
)
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.knowledge.write import EvidenceBackedKnowledgeWriter
from packages.intelligence.normalization.nvd_durable import NVDCanonicalNormalizer
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import (
    EvidenceLinkModel,
    ObjectModel,
    RelationModel,
)
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.db import Base
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

NOW = datetime(2026, 9, 28, 1, 0, tzinfo=UTC)
FIXTURE = json.loads(Path("tests/fixtures/nvd_cve_page.json").read_text())["vulnerabilities"][0]
SOURCES = {item.source_id: item for item in load_source_definitions(Path("config/sources"))}


async def _factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        await sync_source_definitions(
            session,
            [SOURCES["nvd-cves-2"], SOURCES["shodan-assets"]],
        )
        for source_id, run_id in (
            ("nvd-cves-2", "00000000-0000-0000-0000-000000004201"),
            ("shodan-assets", "00000000-0000-0000-0000-000000004202"),
        ):
            session.add(
                AcquisitionRunModel(
                    run_id=run_id,
                    source_id=source_id,
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
    return engine, factory


async def _seed_nvd(factory, store) -> str:
    source = SOURCES["nvd-cves-2"]
    envelope = IngestEnvelope.for_json_payload(
        acquisition_run_id="00000000-0000-0000-0000-000000004201",
        trigger=AcquisitionTrigger.INVESTIGATION,
        source_id=source.source_id,
        external_object_id="CVE-2026-42424",
        payload=FIXTURE,
        canonical_url="https://nvd.nist.gov/vuln/detail/CVE-2026-42424",
        published_at=NOW,
        updated_at=NOW,
        external_revision="fixture-v1",
        observed_at=NOW,
    )
    async with factory() as session, session.begin():
        ack = await EvidenceIngress(store, now=lambda: NOW).accept(session, source, envelope)
        await NVDCanonicalNormalizer(now=lambda: NOW).normalize(session, source, envelope, ack)
    return ack.observation_id


def _asset_envelope(*, port: int, cpes: list[str], revision: str) -> IngestEnvelope:
    return IngestEnvelope.for_json_payload(
        acquisition_run_id="00000000-0000-0000-0000-000000004202",
        trigger=AcquisitionTrigger.INVESTIGATION,
        source_id="shodan-assets",
        external_object_id=f"203.0.113.10:{port}/tcp",
        payload={
            "ip": "203.0.113.10",
            "port": port,
            "transport": "tcp",
            "product": "vLLM",
            "version": None,
            "org": "Example Cloud",
            "isp": "Example ISP",
            "asn": "AS64500",
            "hostnames": ["llm.example.test"],
            "domains": ["example.test"],
            "cpe": cpes,
            "location": {"country_code": "SG"},
        },
        canonical_url=None,
        published_at=None,
        updated_at=NOW,
        external_revision=revision,
        request_metadata={"provider": "shodan", "query": 'product:"vLLM"'},
        observed_at=NOW,
    )


def test_configuration_match_requires_version_and_companion() -> None:
    root = FIXTURE["cve"]["configurations"][0]
    matching = tuple(
        item
        for item in (
            parse_cpe("cpe:/a:example:vllm:0.10.1"),
            parse_cpe("cpe:/h:example:inference_appliance:-"),
        )
        if item is not None
    )
    wrong_version = tuple(
        item
        for item in (
            parse_cpe("cpe:/a:example:vllm:0.11.1"),
            parse_cpe("cpe:/h:example:inference_appliance:-"),
        )
        if item is not None
    )
    missing_companion = tuple(
        item for item in (parse_cpe("cpe:/a:example:vllm:0.10.1"),) if item is not None
    )
    assert configuration_matches(root, matching) is True
    assert configuration_matches(root, wrong_version) is False
    assert configuration_matches(root, missing_companion) is False


@pytest.mark.asyncio
async def test_asset_cpe_join_requires_full_configuration_and_preserves_dual_evidence() -> None:
    engine, factory = await _factory()
    store = MemoryArtifactStore()
    try:
        nvd_observation_id = await _seed_nvd(factory, store)
        service = AssetCPEApplicabilityJoinService(EvidenceBackedKnowledgeWriter(now=lambda: NOW))
        source = SOURCES["shodan-assets"]

        cases = (
            (
                8000,
                [
                    "cpe:/a:example:vllm:0.10.1",
                    "cpe:/h:example:inference_appliance:-",
                ],
                True,
            ),
            (
                8001,
                [
                    "cpe:/a:example:vllm:0.11.1",
                    "cpe:/h:example:inference_appliance:-",
                ],
                False,
            ),
            (8002, ["cpe:/a:example:vllm:0.10.1"], False),
        )
        asset_observations: dict[int, str] = {}
        for port, cpes, should_match in cases:
            envelope = _asset_envelope(port=port, cpes=cpes, revision=f"asset-{port}")
            async with factory() as session, session.begin():
                ack = await EvidenceIngress(store, now=lambda: NOW).accept(
                    session, source, envelope
                )
                asset_observations[port] = ack.observation_id
                result = await service.enrich(
                    session,
                    source=source,
                    envelope=envelope,
                    observation=ack,
                )
                assert result is not None

            async with factory() as session:
                root = await session.scalar(
                    select(ObjectModel).where(
                        ObjectModel.object_type == "InternetAsset",
                        ObjectModel.canonical_key
                        == f"internet-asset:service:203.0.113.10:{port}/tcp",
                    )
                )
                assert root is not None
                affected = list(
                    await session.scalars(
                        select(RelationModel).where(
                            RelationModel.source_object_id == root.object_id,
                            RelationModel.relation_type == "asset-potentially-affected",
                            RelationModel.lifecycle == "accepted",
                            RelationModel.superseded_revision.is_(None),
                        )
                    )
                )
                assert bool(affected) is should_match
                support_types = set(
                    await session.scalars(
                        select(RelationModel.relation_type).where(
                            RelationModel.source_object_id == root.object_id,
                            RelationModel.lifecycle == "accepted",
                            RelationModel.superseded_revision.is_(None),
                        )
                    )
                )
                assert "asset-runs-product" in support_types
                assert "asset-version" in support_types

                if should_match:
                    relation = affected[0]
                    assert relation.qualifier["source_semantics"] == "nvd_cpe_asset_join"
                    evidence_observation_ids = set(
                        await session.scalars(
                            select(EvidenceLinkModel.observation_id).where(
                                EvidenceLinkModel.target_kind == "relation",
                                EvidenceLinkModel.target_id == relation.relation_id,
                            )
                        )
                    )
                    assert asset_observations[port] in evidence_observation_ids
                    assert nvd_observation_id in evidence_observation_ids

        async with factory() as session:
            assert (
                await session.scalar(
                    select(ObservationModel.observation_id).where(
                        ObservationModel.observation_id == nvd_observation_id
                    )
                )
                == nvd_observation_id
            )
    finally:
        await engine.dispose()
