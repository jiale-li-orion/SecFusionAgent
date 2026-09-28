from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.evaluation.m1_m3 import EnrichmentFactKey
from packages.intelligence.knowledge.vocabulary import EnrichmentDimension
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import EvidenceLinkModel
from packages.shared.db import Base
from scripts.evaluate_real_enrichment import (
    STRUCTURED_SNAPSHOT_SOURCE_IDS,
    _prediction_for_target,
)

NOW = datetime(2026, 9, 28, 3, 0, tzinfo=UTC)


def _fact() -> EnrichmentFactKey:
    return EnrichmentFactKey(
        root_object_key="cve:CVE-2026-0001",
        root_object_type="Vulnerability",
        kind="claim",
        dimension=EnrichmentDimension.SEVERITY,
        predicate_or_relation_type="cvss_score",
        normalized_value_or_target_id="9.8",
    )


def _observation(observation_id: str, source_id: str) -> ObservationModel:
    return ObservationModel(
        observation_id=observation_id,
        source_id=source_id,
        acquisition_run_id=None,
        acquisition_trigger="replay",
        external_object_id="CVE-2026-0001",
        external_revision="r1",
        canonical_url=None,
        published_at=None,
        updated_at=NOW,
        observed_at=NOW,
        content_hash=f"hash-{observation_id}",
        request_metadata={},
        request_metadata_captured=True,
        idempotency_key=f"idem-{observation_id}",
        created_at=NOW,
    )


def _link(link_id: str, target_id: str, observation_id: str) -> EvidenceLinkModel:
    return EvidenceLinkModel(
        evidence_link_id=link_id,
        target_kind="claim",
        target_id=target_id,
        observation_id=observation_id,
        artifact_id=None,
        locator={"kind": "jsonpath", "path": "$.metric"},
        locator_hash=f"locator-{link_id}",
    )


@pytest.mark.asyncio
async def test_prediction_scope_keeps_snapshot_sources_and_ignores_external_sources() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session, session.begin():
            session.add_all(
                [
                    _observation("obs-nvd", "nvd-cves-2"),
                    _observation("obs-cve5", "cve-program-cvelist-v5"),
                ]
            )
            await session.flush()
            session.add_all(
                [
                    _link("link-nvd", "target-mixed", "obs-nvd"),
                    _link("link-cve5", "target-mixed", "obs-cve5"),
                    _link("link-cve5-only", "target-cve5-only", "obs-cve5"),
                ]
            )

        async with factory() as session:
            mixed = await _prediction_for_target(
                session,
                fact=_fact(),
                target_kind="claim",
                target_id="target-mixed",
                gold_support={},
                evaluated_source_ids=STRUCTURED_SNAPSHOT_SOURCE_IDS,
            )
            assert mixed is not None
            assert mixed.evidence_correct is True
            assert mixed.evidence_ref_ids == ("evidence:link-nvd",)

            external_only = await _prediction_for_target(
                session,
                fact=_fact(),
                target_kind="claim",
                target_id="target-cve5-only",
                gold_support={},
                evaluated_source_ids=STRUCTURED_SNAPSHOT_SOURCE_IDS,
            )
            assert external_only is None
    finally:
        await engine.dispose()
