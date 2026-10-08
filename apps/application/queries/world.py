from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from apps.application.views.world import (
    WorldKnowledgeChangeListView,
    WorldKnowledgeChangeView,
    WorldStoryEvidenceView,
    WorldStoryListView,
    WorldStoryView,
)
from packages.intelligence.storage.document_models import (
    DocumentChunkModel,
    DocumentModel,
    DocumentRevisionModel,
)
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.incident_models import SecurityIncidentModel
from packages.intelligence.storage.knowledge_models import (
    KnowledgeChangeModel,
    KnowledgeRevisionModel,
    ObjectModel,
    RelationModel,
)
from packages.sources.inventory import load_source_inventory
from packages.sources.registry.loader import load_source_definitions


async def list_world_stories(session: AsyncSession, *, limit: int = 10) -> WorldStoryListView:
    """Read source facts, never create a security judgment or rewrite external prose.

    Latest revision per document; bounded per-source reads prevent a busy mailing list
    from displacing research. Broad independent/news feeds need a durable relation.
    Category interleaving is coverage, not a relevance score.
    """
    inventory = load_source_inventory()
    categories = {
        sid: inventory.measurement_category(sid).value
        for sid in inventory.physical_source_categories()
    }
    names = {sid: entry.name for entry in inventory.entries for sid in entry.source_ids}
    latest = select(
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
    ).subquery()
    # Source scope is registry-owned. A broad feed only enters through a typed
    # connection to the managed AI corpus; arbitrary exploratory relations do not qualify.
    definitions = load_source_definitions(Path("config/sources"))
    scoped_sources = {
        definition.source_id
        for definition in definitions
        if any(
            scope.startswith(("ai_", "agent_", "model_")) for scope in definition.authority_scope
        )
    }
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
    broad_sources = [
        sid
        for sid, category in categories.items()
        if category in {"independent", "incidents"} and sid not in scoped_sources
    ]
    ranked = (
        select(
            DocumentRevisionModel.document_revision_id.label("revision_id"),
            func.row_number()
            .over(
                partition_by=DocumentModel.source_id,
                order_by=(
                    DocumentRevisionModel.updated_at.desc().nullslast(),
                    DocumentRevisionModel.published_at.desc().nullslast(),
                    DocumentRevisionModel.created_at.desc(),
                    DocumentModel.document_id,
                ),
            )
            .label("source_position"),
        )
        .join(DocumentModel, DocumentModel.document_id == DocumentRevisionModel.document_id)
        .join(latest, latest.c.revision_id == DocumentRevisionModel.document_revision_id)
        .where(
            latest.c.position == 1,
            DocumentModel.source_id.in_(categories),
            DocumentModel.source_id.not_in(broad_sources) | linked,
        )
        .subquery()
    )
    document_rows = (
        await session.execute(
            select(DocumentModel, DocumentRevisionModel)
            .join(
                DocumentRevisionModel,
                DocumentRevisionModel.document_id == DocumentModel.document_id,
            )
            .join(ranked, ranked.c.revision_id == DocumentRevisionModel.document_revision_id)
            .where(ranked.c.source_position <= limit)
        )
    ).all()
    candidates: list[WorldStoryView] = []
    revisions: dict[str, DocumentRevisionModel] = {}
    for document, revision in document_rows:
        title = (
            revision.title
            or _string(revision.metadata_json, "subject")
            or _string(revision.metadata_json, "title")
        )
        if not title:
            continue
        story = WorldStoryView(
            story_id=f"document:{document.document_id}",
            category=categories[document.source_id],
            kind="document",
            headline=title,
            happened_at=revision.updated_at or revision.published_at or revision.created_at,
            published_at=revision.published_at,
            observed_at=revision.created_at,
            excerpt=_string(revision.metadata_json, "summary"),
            excerpt_origin="source_summary" if _string(revision.metadata_json, "summary") else None,
            source_id=document.source_id,
            source_name=names.get(document.source_id),
            object_id=document.object_id,
            external_ref=document.canonical_url,
            evidence=WorldStoryEvidenceView(
                observation_id=revision.observation_id,
                document_revision_id=revision.document_revision_id,
                external_revision=revision.external_revision,
                locator={"kind": "document_metadata", "field": "summary"},
            ),
        )
        candidates.append(story)
        revisions[story.story_id] = revision

    object_rows = (
        await session.execute(
            select(ObjectModel, KnowledgeRevisionModel, ObservationModel)
            .join(
                KnowledgeRevisionModel,
                KnowledgeRevisionModel.revision == ObjectModel.created_revision,
            )
            .outerjoin(
                ObservationModel,
                ObservationModel.observation_id == KnowledgeRevisionModel.cause_observation_id,
            )
            .where(
                ObjectModel.superseded_revision.is_(None),
                ObjectModel.object_type.in_(
                    ("Issue", "PullRequest", "Commit", "Release", "InternetAsset")
                ),
            )
            .order_by(KnowledgeRevisionModel.committed_at.desc())
            .limit(limit * 2)
        )
    ).all()
    for obj, _revision, observation in object_rows:
        title = _string(obj.properties, "title") or _string(obj.properties, "name")
        if obj.object_type == "InternetAsset":
            title = _string(obj.properties, "ip") or _string(obj.properties, "hostname")
        if not title or observation is None:
            continue  # An opaque SHA or identity alone is not an event narrative.
        candidates.append(
            WorldStoryView(
                story_id=f"object:{obj.object_id}",
                category="assets" if obj.object_type == "InternetAsset" else "development",
                kind=obj.object_type,
                headline=title,
                happened_at=observation.updated_at
                or observation.published_at
                or observation.observed_at,
                observed_at=observation.observed_at,
                excerpt=_string(obj.properties, "body") or _string(obj.properties, "description"),
                excerpt_origin="source_field",
                facts=obj.properties,
                source_id=observation.source_id,
                source_name=names.get(observation.source_id),
                object_id=obj.object_id,
                external_ref=_string(obj.properties, "html_url") or observation.canonical_url,
                evidence=WorldStoryEvidenceView(
                    observation_id=observation.observation_id,
                    external_revision=observation.external_revision,
                    locator={"kind": "structured_object", "object_id": obj.object_id},
                ),
            )
        )
    for incident in await session.scalars(
        select(SecurityIncidentModel).order_by(SecurityIncidentModel.updated_at.desc()).limit(limit)
    ):
        if incident.current_summary:
            candidates.append(
                WorldStoryView(
                    story_id=f"incident:{incident.incident_id}",
                    category="incidents",
                    kind="Incident",
                    headline=incident.current_summary,
                    happened_at=incident.updated_at,
                    observed_at=incident.updated_at,
                    incident_id=incident.incident_id,
                    facts={"incident_type": incident.incident_type},
                )
            )

    selected = _interleave(candidates, limit)
    missing = {
        revisions[item.story_id].document_revision_id: item
        for item in selected
        if item.story_id in revisions and not item.excerpt
    }
    if missing:
        for chunk in await session.scalars(
            select(DocumentChunkModel).where(
                DocumentChunkModel.document_revision_id.in_(missing),
                DocumentChunkModel.ordinal == 0,
            )
        ):
            story = missing[chunk.document_revision_id]
            story.excerpt = chunk.text
            story.excerpt_origin = "source_excerpt"
            if story.evidence is not None:
                story.evidence.locator = chunk.locator
                story.evidence.chunk_id = chunk.chunk_id
    return WorldStoryListView(items=selected)


def _string(properties: dict[str, object], key: str) -> str | None:
    value = properties.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _interleave(candidates: list[WorldStoryView], limit: int) -> list[WorldStoryView]:
    groups: dict[str, list[WorldStoryView]] = defaultdict(list)
    for story in sorted(
        candidates,
        key=lambda item: (
            item.excerpt_origin == "source_summary",
            item.published_at or item.happened_at,
            item.story_id,
        ),
        reverse=True,
    ):
        groups[story.category].append(story)
    for category, items in groups.items():
        sources: dict[str | None, list[WorldStoryView]] = defaultdict(list)
        for item in items:
            sources[item.source_id].append(item)
        groups[category] = []
        while sources:
            for source in list(sources):
                groups[category].append(sources[source].pop(0))
                if not sources[source]:
                    del sources[source]
    result: list[WorldStoryView] = []
    while groups and len(result) < limit:
        for category in list(groups):
            result.append(groups[category].pop(0))
            if not groups[category]:
                del groups[category]
            if len(result) == limit:
                break
    return result


async def list_world_knowledge_changes(
    session: AsyncSession,
    *,
    limit: int = 12,
) -> WorldKnowledgeChangeListView:
    changes = list(
        await session.scalars(
            select(KnowledgeChangeModel)
            .order_by(
                KnowledgeChangeModel.revision.desc(),
                KnowledgeChangeModel.committed_at.desc(),
            )
            .limit(limit)
        )
    )
    return WorldKnowledgeChangeListView(
        items=[
            WorldKnowledgeChangeView(
                change_id=change.change_id,
                revision=change.revision,
                committed_at=change.committed_at,
                object_ids=_changed_ids(change, "objects"),
                claim_ids=_changed_ids(change, "claims"),
                relation_ids=_changed_ids(change, "relations"),
                cause_processing_run_id=change.cause_processing_run_id,
                cause_observation_id=change.cause_observation_id,
            )
            for change in changes
        ]
    )


def _changed_ids(change: KnowledgeChangeModel, key: str) -> list[str]:
    value = change.changed_ids.get(key, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def world_source_names() -> dict[str, str]:
    return {
        source_id: entry.name
        for entry in load_source_inventory().entries
        for source_id in entry.source_ids
    }
