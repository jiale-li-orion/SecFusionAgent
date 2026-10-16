from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.application.public_briefings import load_briefing_packet, publish_briefing, visible_brief
from apps.application.tests.test_world_projection import document
from apps.runtime_models import register_runtime_models
from packages.intelligence.storage.document_models import (
    DocumentChunkModel,
    DocumentModel,
    DocumentRevisionModel,
)
from packages.intelligence.storage.evidence_models import EvidenceArtifactModel
from packages.reasoning.briefing import BriefingGenerator
from packages.reasoning.tests.test_briefing import Provider
from packages.shared.db import Base
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions
from packages.sources.storage.models import SourceModel

NOW = datetime(2026, 10, 15, tzinfo=UTC)


@pytest.fixture
async def briefing_db():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        source = next(
            s
            for s in load_source_definitions(Path("config/sources"))
            if s.source_id == "arxiv-ai-security"
        )
        await sync_source_definitions(session, [source])
        revision, _, _ = await document(session, source.source_id, title="Agent testing")
        doc = await session.get(DocumentModel, revision.document_id)
        assert doc is not None
        doc.canonical_url = "https://example.org/report"
        session.add(
            DocumentChunkModel(
                chunk_id="c1",
                document_revision_id=revision.document_revision_id,
                ordinal=0,
                text="The vendor reports 12 tests in a simulated environment.",
                metadata_json={},
                locator={},
                content_hash="c" * 64,
                chunker_version="1",
            )
        )
        session.add(
            EvidenceArtifactModel(
                artifact_id=str(uuid4()),
                observation_id=revision.observation_id,
                media_type="text/html",
                storage_uri="file:///fixture.html",
                content_hash="e" * 64,
                access_rights={"classification": "public"},
                created_at=NOW,
            )
        )
        doc_id, rev_id = revision.document_id, revision.document_revision_id
    yield factory, doc_id, rev_id
    await engine.dispose()


class BoundProvider(Provider):
    async def generate_structured(self, request, response_model):
        result = await super().generate_structured(request, response_model)
        if "action" in response_model.model_fields:
            ref = (
                request.data["citation_sources"][0]["evidence_ref"]
                if "citation_sources" in request.data
                else request.data["source_packet"]["materials"][0]["passages"][0]["evidence_ref"]
            )
            result.action.conclusions[0].evidence_refs = [ref]
            result.action.report_paragraphs[0].evidence_refs = [ref]
            result.action.report_summary.evidence_refs = [ref]
        return result


async def test_publication_is_idempotent_and_disappears_when_source_becomes_private(briefing_db):
    factory, doc_id, _ = briefing_db
    provider = BoundProvider()
    first = await publish_briefing(
        factory, BriefingGenerator(provider), topic="Agent safety", document_ids=[doc_id], now=NOW
    )
    second = await publish_briefing(
        factory, BriefingGenerator(provider), topic="Agent safety", document_ids=[doc_id], now=NOW
    )
    assert first.brief_id == second.brief_id
    assert len(provider.requests) == 2
    async with factory() as session, session.begin():
        assert await visible_brief(session, first.brief_id) is not None
        source = await session.get(SourceModel, "arxiv-ai-security")
        source.access_rights = {"classification": "private"}
    async with factory() as session:
        assert await visible_brief(session, first.brief_id) is None


async def test_publication_rejects_error_material_before_model_call(briefing_db):
    factory, doc_id, rev_id = briefing_db
    async with factory() as session, session.begin():
        rev = await session.get(DocumentRevisionModel, rev_id)
        rev.metadata_json = {"content_quality": {"usable": False, "status": "rejected"}}
    provider = BoundProvider()
    with pytest.raises(ValueError, match="material quality"):
        await publish_briefing(
            factory,
            BriefingGenerator(provider),
            topic="Agent safety",
            document_ids=[doc_id],
            now=NOW,
        )
    assert not provider.requests


async def test_new_revision_invalidates_old_public_report(briefing_db):
    factory, doc_id, rev_id = briefing_db
    brief = await publish_briefing(
        factory,
        BriefingGenerator(BoundProvider()),
        topic="Agent safety",
        document_ids=[doc_id],
        now=NOW,
    )
    async with factory() as session, session.begin():
        old = await session.get(DocumentRevisionModel, rev_id)
        session.add(
            DocumentRevisionModel(
                document_revision_id=str(uuid4()),
                document_id=doc_id,
                observation_id=str(uuid4()),
                title="Corrected report",
                metadata_json={},
                created_at=NOW,
                published_at=NOW,
                content_hash="d" * 64,
                parser_name=old.parser_name,
                parser_version="new",
            )
        )
    async with factory() as session:
        assert await visible_brief(session, brief.brief_id) is None


async def test_failed_editorial_review_is_retained_but_not_public(briefing_db):
    factory, doc_id, _ = briefing_db
    brief = await publish_briefing(
        factory,
        BriefingGenerator(BoundProvider(supported=False)),
        topic="Agent safety",
        document_ids=[doc_id],
        now=NOW,
    )
    assert brief.status == "review_required"
    async with factory() as session:
        assert await visible_brief(session, brief.brief_id) is None


async def test_private_source_cannot_enter_packet(briefing_db):
    factory, doc_id, _ = briefing_db
    async with factory() as session, session.begin():
        source = await session.get(SourceModel, "arxiv-ai-security")
        source.access_rights = {"classification": "private"}
    async with factory() as session:
        with pytest.raises(ValueError, match="public"):
            await load_briefing_packet(session, topic="Agent safety", document_ids=[doc_id])


async def test_legacy_error_heading_is_rejected_before_generation(briefing_db):
    factory, doc_id, _ = briefing_db
    async with factory() as session, session.begin():
        chunk = await session.get(DocumentChunkModel, "c1")
        chunk.section = "The server is temporarily unavailable"
        chunk.text = "Please try again later."
    provider = BoundProvider()
    with pytest.raises(ValueError, match="material quality"):
        await publish_briefing(
            factory, BriefingGenerator(provider), topic="Safety", document_ids=[doc_id]
        )
    assert not provider.requests


async def test_missing_retained_artifact_prevents_publication(briefing_db):
    factory, doc_id, _ = briefing_db
    async with factory() as session, session.begin():
        await session.execute(delete(EvidenceArtifactModel))
    async with factory() as session:
        with pytest.raises(ValueError, match="public artifact"):
            await load_briefing_packet(session, topic="Safety", document_ids=[doc_id])


async def test_equivalent_timezone_windows_replay_and_remain_visible(briefing_db):
    factory, doc_id, _ = briefing_db
    provider = BoundProvider()
    start = datetime.fromisoformat("2026-08-01T00:00:00+08:00")
    end = datetime.fromisoformat("2026-10-15T00:00:00+08:00")
    first = await publish_briefing(
        factory,
        BriefingGenerator(provider),
        topic="Safety",
        document_ids=[doc_id],
        window_start=start,
        window_end=end,
    )
    async with factory() as session:
        assert await visible_brief(session, first.brief_id) is not None
    second = await publish_briefing(
        factory,
        BriefingGenerator(provider),
        topic="Safety",
        document_ids=[doc_id],
        window_start=start.astimezone(UTC),
        window_end=end.astimezone(UTC),
    )
    assert second.brief_id == first.brief_id
    assert len(provider.requests) == 2


async def test_frozen_input_and_expired_publication_claim_fail_closed(briefing_db):
    factory, doc_id, _ = briefing_db
    provider = BoundProvider()
    generator = BriefingGenerator(provider)
    with pytest.raises(ValueError, match="frozen editorial input"):
        await publish_briefing(
            factory, generator, topic="Safety", document_ids=[doc_id], expected_digest="different"
        )
    assert not provider.requests

    async def denied(session):
        raise ValueError("editorial claim expired or replaced")

    with pytest.raises(ValueError, match="claim expired"):
        await publish_briefing(
            factory, generator, topic="Safety", document_ids=[doc_id], publication_guard=denied
        )
    from sqlalchemy import select

    from packages.reasoning.briefing_store import IntelligenceBriefModel

    async with factory() as session:
        assert not list(await session.scalars(select(IntelligenceBriefModel)))
