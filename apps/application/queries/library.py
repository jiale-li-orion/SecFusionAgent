"""Streaming public catalog projection with exact usable totals and bounded passages.

One SQL statement reads only latest revisions and their first passage; no ORM object
or whole-document loading, per-document queries, model calls, or corpus writes.
Python applies the shared legacy quality gate so totals and pages use the same gate.
"""

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from apps.application.queries.library_subjects import (
    CATEGORY_LABELS,
    SUBJECT_BY_KEY,
    material_subjects,
)
from apps.application.views.library import (
    LibraryFacetView,
    LibraryMaterialView,
    MaterialLibraryView,
)
from apps.application.views.world import WorldStoryEvidenceView
from packages.intelligence.documents.quality import assess_document_quality
from packages.intelligence.storage.document_models import (
    DocumentChunkModel,
    DocumentModel,
    DocumentRevisionModel,
)
from packages.intelligence.storage.evidence_models import EvidenceArtifactModel, ObservationModel
from packages.intelligence.storage.knowledge_models import ObjectModel, RelationModel
from packages.sources.inventory import load_source_inventory
from packages.sources.registry.loader import load_source_definitions
from packages.sources.storage.models import SourceModel

LANDING_TITLES = frozenset(
    {
        "blog",
        "news",
        "latest news",
        "home",
        "resources",
        "publications",
        "documentation",
        "download now",
    }
)
PASSAGE_LIMIT = 6000
EXCERPT_LIMIT = 1800


async def list_material_library(
    session: AsyncSession,
    *,
    limit: int = 48,
    offset: int = 0,
    as_of: datetime | None = None,
    category: str | None = None,
    source: str | None = None,
    subject: str | None = None,
    q: str | None = None,
) -> MaterialLibraryView:
    snapshot = as_of or datetime.now(UTC)
    inventory = load_source_inventory()
    categories = {
        sid: inventory.measurement_category(sid).value
        for sid in inventory.physical_source_categories()
    }
    names = {sid: entry.name for entry in inventory.entries for sid in entry.source_ids}
    definitions = load_source_definitions(Path("config/sources"))
    scoped = {
        definition.source_id
        for definition in definitions
        if any(
            scope.startswith(("ai_", "agent_", "model_")) for scope in definition.authority_scope
        )
    }
    broad = [
        sid
        for sid, value in categories.items()
        if value in {"independent", "incidents"} and sid not in scoped
    ]
    latest = (
        select(
            DocumentRevisionModel.document_revision_id.label("revision_id"),
            func.row_number()
            .over(
                partition_by=DocumentRevisionModel.document_id,
                order_by=(
                    DocumentRevisionModel.created_at.desc(),
                    DocumentRevisionModel.document_revision_id.desc(),
                ),
            )
            .label("position"),
        )
        .where(DocumentRevisionModel.created_at <= snapshot)
        .subquery()
    )
    target = aliased(ObjectModel)
    linked = (
        select(RelationModel.relation_id)
        .join(target, target.object_id == RelationModel.target_object_id)
        .where(
            RelationModel.source_object_id == DocumentModel.object_id,
            RelationModel.lifecycle == "accepted",
            RelationModel.superseded_revision.is_(None),
            target.superseded_revision.is_(None),
            target.object_type.in_(("Repo", "ResearchWork")),
        )
        .exists()
    )
    public_artifact = (
        select(EvidenceArtifactModel.artifact_id)
        .where(
            EvidenceArtifactModel.observation_id == DocumentRevisionModel.observation_id,
            EvidenceArtifactModel.access_rights["classification"].as_string() == "public",
        )
        .exists()
    )
    restricted_artifact = (
        select(EvidenceArtifactModel.artifact_id)
        .where(
            EvidenceArtifactModel.observation_id == DocumentRevisionModel.observation_id,
            or_(
                EvidenceArtifactModel.access_rights["classification"].as_string().is_(None),
                EvidenceArtifactModel.access_rights["classification"].as_string() != "public",
            ),
        )
        .exists()
    )
    statement = (
        select(
            DocumentModel.document_id,
            DocumentModel.object_id,
            DocumentModel.source_id,
            DocumentModel.canonical_url,
            DocumentRevisionModel.document_revision_id,
            DocumentRevisionModel.observation_id,
            DocumentRevisionModel.external_revision,
            func.coalesce(
                DocumentRevisionModel.title,
                DocumentRevisionModel.metadata_json["subject"].as_string(),
                DocumentRevisionModel.metadata_json["title"].as_string(),
            ).label("title"),
            func.substr(
                DocumentRevisionModel.metadata_json["summary"].as_string(), 1, PASSAGE_LIMIT
            ).label("summary"),
            DocumentRevisionModel.metadata_json["content_quality"].label("quality"),
            DocumentRevisionModel.metadata_json["published_date"]
            .as_string()
            .label("published_date"),
            DocumentRevisionModel.published_at,
            DocumentRevisionModel.created_at,
            ObservationModel.observed_at,
            DocumentChunkModel.chunk_id,
            DocumentChunkModel.section,
            func.substr(DocumentChunkModel.text, 1, PASSAGE_LIMIT).label("passage"),
            DocumentChunkModel.locator,
        )
        .join(DocumentRevisionModel, DocumentRevisionModel.document_id == DocumentModel.document_id)
        .join(
            latest,
            (latest.c.revision_id == DocumentRevisionModel.document_revision_id)
            & (latest.c.position == 1),
        )
        .join(ObjectModel, ObjectModel.object_id == DocumentModel.object_id)
        .join(
            ObservationModel,
            (ObservationModel.observation_id == DocumentRevisionModel.observation_id)
            & (ObservationModel.source_id == DocumentModel.source_id),
        )
        .join(SourceModel, SourceModel.source_id == DocumentModel.source_id)
        .outerjoin(
            DocumentChunkModel,
            (DocumentChunkModel.document_revision_id == DocumentRevisionModel.document_revision_id)
            & (DocumentChunkModel.ordinal == 0),
        )
        .where(
            DocumentModel.source_id.in_(categories),
            ObjectModel.superseded_revision.is_(None),
            SourceModel.access_rights["classification"].as_string() == "public",
            public_artifact,
            ~restricted_artifact,
            DocumentModel.source_id.not_in(broad) | linked,
        )
        .order_by(DocumentRevisionModel.created_at.desc(), DocumentModel.document_id)
        .execution_options(yield_per=128)
    )
    # Streaming all compact candidates makes the usable total exact, including legacy
    # material without content_quality metadata. Never fetch the remaining chunks.
    rows = await session.stream(statement)
    items: list[LibraryMaterialView] = []
    totals: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    subject_counts: Counter[str] = Counter()
    query = (q or "").strip().casefold()
    try:
        async for row in rows.mappings():
            quality = row["quality"]
            if isinstance(quality, dict) and (
                quality.get("status") == "rejected" or quality.get("usable") is False
            ):
                continue
            title = (row["title"] or "").strip()
            summary = (row["summary"] or "").strip()
            passage = row["passage"] or ""
            excerpt = summary or passage
            if not title or title.casefold().strip(" .:/—-") in LANDING_TITLES:
                continue
            if not assess_document_quality(
                excerpt, title, canonical_url=row["canonical_url"]
            ).usable:
                continue
            if (
                row["chunk_id"]
                and not assess_document_quality(f"{row['section'] or ''}\n{passage}", title).usable
            ):
                continue
            cat = categories[row["source_id"]]
            subjects = material_subjects(title, f"{summary}\n{passage}")
            totals["corpus"] += 1
            category_counts[cat] += 1
            source_counts[row["source_id"]] += 1
            subject_counts.update(subjects)
            if (
                (category and cat != category)
                or (source and row["source_id"] != source)
                or (subject and subject not in subjects)
            ):
                continue
            if query and query not in f"{title}\n{summary}\n{passage}".casefold():
                continue
            position = totals["filtered"]
            totals["filtered"] += 1
            if not offset <= position < offset + limit:
                continue
            items.append(
                LibraryMaterialView(
                    story_id=f"document:{row['document_id']}",
                    category=cat,
                    kind="document",
                    headline=title,
                    happened_at=row["published_at"] or row["observed_at"],
                    time_basis="published"
                    if row["published_at"] or row["published_date"]
                    else "observed",
                    published_at=row["published_at"],
                    published_date=row["published_date"],
                    observed_at=row["observed_at"],
                    excerpt=excerpt[:EXCERPT_LIMIT],
                    excerpt_origin="source_summary" if summary else "source_excerpt",
                    source_id=row["source_id"],
                    source_name=names.get(row["source_id"], row["source_id"]),
                    object_id=row["object_id"],
                    external_ref=row["canonical_url"],
                    subjects=subjects,
                    evidence=WorldStoryEvidenceView(
                        observation_id=row["observation_id"],
                        document_revision_id=row["document_revision_id"],
                        external_revision=row["external_revision"],
                        chunk_id=None if summary else row["chunk_id"],
                        locator={"kind": "document_metadata", "field": "summary"}
                        if summary
                        else row["locator"] or {},
                    ),
                )
            )
    finally:
        await rows.close()

    def facets(counts, labels):
        return [
            LibraryFacetView(key=key, label=labels(key)[0], label_en=labels(key)[1], count=count)
            for key, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
        ]

    return MaterialLibraryView(
        items=items,
        total=totals["filtered"],
        corpus_total=totals["corpus"],
        offset=offset,
        limit=limit,
        next_offset=offset + limit if offset + limit < totals["filtered"] else None,
        as_of=snapshot,
        categories=facets(category_counts, lambda key: CATEGORY_LABELS.get(key, (key, key))),
        sources=facets(source_counts, lambda key: (names.get(key, key), names.get(key, key))),
        subjects=facets(
            subject_counts,
            lambda key: (
                (SUBJECT_BY_KEY[key].label, SUBJECT_BY_KEY[key].label_en)
                if key in SUBJECT_BY_KEY
                else ("其他主题", "Other subjects")
            ),
        ),
    )
