from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete, event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.application.queries.library import list_material_library
from apps.application.queries.library_subjects import material_subjects
from apps.application.tests.test_world_projection import document
from apps.runtime_models import register_runtime_models
from packages.intelligence.storage.document_models import DocumentChunkModel, DocumentRevisionModel
from packages.intelligence.storage.evidence_models import EvidenceArtifactModel, ObservationModel
from packages.shared.db import Base
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions
from packages.sources.storage.models import SourceModel

NOW = datetime(2026, 10, 15, tzinfo=UTC)


@pytest.fixture
async def library_db():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        await sync_source_definitions(session, load_source_definitions(Path("config/sources")))
    yield factory, engine
    await engine.dispose()


async def material(
    session,
    *,
    title="Prompt injection containment",
    source="arxiv-ai-security",
    summary="Sandbox tool permissions protect agent tools.",
    created=NOW,
):
    revision, _, _ = await document(session, source, title=title, summary=summary)
    revision.created_at = created
    await observation(session, revision, source, created)
    return revision


async def observation(session, revision, source, created):
    session.add(
        ObservationModel(
            observation_id=revision.observation_id,
            source_id=source,
            external_object_id=revision.document_id,
            observed_at=created,
            content_hash="a" * 64,
            idempotency_key=str(uuid4()),
            created_at=created,
        )
    )
    session.add(
        EvidenceArtifactModel(
            artifact_id=str(uuid4()),
            observation_id=revision.observation_id,
            media_type="text/plain",
            storage_uri="fixture://public",
            content_hash="e" * 64,
            access_rights={"classification": "public"},
            created_at=created,
        )
    )
    await session.flush()


async def test_library_pages_all_material_with_stable_snapshot_and_one_read(library_db):
    factory, engine = library_db
    async with factory() as session, session.begin():
        for index in range(55):
            await material(
                session,
                title=f"Prompt injection research {index}",
                created=NOW - timedelta(minutes=index),
            )
    statements = []

    def count_statement(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", count_statement)
    try:
        async with factory() as session:
            first = await list_material_library(session, limit=48, as_of=NOW)
        assert len(statements) == 1
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", count_statement)
    assert first.total == first.corpus_total == 55
    assert len(first.items) == 48 and first.next_offset == 48
    async with factory() as session, session.begin():
        await material(
            session, title="New ingestion after snapshot", created=NOW + timedelta(hours=1)
        )
    async with factory() as session:
        second = await list_material_library(session, limit=48, offset=48, as_of=first.as_of)
    assert second.total == 55 and len(second.items) == 7 and second.next_offset is None
    assert not {item.story_id for item in first.items} & {item.story_id for item in second.items}


async def test_library_exact_total_excludes_private_rejected_and_legacy_error_material(library_db):
    factory, _ = library_db
    async with factory() as session, session.begin():
        good = await material(session)
        assert good is not None
        rejected = await material(session)
        rejected.metadata_json = {"summary": "Looks valid", "content_quality": {"usable": False}}
        private = await material(session)
        session.add(
            EvidenceArtifactModel(
                artifact_id=str(uuid4()),
                observation_id=private.observation_id,
                media_type="text/plain",
                storage_uri="fixture://private",
                content_hash="b" * 64,
                access_rights={"classification": "private"},
                created_at=NOW,
            )
        )
        missing = await material(session)
        await session.execute(
            delete(EvidenceArtifactModel).where(
                EvidenceArtifactModel.observation_id == missing.observation_id
            )
        )
        unknown = await material(session)
        session.add(
            EvidenceArtifactModel(
                artifact_id=str(uuid4()),
                observation_id=unknown.observation_id,
                media_type="text/plain",
                storage_uri="fixture://unknown",
                content_hash="f" * 64,
                access_rights={},
                created_at=NOW,
            )
        )
        legacy = await material(session, summary="Looks valid")
        session.add(
            DocumentChunkModel(
                chunk_id=str(uuid4()),
                document_revision_id=legacy.document_revision_id,
                ordinal=0,
                section="The server is temporarily unavailable",
                text="Please try again later.",
                metadata_json={},
                locator={},
                content_hash="c" * 64,
                chunker_version="1",
            )
        )
        await material(session, title="Blog")
        await material(session, source="oss-security", title="Unlinked broad feed disclosure")
        await session.flush()
        result = await list_material_library(session, as_of=NOW)
        assert result.total == result.corpus_total == 1
        assert result.items[0].evidence is not None
        assert result.items[0].evidence.document_revision_id == good.document_revision_id
        source = await session.get(SourceModel, "arxiv-ai-security")
        source.access_rights = {"classification": "private"}
        await session.flush()
        assert (await list_material_library(session, as_of=NOW)).total == 0


async def test_library_latest_revision_filters_facets_and_exact_evidence(library_db):
    factory, _ = library_db
    async with factory() as session, session.begin():
        old = await material(
            session, title="Old prompt injection", created=NOW - timedelta(hours=1)
        )
        current = DocumentRevisionModel(
            document_revision_id=str(uuid4()),
            document_id=old.document_id,
            observation_id=str(uuid4()),
            title="Credential authentication in model hubs",
            metadata_json={
                "summary": "Supply chain credential authorization",
                "published_date": "2026-10-01",
            },
            published_at=None,
            created_at=NOW,
            content_hash="d" * 64,
            parser_name="test",
            parser_version="new",
        )
        assert current is not None
        session.add(current)
        await observation(session, current, "arxiv-ai-security", NOW)
        await material(
            session,
            title="Chinese prompt",
            summary="提示注入和沙箱工具权限",
            source="hiddenlayer-reports",
        )
        result = await list_material_library(
            session, subject="identity-access", category="academic", q="credential", as_of=NOW
        )
        assert result.total == 1 and result.corpus_total == 2
        assert result.items[0].headline == current.title
        assert result.items[0].evidence is not None
        assert result.items[0].evidence.observation_id == current.observation_id
        assert result.items[0].published_date == "2026-10-01"
        assert result.items[0].time_basis == "published"
        assert result.items[0].observed_at.date() == NOW.date()
        assert {facet.key: facet.count for facet in result.subjects}["prompt-injection"] == 1
        assert (
            await list_material_library(session, source="hiddenlayer-reports", as_of=NOW)
        ).total == 1
        assert not (await list_material_library(session, q="nonexistent", as_of=NOW)).items


def test_granular_subjects_are_multilabel_and_do_not_match_substrings():
    assert {"prompt-injection", "runtime-containment"} <= set(
        material_subjects("提示注入", "沙箱隔离与工具调用")
    )
    assert {"identity-access", "supply-chain"} <= set(
        material_subjects("Credential protection", "model hub supply-chain")
    )
    assert "rag-retrieval" not in material_subjects("Fragmented storage", "A software migration")


async def test_new_security_sources_are_individually_browsable(library_db):
    factory, _ = library_db
    sources = [
        "huggingface-security",
        "crowdstrike-research",
        "metr-research",
        "transluce-research",
        "rea-project",
    ]
    async with factory() as session, session.begin():
        for source in sources:
            await material(session, source=source, title=f"Agent security research from {source}")
        result = await list_material_library(session, as_of=NOW)
        assert result.total == 5
        assert {item.source_id for item in result.items} == set(sources)
        assert all(item.source_name != item.source_id for item in result.items)
        for source in sources:
            filtered = await list_material_library(session, source=source, as_of=NOW)
            assert filtered.total == 1 and filtered.items[0].source_id == source
