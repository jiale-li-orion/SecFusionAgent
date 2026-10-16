from datetime import UTC, datetime, timedelta

from apps.application.automatic_editorial import execute_editorial, select_editorial_materials
from apps.application.tests.test_public_briefings import BoundProvider
from apps.application.tests.test_public_briefings import briefing_db as briefing_db
from packages.intelligence.storage.document_models import DocumentRevisionModel
from packages.reasoning.briefing import BriefingGenerator
from packages.reasoning.editorial import EditorialRunModel, claim_run, schedule_editorial
from packages.shared.config import Settings
from packages.sources.storage.models import SourceModel


async def test_selection_excludes_stale_private_and_attempted_content(briefing_db):
    factory, doc_id, revision_id = briefing_db
    now = datetime.now(UTC)
    async with factory() as session, session.begin():
        assert not (await select_editorial_materials(session, now=now, lookback_days=14, limit=4))[
            "document_ids"
        ]
        revision = await session.get(DocumentRevisionModel, revision_id)
        revision.published_at = now - timedelta(days=1)
    async with factory() as session, session.begin():
        selected = await select_editorial_materials(session, now=now, lookback_days=14, limit=4)
        assert selected["document_ids"] == [doc_id]
        run_id = await schedule_editorial(session, now=now)
        run = await session.get(EditorialRunModel, run_id)
        run.selection = selected
    async with factory() as session, session.begin():
        assert not (await select_editorial_materials(session, now=now, lookback_days=14, limit=4))[
            "document_ids"
        ]
        run = await session.get(EditorialRunModel, run_id)
        run.selection = {}
        source = await session.get(SourceModel, "arxiv-ai-security")
        source.access_rights = {"classification": "private"}
    async with factory() as session:
        assert not (await select_editorial_materials(session, now=now, lookback_days=14, limit=4))[
            "document_ids"
        ]


async def test_auto_cycle_publishes_summary_and_records_terminal_run(briefing_db):
    factory, doc_id, revision_id = briefing_db
    now = datetime.now(UTC)
    async with factory() as session, session.begin():
        (await session.get(DocumentRevisionModel, revision_id)).published_at = now - timedelta(
            days=1
        )
        run_id = await schedule_editorial(session, now=now)
        token = await claim_run(session, run_id, now=now)
        assert token is not None
    provider = BoundProvider()
    assert (
        await execute_editorial(factory, BriefingGenerator(provider), Settings(), run_id, token)
        == "published"
    )
    assert len(provider.requests) == 2
    async with factory() as session:
        run = await session.get(EditorialRunModel, run_id)
        assert run.status == "published" and run.brief_id
        assert run.selection["document_ids"] == [doc_id]
        assert run.selection["input_digest"]


async def test_arriving_revision_cannot_escape_date_or_fingerprint_checks(briefing_db, monkeypatch):
    import apps.application.automatic_editorial as module

    factory, _, revision_id = briefing_db
    now = datetime.now(UTC)
    async with factory() as session, session.begin():
        (await session.get(DocumentRevisionModel, revision_id)).published_at = now - timedelta(
            days=1
        )
    original = module.load_briefing_packet

    async def changed(*args, **kwargs):
        packet = await original(*args, **kwargs)
        packet.materials[0].revision_id = "new-arriving-revision"
        packet.materials[0].published_at = now + timedelta(days=1)
        return packet

    monkeypatch.setattr(module, "load_briefing_packet", changed)
    async with factory() as session:
        selected = await select_editorial_materials(session, now=now, lookback_days=14, limit=4)
        assert not selected["document_ids"]
