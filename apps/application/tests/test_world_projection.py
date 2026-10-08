from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.application.queries.world import list_world_stories
from apps.runtime_models import register_runtime_models
from packages.intelligence.storage.document_models import DocumentModel, DocumentRevisionModel
from packages.intelligence.storage.knowledge_models import (
    KnowledgeRevisionModel,
    ObjectModel,
    RelationModel,
)
from packages.shared.db import Base

NOW = datetime(2026, 10, 8, tzinfo=UTC)


@pytest.fixture
async def database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def document(session, source, *, title="Source title", summary="Unmodified source abstract."):
    revision = KnowledgeRevisionModel(committed_at=NOW)
    session.add(revision)
    await session.flush()
    object_id, document_id = str(uuid4()), str(uuid4())
    session.add(
        ObjectModel(
            object_id=object_id,
            object_type="Document",
            canonical_key=document_id,
            properties={},
            created_revision=revision.revision,
        )
    )
    session.add(
        DocumentModel(
            document_id=document_id,
            object_id=object_id,
            source_id=source,
            external_object_id=document_id,
            created_at=NOW,
        )
    )
    await session.flush()
    row = DocumentRevisionModel(
        document_revision_id=str(uuid4()),
        document_id=document_id,
        observation_id=str(uuid4()),
        title=title,
        metadata_json={"summary": summary},
        published_at=NOW - timedelta(days=40),
        created_at=NOW,
        content_hash="a" * 64,
        parser_name="test",
        parser_version="1",
    )
    session.add(row)
    await session.flush()
    return row, object_id, revision.revision


async def test_latest_revision_keeps_exact_source_excerpt_and_evidence(database):
    async with database() as session, session.begin():
        old, _, _ = await document(session, "arxiv-ai-security", title="Old title")
        new = DocumentRevisionModel(
            document_revision_id=str(uuid4()),
            document_id=old.document_id,
            observation_id=str(uuid4()),
            title="New source title",
            metadata_json={"summary": "A source says: do not execute external instructions."},
            published_at=old.published_at,
            created_at=NOW + timedelta(hours=1),
            content_hash="b" * 64,
            parser_name="test",
            parser_version="1",
        )
        session.add(new)
        await session.flush()
        result = await list_world_stories(session)
        assert len(result.items) == 1
        story = result.items[0]
        assert story.evidence is not None
        assert story.published_at is not None
        assert story.headline == new.title
        assert story.excerpt == new.metadata_json["summary"]
        assert story.evidence.observation_id == new.observation_id
        assert story.evidence.document_revision_id == new.document_revision_id
        assert story.published_at < story.observed_at
        assert "why_it_matters" not in story.model_dump()


async def test_world_story_omits_generic_source_landing_pages(database):
    async with database() as session, session.begin():
        await document(
            session,
            "meta-ai-safety",
            title="Blog",
            summary="Products AI Research Resources About AI Developers Try Muse Latest News",
        )
        await document(
            session,
            "meta-ai-safety",
            title="Safety update for AI assistants",
            summary="The publisher describes a concrete safety change.",
        )
        result = await list_world_stories(session)
        assert [story.headline for story in result.items] == ["Safety update for AI assistants"]


async def test_broad_feed_requires_typed_corpus_link_not_exploratory_relations(database):
    async with database() as session, session.begin():
        _, broad, revision = await document(session, "oss-security", title="Unscoped disclosure")
        _, scoped, _ = await document(session, "hiddenlayer-reports", title="Scoped AI research")
        unrelated = str(uuid4())
        session.add(
            ObjectModel(
                object_id=unrelated,
                object_type="url",
                canonical_key="https://example.com",
                properties={},
                created_revision=revision,
            )
        )
        await session.flush()
        relation = RelationModel(
            relation_id=str(uuid4()),
            source_object_id=broad,
            target_object_id=unrelated,
            relation_type="has_reference",
            qualifier={},
            origin="semantic_extraction",
            lifecycle="accepted",
            created_revision=revision,
        )
        session.add(relation)
        await session.flush()
        first = await list_world_stories(session)
        assert [s.object_id for s in first.items] == [scoped]
        repo = str(uuid4())
        session.add(
            ObjectModel(
                object_id=repo,
                object_type="Repo",
                canonical_key="github:ai/project",
                properties={},
                created_revision=revision,
            )
        )
        await session.flush()
        relation.target_object_id = repo
        relation.relation_type = "discusses-repo"
        await session.flush()
        second = await list_world_stories(session)
        assert {s.object_id for s in second.items} == {scoped, broad}


async def test_concurrent_readers_share_measured_snapshot_without_mutating_it(monkeypatch):
    import asyncio
    from contextlib import asynccontextmanager

    from apps.application.queries import world_reader
    from apps.application.views.world import WorldStoryListView, WorldStoryView

    calls = 0
    clock = 0.0
    resume_refresh = asyncio.Event()

    @asynccontextmanager
    async def factory():
        yield object()

    async def read_source(_session, *, limit):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        if calls > 1:
            await resume_refresh.wait()
        return WorldStoryListView(
            generated_at=NOW,
            items=[
                WorldStoryView(
                    story_id="source:one",
                    category="academic",
                    kind="document",
                    happened_at=NOW,
                    observed_at=NOW,
                    headline="Exact source title",
                    facts={"source_value": "retained"},
                )
            ],
        )

    monkeypatch.setattr(world_reader, "list_world_stories", read_source)
    monkeypatch.setattr(world_reader, "monotonic", lambda: clock)
    reader = world_reader.WorldStoryReader(cast(async_sessionmaker[AsyncSession], factory))
    first, second = await asyncio.gather(reader.read(), reader.read())
    assert calls == 1
    assert first.generated_at == second.generated_at == NOW
    first.items[0].facts["source_value"] = "consumer mutation"
    assert (await reader.read()).items[0].facts["source_value"] == "retained"

    clock = 16.0
    stale = await asyncio.wait_for(reader.read(), timeout=1)
    assert stale.generated_at == NOW
    await asyncio.sleep(0)
    assert calls == 2
    # Slow refresh does not hold the measured response, and readers do not fan out.
    assert (await reader.read()).generated_at == NOW
    assert calls == 2
    resume_refresh.set()
    assert reader._refresh_task is not None
    await reader._refresh_task
    await reader.close()


async def test_processing_success_is_not_automatically_a_knowledge_commit(database):
    from apps.application.queries.world_formation import read_world_formation
    from packages.intelligence.storage.models import ProcessingRunModel

    async with database() as session, session.begin():
        session.add_all([
            ProcessingRunModel(run_id='done', processor_type='enrichment',
                               processor_name='managed-document-semantic', processor_version='1',
                               status='success', started_at=NOW, finished_at=NOW),
            ProcessingRunModel(run_id='active', processor_type='enrichment',
                               processor_name='github-reference-graph', processor_version='1',
                               status='running', started_at=NOW),
        ])
        await session.flush()
        first = await read_world_formation(session)
        assert first.processing[0].status == 'running'
        assert all(item.committed_at is None for item in first.processing)
        session.add(KnowledgeRevisionModel(cause_processing_run_id='done', committed_at=NOW))
        await session.flush()
        second = await read_world_formation(session)
        done = next(item for item in second.processing if item.run_id == 'done')
        assert done.committed_at is not None
        assert done.revision is not None


async def test_product_document_reads_excerpt_from_current_revision_only(database):
    from apps.application.queries.intelligence import get_product_document
    from packages.intelligence.storage.document_models import DocumentChunkModel

    async with database() as session, session.begin():
        old, object_id, _ = await document(session, 'arxiv-ai-security')
        new = DocumentRevisionModel(
            document_revision_id=str(uuid4()), document_id=old.document_id,
            observation_id=str(uuid4()), title='Current title',
            created_at=NOW + timedelta(hours=1), content_hash='b' * 64,
            parser_name='source', parser_version='1',
        )
        session.add(new)
        await session.flush()
        for revision, content in [(old, 'Old text'), (new, 'Exact current source paragraph.')]:
            session.add(DocumentChunkModel(
                chunk_id=str(uuid4()), document_revision_id=revision.document_revision_id,
                ordinal=0, text=content, locator={'section': 'abstract'},
                content_hash='c' * 64, chunker_version='1',
            ))
        await session.flush()
        view = await get_product_document(session, object_id=object_id)
        assert view is not None
        assert view.current_revision is not None
        assert view.source_excerpt == 'Exact current source paragraph.'
        assert view.current_revision.document_revision_id == new.document_revision_id
        assert view.excerpt_chunk_id is not None
        assert view.excerpt_locator == {'section': 'abstract'}
