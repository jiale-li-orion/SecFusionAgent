from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import String, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.application.views.intelligence import (
    IntelligenceGraphCenterView,
    IntelligenceGraphView,
    IntelligenceSearchItemView,
    IntelligenceSearchView,
    ProductDocumentInsightView,
    ProductDocumentRevisionView,
    ProductDocumentView,
)
from packages.intelligence.knowledge.read import get_object_by_id
from packages.intelligence.storage.document_models import (
    DocumentChunkModel,
    DocumentModel,
    DocumentRevisionModel,
    InsightCandidateModel,
)
from packages.intelligence.storage.knowledge_models import (
    ExternalIdentifierModel,
    ObjectModel,
)


async def search_product_intelligence(
    session: AsyncSession,
    query: str,
    *,
    limit: int = 12,
) -> IntelligenceSearchView:
    normalized = query.strip()
    if len(normalized) < 2:
        return IntelligenceSearchView(query=normalized)

    pattern = f"%{_escape_like(normalized)}%"
    candidates = list(
        await session.scalars(
            select(ObjectModel)
            .outerjoin(
                ExternalIdentifierModel,
                ExternalIdentifierModel.object_id == ObjectModel.object_id,
            )
            .where(
                ObjectModel.superseded_revision.is_(None),
                or_(
                    ObjectModel.canonical_key.ilike(pattern, escape="!"),
                    ExternalIdentifierModel.value.ilike(pattern, escape="!"),
                    cast(ObjectModel.properties, String).ilike(pattern, escape="!"),
                ),
            )
            .limit(max(limit * 8, 64))
        )
    )
    if not candidates:
        return IntelligenceSearchView(query=normalized)

    unique: dict[str, ObjectModel] = {}
    for item in candidates:
        unique.setdefault(item.object_id, item)
    object_ids = list(unique)

    identifiers: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    rows = list(
        await session.scalars(
            select(ExternalIdentifierModel).where(
                ExternalIdentifierModel.object_id.in_(object_ids)
            )
        )
    )
    for row in rows:
        identifiers[row.object_id][row.namespace].append(row.value)

    needle = normalized.casefold()
    ranked = sorted(
        unique.values(),
        key=lambda item: _search_rank(
            item,
            identifiers.get(item.object_id, {}),
            needle,
        ),
    )
    return IntelligenceSearchView(
        query=normalized,
        items=[
            IntelligenceSearchItemView(
                object_id=item.object_id,
                object_type=item.object_type,
                canonical_key=item.canonical_key,
                label=_object_label(item, identifiers.get(item.object_id, {})),
                created_revision=item.created_revision,
                external_identifiers={
                    namespace: sorted(values)
                    for namespace, values in identifiers.get(item.object_id, {}).items()
                },
            )
            for item in ranked[:limit]
        ],
    )


async def get_product_intelligence_graph(
    session: AsyncSession,
    object_id: str,
    *,
    limit: int = 24,
) -> IntelligenceGraphView | None:
    obj = await get_object_by_id(session, object_id)
    if obj is None:
        return None
    label = _knowledge_object_label(
        obj.properties,
        obj.external_identifiers,
        obj.canonical_key,
    )
    return IntelligenceGraphView(
        center=IntelligenceGraphCenterView(
            object_id=obj.object_id,
            object_type=obj.object_type,
            canonical_key=obj.canonical_key,
            label=label,
        ),
        relations=obj.relations[:limit],
        total_relation_count=len(obj.relations),
    )


def _knowledge_object_label(
    properties: dict[str, object],
    identifiers: dict[str, list[str]],
    canonical_key: str,
) -> str:
    for key in ("display_name", "title", "name", "summary"):
        value = properties.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for namespace in ("cve", "cwe", "github_repo", "git_commit_sha", "package"):
        values = identifiers.get(namespace)
        if values:
            return values[0]
    return canonical_key


def _escape_like(value: str) -> str:
    return value.replace("!", "!!").replace("%", "!%").replace("_", "!_")


def _object_label(
    item: ObjectModel,
    identifiers: dict[str, list[str]],
) -> str:
    for key in ("display_name", "title", "name", "summary"):
        value = item.properties.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for namespace in ("cve", "cwe", "git_commit_sha", "package"):
        values = identifiers.get(namespace)
        if values:
            return values[0]
    return item.canonical_key


def _search_rank(
    item: ObjectModel,
    identifiers: dict[str, list[str]],
    needle: str,
) -> tuple[int, int, str]:
    canonical = item.canonical_key.casefold()
    values = [
        value.casefold()
        for namespace_values in identifiers.values()
        for value in namespace_values
    ]
    label = _object_label(item, identifiers).casefold()
    if needle == canonical or needle in values or needle == label:
        tier = 0
    elif canonical.startswith(needle) or any(value.startswith(needle) for value in values):
        tier = 1
    elif label.startswith(needle):
        tier = 2
    elif needle in canonical or any(needle in value for value in values):
        tier = 3
    else:
        tier = 4
    return tier, len(canonical), canonical


async def get_product_document(
    session: AsyncSession,
    *,
    document_id: str | None = None,
    object_id: str | None = None,
) -> ProductDocumentView | None:
    if document_id is None and object_id is None:
        raise ValueError("document_id or object_id is required")
    if document_id is not None:
        document = await session.get(DocumentModel, document_id)
    else:
        document = await session.scalar(
            select(DocumentModel).where(DocumentModel.object_id == object_id)
        )
    if document is None:
        return None

    revision = await session.scalar(
        select(DocumentRevisionModel)
        .where(DocumentRevisionModel.document_id == document.document_id)
        .order_by(DocumentRevisionModel.created_at.desc())
        .limit(1)
    )
    chunks: list[DocumentChunkModel] = []
    insight = None
    if revision is not None:
        chunks = list(
            await session.scalars(
                select(DocumentChunkModel)
                .where(
                    DocumentChunkModel.document_revision_id
                    == revision.document_revision_id
                )
                .order_by(DocumentChunkModel.ordinal)
            )
        )
        insight = await session.scalar(
            select(InsightCandidateModel).where(
                InsightCandidateModel.document_revision_id
                == revision.document_revision_id
            )
        )
    index_counts = Counter(item.index_status for item in chunks)
    return ProductDocumentView(
        document_id=document.document_id,
        object_id=document.object_id,
        source_id=document.source_id,
        external_object_id=document.external_object_id,
        canonical_url=document.canonical_url,
        created_at=document.created_at.isoformat(),
        current_revision=(
            ProductDocumentRevisionView(
                document_revision_id=revision.document_revision_id,
                observation_id=revision.observation_id,
                external_revision=revision.external_revision,
                title=revision.title,
                published_at=revision.published_at.isoformat()
                if revision.published_at
                else None,
                updated_at=revision.updated_at.isoformat()
                if revision.updated_at
                else None,
                content_hash=revision.content_hash,
                parser_name=revision.parser_name,
                parser_version=revision.parser_version,
                created_at=revision.created_at.isoformat(),
            )
            if revision is not None
            else None
        ),
        chunk_count=len(chunks),
        index_status_counts=dict(sorted(index_counts.items())),
        embedded_chunk_count=sum(1 for item in chunks if item.embedding is not None),
        embedding_models=sorted(
            {
                item.embedding_model
                for item in chunks
                if item.embedding_model
            }
        ),
        sections=sorted(
            {
                item.section
                for item in chunks
                if item.section
            }
        ),
        insight=(
            ProductDocumentInsightView(
                insight_candidate_id=insight.insight_candidate_id,
                change_type=insight.change_type,
                evidence_maturity=insight.evidence_maturity,
                promotion_state=insight.promotion_state,
                related_object_ids=list(insight.related_object_ids),
                related_claim_ids=list(insight.related_claim_ids),
                related_relation_ids=list(insight.related_relation_ids),
            )
            if insight is not None
            else None
        ),
    )
