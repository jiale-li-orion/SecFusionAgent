"""Bounded display excerpts from existing, public Evidence; no new factual synthesis."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.application.views.recommendations import PreviewOrigin
from packages.intelligence.knowledge.read import EvidenceRef
from packages.intelligence.storage.document_models import DocumentChunkModel, DocumentRevisionModel
from packages.intelligence.storage.evidence_models import EvidenceArtifactModel, ObservationModel
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    EvidenceLinkModel,
    ObjectModel,
)
from packages.sources.storage.models import SourceModel


@dataclass(frozen=True)
class PreviewText:
    text: str | None = None
    origin: PreviewOrigin | None = None
    evidence_ref: str | None = None
    chunk_ref: str | None = None


_GENERIC_TITLES = frozenset(
    {
        "home",
        "blog",
        "news",
        "latest news",
        "resources",
        "publications",
        "documentation",
        "download now",
        "insights",
        "intelligence center",
        "research",
        "our authors",
    }
)
_NAVIGATION_MARKERS = (
    "sort by:",
    "our authors",
    "read more from",
    "all categories",
    "skip to content",
    "sign in",
    "subscribe to",
    "cookie preferences",
)


_DATE_PREFIX = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+\d{1,2},?\s+\d{4}\s+"
)
_CATEGORY_PREFIX = r"(?:Announcements|News|Research|Insights|Blog)\s+"


def _text(
    value: object,
    limit: int,
    *,
    title: bool = False,
    heading: str | None = None,
) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if title:
        # A date followed by a section label is page metadata, not article prose.
        text = re.sub("^" + _DATE_PREFIX + _CATEGORY_PREFIX, "", text, flags=re.IGNORECASE)
    elif heading:
        candidate = re.sub("^" + _CATEGORY_PREFIX, "", text, flags=re.IGNORECASE)
        if candidate.casefold().startswith(heading.casefold() + " "):
            text = candidate[len(heading) :].lstrip()
            text = re.sub("^" + _DATE_PREFIX, "", text, flags=re.IGNORECASE)
    if not text:
        return None
    if title and text.casefold().strip(" .:/—-") in _GENERIC_TITLES:
        return None
    # Several independent UI controls in the opening passage signal a directory or
    # page shell. A lone word such as "category" in technical prose is not enough.
    opening = text[:600].casefold()
    if sum(marker in opening for marker in _NAVIGATION_MARKERS) >= 2:
        return None
    if len(text) <= limit:
        return text
    prefix = text[: limit - 1]
    sentences = list(re.finditer(r"(?:[.!?](?=\s|$)|[\u3002\uff01\uff1f])", prefix))
    if sentences and sentences[-1].end() >= limit // 2:
        return prefix[: sentences[-1].end()]
    # Do not cut a Latin word/identifier midway. Text without word separators has
    # no safe word boundary, so omit it instead of returning a broken identifier.
    boundary = prefix.rfind(" ")
    return prefix[:boundary].rstrip() + "…" if boundary > 0 else None


def canonical_preview(
    obj: ObjectModel,
    claims: list[ClaimModel],
    evidence_by_fact: dict[str, list[EvidenceRef]],
    *,
    title: bool,
) -> PreviewText:
    keys = (
        ("display_name", "title", "name", "summary")
        if title
        else ("summary", "description", "abstract")
    )
    limit = 180 if title else 320
    heading = (
        next(
            (
                text
                for key in ("display_name", "title", "name")
                if (text := _text(obj.properties.get(key), 180, title=True))
            ),
            None,
        )
        if not title
        else None
    )
    for key in keys:
        if text := _text(obj.properties.get(key), limit, title=title, heading=heading):
            # Canonical properties have no field-level EvidenceLink; do not invent one.
            return PreviewText(text, "canonical_property")
    for key in keys:
        for claim in sorted(claims, key=lambda row: (-row.created_revision, row.claim_id)):
            if claim.predicate == key and (
                text := _text(claim.value, limit, title=title, heading=heading)
            ):
                return PreviewText(
                    text, "accepted_claim", evidence_by_fact[claim.claim_id][0].evidence_ref
                )
    return PreviewText()


async def retained_previews(
    session: AsyncSession,
    evidence: list[EvidenceRef],
) -> dict[str, tuple[PreviewText, PreviewText]]:
    """Latest parser revision and first chunk of each exact cited public observation."""
    if not evidence:
        return {}
    observations = {item.observation_id for item in evidence}
    revisions = (
        select(
            DocumentRevisionModel.document_revision_id,
            DocumentRevisionModel.observation_id,
            DocumentRevisionModel.title,
            func.row_number()
            .over(
                partition_by=DocumentRevisionModel.observation_id,
                order_by=(
                    DocumentRevisionModel.created_at.desc(),
                    DocumentRevisionModel.document_revision_id.desc(),
                ),
            )
            .label("rank"),
        )
        .where(DocumentRevisionModel.observation_id.in_(observations))
        .subquery()
    )
    first_chunks = (
        select(
            DocumentChunkModel.document_revision_id,
            DocumentChunkModel.chunk_id,
            DocumentChunkModel.text,
            func.row_number()
            .over(
                partition_by=DocumentChunkModel.document_revision_id,
                order_by=DocumentChunkModel.ordinal,
            )
            .label("rank"),
        )
        .where(
            DocumentChunkModel.document_revision_id.in_(
                select(revisions.c.document_revision_id).where(revisions.c.rank == 1)
            )
        )
        .subquery()
    )
    rows = (
        await session.execute(
            select(
                EvidenceLinkModel.evidence_link_id,
                revisions.c.title,
                revisions.c.document_revision_id,
                first_chunks.c.chunk_id,
                first_chunks.c.text,
            )
            .select_from(EvidenceLinkModel)
            .join(
                ObservationModel,
                ObservationModel.observation_id == EvidenceLinkModel.observation_id,
            )
            .join(SourceModel, SourceModel.source_id == ObservationModel.source_id)
            .outerjoin(
                EvidenceArtifactModel,
                EvidenceArtifactModel.artifact_id == EvidenceLinkModel.artifact_id,
            )
            .join(
                revisions,
                (revisions.c.observation_id == ObservationModel.observation_id)
                & (revisions.c.rank == 1),
            )
            .outerjoin(
                first_chunks,
                (first_chunks.c.document_revision_id == revisions.c.document_revision_id)
                & (first_chunks.c.rank == 1),
            )
            .where(
                EvidenceLinkModel.evidence_link_id.in_(
                    [item.evidence_ref.removeprefix("evidence:") for item in evidence]
                ),
                SourceModel.retention_mode == "durable_managed",
                SourceModel.access_rights["classification"].as_string() == "public",
                or_(
                    EvidenceArtifactModel.artifact_id.is_(None),
                    EvidenceArtifactModel.access_rights["classification"].as_string().is_(None),
                    EvidenceArtifactModel.access_rights["classification"].as_string() == "public",
                ),
            )
        )
    ).all()
    result = {}
    for link_id, title, revision_id, chunk_id, text in rows:
        ref = f"evidence:{link_id}"
        chunk_ref = f"document-chunk:{chunk_id}@{revision_id}" if chunk_id else None
        result[ref] = (
            PreviewText(_text(title, 180, title=True), "retained_excerpt", ref),
            PreviewText(
                _text(text, 320, heading=_text(title, 180, title=True)),
                "retained_excerpt",
                ref,
                chunk_ref,
            ),
        )
    return result
