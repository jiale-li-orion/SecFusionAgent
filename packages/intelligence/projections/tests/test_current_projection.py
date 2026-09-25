from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.intelligence.projections.service import (
    CurrentProjectionService,
    get_current_projection,
)
from packages.intelligence.storage.evidence_models import ObservationModel  # noqa: F401
from packages.intelligence.storage.incident_models import (
    IncidentRevisionModel,
    IncidentSourceLinkModel,
    IncidentTimelineEventModel,
    SecurityIncidentModel,
)
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    ExternalIdentifierModel,
    KnowledgeRevisionModel,
    ObjectModel,
    RelationModel,
)
from packages.intelligence.storage.models import ProcessingRunModel  # noqa: F401
from packages.monitoring.storage.models import AcquisitionRunModel, SourceStateModel  # noqa: F401
from packages.shared.db import Base
from packages.shared.storage.models import OutboxEventModel  # noqa: F401
from packages.sources.storage.models import SourceModel  # noqa: F401

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_vulnerability_projection_preserves_conflict_and_relations() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session, session.begin():
            revision1 = KnowledgeRevisionModel(committed_at=NOW)
            revision2 = KnowledgeRevisionModel(committed_at=NOW)
            session.add_all([revision1, revision2])
            await session.flush()
            vulnerability = ObjectModel(
                object_id="vuln-1",
                object_type="Vulnerability",
                canonical_key="cve:CVE-2026-42424",
                properties={"display_name": "CVE-2026-42424"},
                created_revision=revision1.revision,
            )
            package = ObjectModel(
                object_id="pkg-1",
                object_type="Package",
                canonical_key="package:pypi:vllm",
                properties={"name": "vllm", "ecosystem": "PyPI"},
                created_revision=revision1.revision,
            )
            session.add_all([vulnerability, package])
            session.add(
                ExternalIdentifierModel(
                    external_identifier_id="eid-1",
                    namespace="cve",
                    value="CVE-2026-42424",
                    object_id="vuln-1",
                )
            )
            session.add_all(
                [
                    ClaimModel(
                        claim_id="claim-1",
                        subject_id="vuln-1",
                        predicate="cvss_score",
                        value=9.8,
                        qualifier={"source_id": "nvd"},
                        origin="source_asserted",
                        lifecycle="accepted",
                        created_revision=revision1.revision,
                    ),
                    ClaimModel(
                        claim_id="claim-2",
                        subject_id="vuln-1",
                        predicate="cvss_score",
                        value=9.1,
                        qualifier={"source_id": "vendor"},
                        origin="source_asserted",
                        lifecycle="accepted",
                        created_revision=revision2.revision,
                    ),
                ]
            )
            session.add(
                RelationModel(
                    relation_id="rel-1",
                    source_object_id="vuln-1",
                    relation_type="affects-package",
                    target_object_id="pkg-1",
                    qualifier={"vulnerable_version_range": "<0.11.1"},
                    origin="source_asserted",
                    lifecycle="accepted",
                    created_revision=revision2.revision,
                )
            )

        service = CurrentProjectionService(now=lambda: NOW)
        async with factory() as session, session.begin():
            result = await service.rebuild_knowledge_object(
                session,
                object_id="vuln-1",
                upstream_revision=2,
            )
        assert result is not None and result.changed is True

        async with factory() as session:
            projection = await get_current_projection(
                session,
                projection_type="current_vulnerability_view",
                projection_key="CVE-2026-42424",
            )
            assert projection is not None
            fields = projection.data["fields"]
            assert isinstance(fields, dict)
            cvss = fields["cvss_score"]
            assert isinstance(cvss, dict)
            assert cvss["value"] == 9.1
            assert cvss["conflict"] is True
            assert projection.data["conflict_predicates"] == ["cvss_score"]
            relations = projection.data["relations"]
            assert isinstance(relations, list)
            assert relations[0]["target_key"] == "package:pypi:vllm"

        async with factory() as session, session.begin():
            replay = await service.rebuild_knowledge_object(
                session,
                object_id="vuln-1",
                upstream_revision=2,
            )
        assert replay is not None and replay.changed is False
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_incident_projection_is_timeline_oriented() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session, session.begin():
            revision = IncidentRevisionModel(committed_at=NOW)
            session.add(revision)
            await session.flush()
            session.add(
                SecurityIncidentModel(
                    incident_id="incident-1",
                    candidate_id="candidate-1",
                    incident_type="exchange-compromise",
                    lifecycle="active",
                    promotion_reason="independent_corroboration",
                    current_summary="Funds are moving on-chain",
                    watch_state={"watch_priority": 80},
                    created_revision=revision.revision,
                    current_revision=revision.revision,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            session.add(
                IncidentTimelineEventModel(
                    event_id="event-1",
                    incident_id="incident-1",
                    signal_id="signal-1",
                    event_time=NOW,
                    observed_at=NOW,
                    event_type="fund-movement",
                    summary="Attacker moved funds",
                    source_role="forensic",
                    claim_refs=[],
                    evidence_refs=["obs-1"],
                    created_revision=revision.revision,
                )
            )
            session.add(
                IncidentSourceLinkModel(
                    source_link_id="link-1",
                    incident_id="incident-1",
                    observation_id="obs-1",
                    source_id="forensic-a",
                    source_family="forensic-a",
                    upstream_source=None,
                    independence_key="forensic-a",
                    source_role="forensic",
                    created_revision=revision.revision,
                )
            )

        service = CurrentProjectionService(now=lambda: NOW)
        async with factory() as session, session.begin():
            result = await service.rebuild_incident(
                session,
                incident_id="incident-1",
                upstream_revision=1,
            )
        assert result is not None and result.changed is True
        async with factory() as session:
            projection = await get_current_projection(
                session,
                projection_type="current_incident_view",
                projection_key="incident-1",
            )
            assert projection is not None
            assert projection.data["current_summary"] == "Funds are moving on-chain"
            assert projection.data["source_diversity"] == ["forensic-a"]
            timeline = projection.data["timeline"]
            assert isinstance(timeline, list)
            assert timeline[0]["event_type"] == "fund-movement"
    finally:
        await engine.dispose()
