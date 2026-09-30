from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.intelligence.retrieval.operators import LexicalRetrievalOperator
from packages.intelligence.storage.document_models import (
    DocumentChunkModel,
    DocumentModel,
    DocumentRevisionModel,
)
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import ObjectModel
from packages.shared.db import Base
from packages.sources.storage.models import SourceModel


@pytest.mark.asyncio
async def test_chunk_ref_replay_preserves_requested_order_and_exact_revision() -> None:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime(2026, 9, 30, tzinfo=UTC)
    try:
        async with factory() as session, session.begin():
            session.add(
                SourceModel(
                    source_id="retrieval-replay-source",
                    adapter_type="fixture",
                    source_class="vendor",
                    authority_scope=["document"],
                    source_role="primary",
                    source_family="retrieval-replay",
                    access_mode="fixture",
                    update_semantics="immutable",
                    discovery_method={},
                    time_semantics={},
                    identity_semantics={},
                    rate_limit_policy={},
                    access_rights={},
                    retention_mode="durable_managed",
                    schedule_policy={},
                    schema_version="1",
                    definition_hash="retrieval-replay-source-hash",
                    updated_at=now,
                )
            )
            await session.flush()
            session.add(
                ObservationModel(
                    observation_id="retrieval-replay-observation",
                    source_id="retrieval-replay-source",
                    acquisition_run_id=None,
                    acquisition_trigger="replay",
                    external_object_id="doc-1",
                    external_revision="source-r1",
                    canonical_url="https://example.test/doc-1",
                    published_at=now,
                    updated_at=now,
                    observed_at=now,
                    content_hash="a" * 64,
                    request_metadata={},
                    request_metadata_captured=False,
                    idempotency_key="b" * 64,
                    created_at=now,
                )
            )
            session.add(
                ObjectModel(
                    object_id="retrieval-replay-object",
                    object_type="Document",
                    canonical_key="document:fixture:replay",
                    properties={"title": "Replay doc"},
                    created_revision=1,
                )
            )
            await session.flush()
            session.add(
                DocumentModel(
                    document_id="retrieval-replay-document",
                    object_id="retrieval-replay-object",
                    source_id="retrieval-replay-source",
                    external_object_id="doc-1",
                    canonical_url="https://example.test/doc-1",
                    created_at=now,
                )
            )
            await session.flush()
            session.add(
                DocumentRevisionModel(
                    document_revision_id="retrieval-replay-r1",
                    document_id="retrieval-replay-document",
                    observation_id="retrieval-replay-observation",
                    external_revision="source-r1",
                    title="Replay doc",
                    metadata_json={},
                    published_at=now,
                    updated_at=now,
                    content_hash="c" * 64,
                    parser_name="fixture",
                    parser_version="1",
                    created_at=now,
                )
            )
            await session.flush()
            session.add_all(
                [
                    DocumentChunkModel(
                        chunk_id="retrieval-replay-chunk-1",
                        document_revision_id="retrieval-replay-r1",
                        ordinal=0,
                        section="one",
                        page_number=None,
                        text="first chunk",
                        metadata_json={},
                        locator={"ordinal": 0},
                        content_hash="d" * 64,
                        chunker_version="1",
                        index_status="indexed",
                        embedding=None,
                        embedding_model=None,
                        embedding_version=None,
                    ),
                    DocumentChunkModel(
                        chunk_id="retrieval-replay-chunk-2",
                        document_revision_id="retrieval-replay-r1",
                        ordinal=1,
                        section="two",
                        page_number=None,
                        text="second chunk",
                        metadata_json={},
                        locator={"ordinal": 1},
                        content_hash="e" * 64,
                        chunker_version="1",
                        index_status="indexed",
                        embedding=None,
                        embedding_model=None,
                        embedding_version=None,
                    ),
                ]
            )

        async with factory() as session:
            replayed = await LexicalRetrievalOperator().by_chunk_refs(
                session,
                refs=[
                    "document-chunk:retrieval-replay-chunk-2@retrieval-replay-r1",
                    "document-chunk:retrieval-replay-chunk-1@retrieval-replay-r1",
                ],
            )
            assert [item.document_chunk_id for item in replayed] == [
                "retrieval-replay-chunk-2",
                "retrieval-replay-chunk-1",
            ]
            assert [item.payload["text"] for item in replayed] == [
                "second chunk",
                "first chunk",
            ]
            assert all(item.score_channels == {"reused": 1.0} for item in replayed)

            stale = await LexicalRetrievalOperator().by_chunk_refs(
                session,
                refs=[
                    "document-chunk:retrieval-replay-chunk-1@another-revision"
                ],
            )
            assert stale == []
    finally:
        await engine.dispose()
