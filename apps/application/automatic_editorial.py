"""Compose bounded material selection, M6 editorial jobs and publication."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.application.public_briefings import load_briefing_packet, publish_briefing
from packages.intelligence.storage.document_models import DocumentModel, DocumentRevisionModel
from packages.reasoning.briefing import BriefingGenerator
from packages.reasoning.editorial import EditorialRunModel, finish_run, utc, verify_claim
from packages.reasoning.editorial_selection import EditorialCandidate, choose_materials
from packages.shared.config import Settings
from packages.sources.storage.models import SourceModel


async def select_editorial_materials(
    session: AsyncSession, *, now: datetime, lookback_days: int, limit: int
) -> dict[str, object]:
    since = now - timedelta(days=lookback_days)
    # Only current revisions; unknown dates, date-only precision and future dates
    # are not silently substituted with ingestion time.
    latest = select(
        DocumentRevisionModel.document_revision_id.label("id"),
        func.row_number()
        .over(
            partition_by=DocumentRevisionModel.document_id,
            order_by=(
                DocumentRevisionModel.created_at.desc(),
                DocumentRevisionModel.document_revision_id.desc(),
            ),
        )
        .label("position"),
    ).subquery()
    rows = (
        await session.execute(
            select(DocumentModel, DocumentRevisionModel, SourceModel)
            .join(
                DocumentRevisionModel,
                DocumentRevisionModel.document_id == DocumentModel.document_id,
            )
            .join(latest, latest.c.id == DocumentRevisionModel.document_revision_id)
            .join(SourceModel, SourceModel.source_id == DocumentModel.source_id)
            .where(
                latest.c.position == 1,
                SourceModel.enabled.is_(True),
                DocumentRevisionModel.published_at >= since,
                DocumentRevisionModel.published_at <= now,
            )
            .order_by(DocumentRevisionModel.published_at.desc(), DocumentModel.document_id)
            .limit(200)
        )
    ).all()
    used = {
        fingerprint
        for selection in await session.scalars(select(EditorialRunModel.selection))
        for fingerprint in _strings(selection.get("fingerprints", []))
    }
    candidates = []
    revisions: dict[str, str] = {}
    for doc, revision, source in rows:
        if source.access_rights.get("classification") != "public" or revision.content_hash in used:
            continue
        try:
            packet = await load_briefing_packet(
                session, topic="选题", document_ids=[doc.document_id]
            )
        except ValueError:
            continue
        material = packet.materials[0]
        if (
            material.revision_id != revision.document_revision_id
            or material.published_at is None
            or not since <= material.published_at <= now
        ):
            continue
        revisions[doc.document_id] = material.revision_id
        candidates.append(
            EditorialCandidate(
                doc.document_id,
                revision.content_hash,
                material.title,
                material.origin_key,
                material.published_at,
            )
        )
    topic, selected = choose_materials(candidates, limit=limit)
    return {
        "topic": topic,
        "document_ids": [c.document_id for c in selected],
        "fingerprints": [c.fingerprint for c in selected],
        "candidate_count": len(candidates),
        "revision_ids": {c.document_id: revisions[c.document_id] for c in selected},
    }


async def execute_editorial(
    factory: async_sessionmaker[AsyncSession],
    generator: BriefingGenerator,
    settings: Settings,
    run_id: str,
    token: str,
) -> str:
    async with factory() as session, session.begin():
        run = await verify_claim(session, run_id, token, now=datetime.now(UTC))
        if not run.selection:
            # Serialize content reservation across slot boundaries. A row lock on
            # this run alone cannot prevent two slots selecting identical inputs.
            if session.get_bind().dialect.name == "postgresql":
                await session.execute(text("SELECT pg_advisory_xact_lock(1397048902)"))
            if utc(run.slot_at) + timedelta(
                hours=settings.editorial_interval_hours
            ) <= datetime.now(UTC):
                await finish_run(
                    session,
                    run_id,
                    token,
                    status="skipped",
                    now=datetime.now(UTC),
                    error="expired unstarted slot",
                )
                return "skipped"
            selection = await select_editorial_materials(
                session,
                now=datetime.now(UTC),
                lookback_days=settings.editorial_lookback_days,
                limit=settings.editorial_max_documents,
            )
            if not selection["document_ids"]:
                run.selection = selection
                await finish_run(
                    session,
                    run_id,
                    token,
                    status="skipped",
                    now=datetime.now(UTC),
                    error="no eligible new material",
                )
                return "skipped"
            packet = await load_briefing_packet(
                session,
                topic=str(selection["topic"]),
                document_ids=_strings(selection["document_ids"]),
            )
            if {m.document_id: m.revision_id for m in packet.materials} != selection[
                "revision_ids"
            ]:
                raise ValueError("selected material changed before editorial freeze")
            selection["input_digest"] = packet.digest(policy=generator.policy)
            selection["policy"] = generator.policy
            run.selection = selection
        selection = dict(run.selection)

    async def guard(session: AsyncSession) -> None:
        await verify_claim(session, run_id, token, now=datetime.now(UTC))

    brief = await publish_briefing(
        factory,
        generator,
        topic=str(selection["topic"]),
        document_ids=_strings(selection["document_ids"]),
        expected_digest=str(selection["input_digest"]),
        publication_guard=guard,
    )
    async with factory() as session, session.begin():
        await finish_run(
            session,
            run_id,
            token,
            status=brief.status,
            now=datetime.now(UTC),
            brief_id=brief.brief_id,
        )
    return brief.status


def _strings(value: object) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("invalid editorial material manifest")
    return value
