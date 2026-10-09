from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.dependencies import database_session
from apps.api.main import create_app
from apps.runtime_models import register_runtime_models
from packages.intelligence.storage.document_models import (
    DocumentChunkModel,
    DocumentModel,
    DocumentRevisionModel,
)
from packages.intelligence.storage.evidence_models import EvidenceArtifactModel, ObservationModel
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    EvidenceLinkModel,
    KnowledgeRevisionModel,
    ObjectModel,
)
from packages.shared.db import Base
from packages.sources.storage.models import SourceModel

NOW = datetime(2026, 10, 4, 8, 0, tzinfo=UTC)


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        source = SourceModel(
            source_id="vendor-primary",
            adapter_type="test",
            source_class="vendor_advisory",
            authority_scope=["fix-boundary"],
            source_role="primary",
            source_family="vendor",
            upstream_source=None,
            access_mode="public",
            update_semantics="revisioned",
            discovery_method={},
            time_semantics={},
            identity_semantics={},
            auth_ref=None,
            rate_limit_policy={},
            access_rights={"classification": "public"},
            retention_mode="durable_managed",
            schedule_policy={},
            schema_version="1",
            definition_hash="def-hash",
            managed_by="test",
            enabled=True,
            updated_at=NOW,
        )
        session.add(source)
        revision = KnowledgeRevisionModel(committed_at=NOW)
        session.add(revision)
        await session.flush()
        session.add(
            ObjectModel(
                object_id="object-1",
                object_type="Vulnerability",
                canonical_key="cve:CVE-2026-42424",
                properties={"display_name": "CVE-2026-42424"},
                created_revision=revision.revision,
            )
        )
        claim = ClaimModel(
            claim_id="claim-1",
            subject_id="object-1",
            predicate="fixed_version",
            value="2.4.1",
            qualifier={},
            origin="source_asserted",
            lifecycle="accepted",
            processing_run_id=None,
            created_revision=revision.revision,
            superseded_revision=None,
        )
        session.add(claim)
        observation = ObservationModel(
            observation_id="observation-1",
            source_id=source.source_id,
            acquisition_run_id=None,
            acquisition_trigger="scheduled",
            external_object_id="ADV-42424",
            external_revision="rev-7",
            canonical_url="https://vendor.example/advisories/42424",
            published_at=NOW,
            updated_at=NOW,
            observed_at=NOW,
            content_hash="a" * 64,
            request_metadata={"secret": "must-not-leak"},
            request_metadata_captured=True,
            idempotency_key="b" * 64,
            created_at=NOW,
        )
        session.add(observation)
        artifact = EvidenceArtifactModel(
            artifact_id="artifact-1",
            observation_id=observation.observation_id,
            media_type="application/json",
            storage_uri="file:///private/internal/path.json",
            content_hash=observation.content_hash,
            access_rights={},
            trust_class="external_untrusted",
            created_at=NOW,
        )
        session.add(artifact)
        session.add(
            EvidenceLinkModel(
                evidence_link_id="evidence-link-1",
                target_kind="claim",
                target_id=claim.claim_id,
                observation_id=observation.observation_id,
                artifact_id=artifact.artifact_id,
                locator={"kind": "jsonpath", "path": "$.fixed_version"},
                locator_hash="c" * 64,
            )
        )
        session.add(
            DocumentModel(
                document_id="document-1",
                object_id="object-1",
                source_id=source.source_id,
                external_object_id=observation.external_object_id,
                canonical_url=observation.canonical_url,
                created_at=NOW,
            )
        )
        await session.flush()
        session.add(
            DocumentRevisionModel(
                document_revision_id="document-revision-1",
                document_id="document-1",
                observation_id=observation.observation_id,
                external_revision="rev-7",
                title="Vendor advisory",
                metadata_json={},
                published_at=NOW,
                updated_at=NOW,
                content_hash=observation.content_hash,
                parser_name="selectolax-html",
                parser_version="3",
                created_at=NOW,
            )
        )
        await session.flush()
        session.add(
            DocumentChunkModel(
                chunk_id="document-chunk-1",
                document_revision_id="document-revision-1",
                ordinal=0,
                section="Remediation",
                page_number=None,
                text="The vendor confirmed fixed release 2.4.1.",
                metadata_json={},
                locator={"section": "Remediation", "char_start": 0, "char_end": 41},
                content_hash="d" * 64,
                chunker_version="char-window-v1",
                index_status="lexical_ready",
            )
        )
    return engine, factory


@pytest.mark.asyncio
async def test_product_evidence_resolves_safe_traceable_view() -> None:
    engine, factory = await _database()
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/evidence/evidence:evidence-link-1")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["evidence_ref"] == "evidence:evidence-link-1"
        assert payload["source"]["source_role"] == "primary"
        assert payload["observation"]["external_revision"] == "rev-7"
        assert payload["target"]["label"] == "fixed_version"
        assert payload["target"]["detail"]["value"] == "2.4.1"
        assert payload["locator"] == {"kind": "jsonpath", "path": "$.fixed_version"}
        assert payload["artifact"]["trust_class"] == "external_untrusted"
        assert payload["document_passages"] == [
            {
                "chunk_ref": "document-chunk:document-chunk-1@document-revision-1",
                "section": "Remediation",
                "text": "The vendor confirmed fixed release 2.4.1.",
            }
        ]
        serialized = response.text
        assert "storage_uri" not in serialized
        assert "request_metadata" not in serialized
        assert "private/internal" not in serialized
        assert "secret" not in serialized
        async with factory() as session, session.begin():
            source = await session.get(SourceModel, "vendor-primary")
            assert source is not None
            source.access_rights = {"classification": "restricted"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            restricted = await client.get("/api/v1/evidence/evidence:evidence-link-1")
        assert restricted.status_code == 200
        assert restricted.json()["document_passages"] == []
    finally:
        await engine.dispose()
