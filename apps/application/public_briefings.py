"""Compose public material, M4/M6 editorial generation and durable publication.

No user Case or private Decision can be selected by this entry point. Generation
runs outside database transactions; source visibility and revisions are rechecked
before committing and again at public read time.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.intelligence.documents.quality import assess_document_quality
from packages.intelligence.storage.document_models import (
    DocumentChunkModel,
    DocumentModel,
    DocumentRevisionModel,
)
from packages.intelligence.storage.evidence_models import EvidenceArtifactModel
from packages.investigation.briefing import BriefingMaterial, BriefingPacket, BriefingPassage
from packages.reasoning.briefing import BriefingGenerator
from packages.reasoning.briefing_store import IntelligenceBriefModel
from packages.reasoning.report_html import safe_source_url
from packages.reasoning.storage import DecisionResultStore
from packages.sources.storage.models import SourceModel


async def load_briefing_packet(
    session: AsyncSession,
    *,
    topic: str,
    document_ids: list[str],
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> BriefingPacket:
    ids = sorted(set(document_ids))
    if not 1 <= len(ids) <= 8:
        raise ValueError("select between one and eight public documents")
    materials = []
    for document_id in ids:
        document = await session.get(DocumentModel, document_id)
        if document is None or safe_source_url(document.canonical_url) is None:
            raise ValueError("public document with a source URL is required")
        source = await session.get(SourceModel, document.source_id)
        if source is None or source.access_rights.get("classification") != "public":
            raise ValueError("only explicitly public sources may enter public briefings")
        revision = await session.scalar(
            select(DocumentRevisionModel)
            .where(
                DocumentRevisionModel.document_id == document_id,
            )
            .order_by(
                DocumentRevisionModel.created_at.desc(),
                DocumentRevisionModel.document_revision_id.desc(),
            )
            .limit(1)
        )
        if revision is None:
            raise ValueError("public document has no retained revision")
        artifacts = list(
            await session.scalars(
                select(EvidenceArtifactModel).where(
                    EvidenceArtifactModel.observation_id == revision.observation_id,
                )
            )
        )
        if not artifacts or any(
            item.access_rights.get("classification") != "public" for item in artifacts
        ):
            raise ValueError("retained public artifact is required")
        quality = revision.metadata_json.get("content_quality")
        if isinstance(quality, dict) and (
            quality.get("usable") is False or quality.get("status") == "rejected"
        ):
            raise ValueError("document rejected by material quality assessment")
        chunks = list(
            await session.scalars(
                select(DocumentChunkModel)
                .where(
                    DocumentChunkModel.document_revision_id == revision.document_revision_id,
                )
                .order_by(DocumentChunkModel.ordinal)
                .limit(5)
            )
        )
        if (
            not chunks
            or not assess_document_quality(
                "\n".join(f"{chunk.section or ''}\n{chunk.text}" for chunk in chunks),
                revision.title,
            ).usable
        ):
            raise ValueError("document rejected by material quality assessment")
        materials.append(
            BriefingMaterial(
                document_id=document_id,
                revision_id=revision.document_revision_id,
                source_id=source.source_id,
                source_role=source.source_role,
                origin_key=source.upstream_source or source.source_family,
                title=revision.title or "未命名材料",
                url=document.canonical_url or "",
                published_at=_utc(revision.published_at),
                published_date=str(revision.metadata_json["published_date"])
                if revision.metadata_json.get("published_date")
                else None,
                passages=[
                    BriefingPassage(
                        evidence_ref=f"document-chunk:{chunk.chunk_id}@{revision.document_revision_id}",
                        text=chunk.text[:8000],
                        section=chunk.section,
                    )
                    for chunk in chunks[:4]
                ],
                truncated=len(chunks) > 4 or any(len(chunk.text) > 8000 for chunk in chunks[:4]),
            )
        )
    return BriefingPacket(
        topic=topic, materials=materials, window_start=window_start, window_end=window_end
    )


async def publish_briefing(
    factory: async_sessionmaker[AsyncSession],
    generator: BriefingGenerator,
    *,
    topic: str,
    document_ids: list[str],
    now: datetime | None = None,
    expected_digest: str | None = None,
    publication_guard: Callable[[AsyncSession], Awaitable[None]] | None = None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> IntelligenceBriefModel:
    async with factory() as session:
        packet = await load_briefing_packet(
            session,
            topic=topic,
            document_ids=document_ids,
            window_start=window_start,
            window_end=window_end,
        )
        digest = packet.digest(policy=generator.policy)
        if expected_digest is not None and digest != expected_digest:
            raise ValueError("frozen editorial input changed")
        brief_id = "brief:" + digest[:32]
        existing = await session.get(IntelligenceBriefModel, brief_id)
        if existing is not None:
            return existing
    generated = await generator.generate(packet, now=now or datetime.now(UTC))
    try:
        async with factory() as session, session.begin():
            if publication_guard is not None:
                await publication_guard(session)
            # Lock selected parents so simultaneous publishers serialize their final
            # idempotency check. The source revision is still rechecked below.
            await session.execute(
                select(DocumentModel.document_id)
                .where(
                    DocumentModel.document_id.in_(sorted(set(document_ids))),
                )
                .order_by(DocumentModel.document_id)
                .with_for_update()
            )
            current = await load_briefing_packet(
                session,
                topic=topic,
                document_ids=document_ids,
                window_start=window_start,
                window_end=window_end,
            )
            if current.digest(policy=generator.policy) != digest:
                raise ValueError("source material changed during briefing generation; retry")
            existing = await session.get(IntelligenceBriefModel, brief_id)
            if existing is not None:
                return existing
            stored = await DecisionResultStore().persist(session, generated.decision)
            layout = generated.decision.report_layout
            row = IntelligenceBriefModel(
                brief_id=brief_id,
                input_digest=digest,
                topic=topic,
                title=layout.title if layout else topic,
                decision_id=stored.decision_id,
                status="published" if generated.publishable else "review_required",
                material_manifest=[
                    material.model_dump(mode="json", exclude={"passages"})
                    for material in packet.materials
                ],
                review_json={
                    **generated.review.model_dump(mode="json"),
                    "publication_issues": generated.publication_issues,
                    "revision_history": generated.revision_history,
                },
                policy_revision=generator.policy,
                window_start=packet.window_start,
                window_end=packet.window_end,
                created_at=now or datetime.now(UTC),
            )
            session.add(row)
            await session.flush()
            return row
    except IntegrityError:
        # A concurrent identical publication may win. Never hide unrelated DB errors.
        async with factory() as session:
            existing = await session.get(IntelligenceBriefModel, brief_id)
            if existing is not None and existing.input_digest == digest:
                return existing
        raise


async def visible_brief(session: AsyncSession, brief_id: str) -> IntelligenceBriefModel | None:
    row = await session.get(IntelligenceBriefModel, brief_id)
    if row is None or row.status != "published" or not row.material_manifest:
        return None
    try:
        packet = await load_briefing_packet(
            session,
            topic=row.topic,
            document_ids=[str(item["document_id"]) for item in row.material_manifest],
            window_start=_utc(row.window_start),
            window_end=_utc(row.window_end),
        )
    except (ValueError, KeyError):
        return None
    if packet.digest(policy=row.policy_revision) != row.input_digest:
        return None
    return row


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
