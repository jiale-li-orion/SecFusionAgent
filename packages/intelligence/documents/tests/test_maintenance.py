from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.intelligence.documents.maintenance import DocumentQualityMaintenance
from packages.intelligence.documents.parsers import HTMLDocumentParser
from packages.intelligence.documents.service import ManagedDocumentService
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.document_models import DocumentChunkModel, DocumentRevisionModel
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.db import Base
from packages.shared.storage.models import OutboxEventModel
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

NOW = datetime(2026, 1, 1, tzinfo=UTC)
SOURCE = next(
    item
    for item in load_source_definitions(Path("config/sources"))
    if item.source_id == "trailofbits-research"
)
BODY = b"""<meta property="article:published_time" content="2025-05-14">
<article><h1>Original research title</h1><p>Detailed security evidence.</p></article>"""


@pytest.fixture
async def retained_document():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    store = MemoryArtifactStore()

    class HistoricalHTMLParser(HTMLDocumentParser):
        VERSION = "legacy"

    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, [SOURCE])
            session.add(
                AcquisitionRunModel(
                    run_id="retained-run",
                    source_id=SOURCE.source_id,
                    trigger="scheduled",
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
        envelope = IngestEnvelope.for_binary_payload(
            acquisition_run_id="retained-run",
            trigger=AcquisitionTrigger.SCHEDULED,
            source_id=SOURCE.source_id,
            external_object_id="retained-html",
            body=BODY,
            media_type="text/html",
            canonical_url="https://example.test/article",
            published_at=None,
            updated_at=None,
            external_revision="v1",
            request_metadata={"title": "Discovery card title"},
            observed_at=NOW,
        )
        async with factory() as session, session.begin():
            result = await ManagedDocumentService(
                EvidenceIngress(store),
                {"text/html": HistoricalHTMLParser()},
            ).ingest(session, SOURCE, envelope)
            revision = await session.get(DocumentRevisionModel, result.document_revision_id)
            assert revision is not None
            revision.metadata_json = {}
            chunk = await session.scalar(select(DocumentChunkModel))
            assert chunk is not None
            chunk.section = None
            chunk.text = "404 Not Found\nnginx"
        yield factory, store, result
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_quality_audit_reads_current_and_retained_material_without_writes(retained_document):
    factory, store, result = retained_document
    service = DocumentQualityMaintenance(store)
    async with factory() as session:
        before = await session.scalar(select(func.count()).select_from(OutboxEventModel))
        rows = await service.audit_documents(session, document_ids=[result.document_id], limit=1)
        assert len(rows) == 1
        row = rows[0]
        assert row.document_id == result.document_id
        assert row.stored_chunk_quality["usable"] is False
        assert row.retained_quality is not None
        assert row.retained_quality["usable"] is True
        assert row.publication["published_date"] == "2025-05-14"
        assert "Detailed security evidence" not in row.model_dump_json()
        assert await session.scalar(select(func.count()).select_from(OutboxEventModel)) == before
        assert await session.scalar(select(func.count()).select_from(DocumentRevisionModel)) == 1


@pytest.mark.asyncio
async def test_reparse_reuses_original_evidence_and_preserves_old_revision(retained_document):
    factory, store, original = retained_document
    service = DocumentQualityMaintenance(store)
    async with factory() as session, session.begin():
        result = await service.reparse_revision(
            session,
            document_revision_id=original.document_revision_id,
            source=SOURCE,
        )
        assert result.observation_id == original.observation_id
        assert result.document_revision_id != original.document_revision_id
        revision = await session.get(DocumentRevisionModel, result.document_revision_id)
        assert revision.title == "Original research title"
        assert revision.metadata_json["published_date"] == "2025-05-14"
        assert revision.metadata_json["content_quality"]["usable"] is True
        observation = await session.get(ObservationModel, original.observation_id)
        assert observation.request_metadata == {"title": "Discovery card title"}
        assert observation.published_at is None
        assert await session.scalar(select(func.count()).select_from(ObservationModel)) == 1
        assert await session.scalar(select(func.count()).select_from(DocumentRevisionModel)) == 2
        old_chunk = await session.scalar(
            select(DocumentChunkModel).where(
                DocumentChunkModel.document_revision_id == original.document_revision_id
            )
        )
        assert old_chunk.text == "404 Not Found\nnginx"
        replay = await service.reparse_revision(
            session,
            document_revision_id=original.document_revision_id,
            source=SOURCE,
        )
        assert replay.replay and replay.document_revision_id == result.document_revision_id


@pytest.mark.asyncio
async def test_reparse_refuses_corrupt_retained_artifact(retained_document):
    factory, store, original = retained_document
    store.objects[next(iter(store.objects))] = b"corrupted bytes"
    async with factory() as session:
        with pytest.raises(RuntimeError, match="content hash"):
            await DocumentQualityMaintenance(store).reparse_revision(
                session,
                document_revision_id=original.document_revision_id,
                source=SOURCE,
            )
        assert await session.scalar(select(func.count()).select_from(DocumentRevisionModel)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [0, 101])
async def test_audit_enforces_bounded_limit(retained_document, limit):
    factory, store, _ = retained_document
    async with factory() as session:
        with pytest.raises(ValueError, match=r"1.*100"):
            await DocumentQualityMaintenance(store).audit_documents(session, limit=limit)
