from datetime import timedelta

from sqlalchemy import select

from apps.application.tests.test_public_briefings import NOW
from apps.application.tests.test_public_briefings import briefing_db as briefing_db
from packages.reasoning.editorial import (
    EditorialRunModel,
    claim_run,
    finish_run,
    schedule_editorial,
    verify_claim,
)
from packages.shared.storage.models import OutboxEventModel


async def test_schedule_replay_claim_fencing_and_next_slot(briefing_db):
    factory, _, _ = briefing_db
    async with factory() as session, session.begin():
        first = await schedule_editorial(session, now=NOW)
        assert await schedule_editorial(session, now=NOW + timedelta(seconds=1)) == first
    async with factory() as session, session.begin():
        assert len(list(await session.scalars(select(OutboxEventModel)))) == 1
        token = await claim_run(session, first, now=NOW)
        assert token is not None
        assert token
        assert await claim_run(session, first, now=NOW) is None
    async with factory() as session, session.begin():
        await verify_claim(session, first, token, now=NOW)
        await finish_run(session, first, token, status="skipped", now=NOW)
    async with factory() as session, session.begin():
        assert await claim_run(session, first, now=NOW) is None
        second = await schedule_editorial(session, now=NOW + timedelta(hours=6))
        assert second != first


async def test_expired_claim_recovers_but_has_bounded_attempts(briefing_db):
    factory, _, _ = briefing_db
    async with factory() as session, session.begin():
        run_id = await schedule_editorial(session, now=NOW)
        token = await claim_run(session, run_id, now=NOW)
        assert token is not None
    later = NOW + timedelta(minutes=21)
    async with factory() as session, session.begin():
        await schedule_editorial(session, now=later)
        new_token = await claim_run(session, run_id, now=later)
        assert new_token and new_token != token
        assert not await finish_run(session, run_id, token, status="published", now=later)
    async with factory() as session, session.begin():
        await schedule_editorial(session, now=later + timedelta(minutes=21))
        assert (await session.get(EditorialRunModel, run_id)).status == "failed"
        assert await claim_run(session, run_id, now=later) is None


def test_topic_selection_deduplicates_and_prefers_complementary_sources():
    from packages.reasoning.editorial_selection import EditorialCandidate, choose_materials

    def candidate(identity, origin, age=0, fingerprint=None):
        return EditorialCandidate(
            identity,
            fingerprint or identity,
            "Agent boundary research",
            origin,
            NOW - timedelta(hours=age),
        )

    topic, chosen = choose_materials(
        [
            candidate("a", "vendor"),
            candidate("b", "vendor", 1),
            candidate("c", "researcher", 2),
            candidate("reprint", "other", 3, "a"),
        ],
        limit=2,
    )
    assert topic == "Agent 安全与权限边界"
    assert [c.document_id for c in chosen] == ["a", "c"]
