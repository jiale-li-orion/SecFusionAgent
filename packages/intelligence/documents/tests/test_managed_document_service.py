from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from packages.intelligence.documents.parsers import PlainTextDocumentParser
from packages.intelligence.documents.service import ManagedDocumentService
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.retrieval.contracts import EmbeddingBatch
from packages.intelligence.retrieval.indexing import DocumentIndexService
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.document_models import (
    DocumentChunkModel,
    DocumentModel,
    DocumentRevisionModel,
    InsightCandidateModel,
)
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import ExternalIdentifierModel, ObjectModel
from packages.intelligence.storage.models import ProcessingRunModel
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.db import Base
from packages.shared.storage.models import OutboxEventModel
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

NOW = datetime(2026, 9, 25, 13, 0, tzinfo=UTC)
SOURCE = next(
    item
    for item in load_source_definitions(Path("config/sources"))
    if item.source_id == "arxiv-ai-security"
)


class FakeEmbeddingProvider:
    async def embed(self, texts: list[str]) -> EmbeddingBatch:
        return EmbeddingBatch(
            model="fake-embedding",
            version="1",
            dimensions=3,
            vectors=[[float(index), 0.5, 1.0] for index, _ in enumerate(texts)],
        )


@pytest.mark.asyncio
async def test_managed_document_versions_are_durable_and_chunked() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    service = ManagedDocumentService(
        EvidenceIngress(MemoryArtifactStore(), now=lambda: NOW),
        {"text/plain": PlainTextDocumentParser()},
        now=lambda: NOW,
    )
    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, [SOURCE])
            for run_id in ("paper-run-v1", "paper-run-v2"):
                session.add(
                    AcquisitionRunModel(
                        run_id=run_id,
                        source_id=SOURCE.source_id,
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

        first = IngestEnvelope.for_binary_payload(
            acquisition_run_id="paper-run-v1",
            trigger=AcquisitionTrigger.SCHEDULED,
            source_id=SOURCE.source_id,
            external_object_id="2609.12345",
            body=("security evidence " * 500).encode(),
            media_type="text/plain",
            canonical_url="https://arxiv.org/abs/2609.12345v1",
            published_at=NOW,
            updated_at=NOW,
            external_revision="2609.12345v1",
            request_metadata={
                "title": "Agent Security Study",
                "authors": ["Alice Example"],
                "categories": ["cs.CR"],
            },
            observed_at=NOW,
        )
        async with factory() as session, session.begin():
            result1 = await service.ingest(session, SOURCE, first)
        assert result1.replay is False
        assert result1.chunk_count > 1

        async with factory() as session, session.begin():
            replay = await service.ingest(session, SOURCE, first)
        assert replay.replay is True
        assert replay.document_revision_id == result1.document_revision_id

        second = IngestEnvelope.for_binary_payload(
            acquisition_run_id="paper-run-v2",
            trigger=AcquisitionTrigger.SCHEDULED,
            source_id=SOURCE.source_id,
            external_object_id="2609.12345",
            body=("security evidence revised " * 300).encode(),
            media_type="text/plain",
            canonical_url="https://arxiv.org/abs/2609.12345v2",
            published_at=NOW,
            updated_at=NOW,
            external_revision="2609.12345v2",
            request_metadata={"title": "Agent Security Study v2"},
            observed_at=NOW,
        )
        async with factory() as session, session.begin():
            result2 = await service.ingest(session, SOURCE, second)
        assert result2.document_id == result1.document_id
        assert result2.document_revision_id != result1.document_revision_id

        async with factory() as session:
            assert await _count(session, DocumentModel) == 1
            assert await _count(session, DocumentRevisionModel) == 2
            assert await _count(session, InsightCandidateModel) == 2
            assert await _count(session, ObservationModel) == 2
            assert await _count(session, ProcessingRunModel) == 2
            assert await _count(session, OutboxEventModel) == 4
            assert await _count(session, DocumentChunkModel) == (
                result1.chunk_count + result2.chunk_count
            )
            obj = await session.get(ObjectModel, result1.object_id)
            assert obj is not None and obj.object_type == "ResearchWork"
            arxiv_id = await session.scalar(
                select(ExternalIdentifierModel).where(
                    ExternalIdentifierModel.object_id == result1.object_id,
                    ExternalIdentifierModel.namespace == "arxiv",
                )
            )
            assert arxiv_id is not None and arxiv_id.value == "2609.12345"
            insights = list(
                await session.scalars(
                    select(InsightCandidateModel).order_by(InsightCandidateModel.created_at)
                )
            )
            assert {item.change_type for item in insights} == {"new_document", "new_revision"}

        indexer = DocumentIndexService()
        async with factory() as session, session.begin():
            indexed = await indexer.build_lexical_index(
                session, document_revision_id=result2.document_revision_id
            )
            assert indexed.changed is True
            assert len(indexed.indexed_chunk_ids) == result2.chunk_count

        async with factory() as session:
            first_chunks = list(
                await session.scalars(
                    select(DocumentChunkModel).where(
                        DocumentChunkModel.document_revision_id == result1.document_revision_id
                    )
                )
            )
            second_chunks = list(
                await session.scalars(
                    select(DocumentChunkModel).where(
                        DocumentChunkModel.document_revision_id == result2.document_revision_id
                    )
                )
            )
            assert {item.index_status for item in first_chunks} == {"pending"}
            assert {item.index_status for item in second_chunks} == {"lexical_ready"}
            assert {item.metadata_json.get("lexical_index_version") for item in second_chunks} == {
                DocumentIndexService.LEXICAL_INDEX_VERSION
            }

        async with factory() as session, session.begin():
            dense = await indexer.build_dense_index(
                session,
                document_revision_id=result2.document_revision_id,
                provider=FakeEmbeddingProvider(),
            )
            assert dense.changed is True
            assert dense.embedding_model == "fake-embedding"
            assert dense.dimensions == 3

        async with factory() as session:
            dense_chunks = list(
                await session.scalars(
                    select(DocumentChunkModel).where(
                        DocumentChunkModel.document_revision_id == result2.document_revision_id
                    )
                )
            )
            assert {item.index_status for item in dense_chunks} == {"retrieval_ready"}
            assert {item.embedding_model for item in dense_chunks} == {"fake-embedding"}
            assert {item.embedding_version for item in dense_chunks} == {"1"}
            assert all(
                item.embedding is not None and len(item.embedding) == 3 for item in dense_chunks
            )

        async with factory() as session, session.begin():
            replay_index = await indexer.build_lexical_index(
                session, document_revision_id=result2.document_revision_id
            )
            assert replay_index.changed is False
            replay_dense = await indexer.build_dense_index(
                session,
                document_revision_id=result2.document_revision_id,
                provider=FakeEmbeddingProvider(),
            )
            assert replay_dense.changed is False
    finally:
        await engine.dispose()


async def _count(session: AsyncSession, model: type[object]) -> int:
    value = await session.scalar(select(func.count()).select_from(model))
    return int(value or 0)
