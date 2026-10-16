"""Bounded audit and parser-version replay over retained document evidence."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, Field, JsonValue
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.documents.parsers import (
    HTMLDocumentParser,
    ManagedDocumentParser,
    PDFDocumentParser,
    PlainTextDocumentParser,
)
from packages.intelligence.documents.quality import assess_document_quality
from packages.intelligence.documents.service import ManagedDocumentResult, ManagedDocumentService
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.ingestion.replay import ObservationEnvelopeLoader
from packages.intelligence.storage.artifacts import ArtifactStore, ArtifactStoreUnavailable
from packages.intelligence.storage.document_models import (
    DocumentChunkModel,
    DocumentModel,
    DocumentRevisionModel,
)
from packages.sources.adapters.html_article_metadata import extract_article_metadata
from packages.sources.contracts import IngestEnvelope, SourceDefinition


class DocumentQualityAudit(BaseModel):
    document_id: str
    document_revision_id: str
    observation_id: str
    source_id: str
    parser_name: str
    parser_version: str
    current_parser_version: str | None = None
    stored_quality: dict[str, object] | None = None
    stored_chunk_quality: dict[str, object]
    retained_quality: dict[str, object] | None = None
    publication: dict[str, JsonValue] = Field(default_factory=dict)
    status: str = "audited"
    error_kind: str | None = None


class DocumentQualityMaintenance:
    """Audit without writes; explicitly reparse into ordinary versioned projections.

    Neither method fetches a source or invokes a model. Reparse uses the verified
    original envelope/idempotency key and never changes or deletes old evidence.
    """

    def __init__(self, artifact_store: ArtifactStore) -> None:
        self._loader = ObservationEnvelopeLoader(artifact_store)
        self._parsers: dict[str, ManagedDocumentParser] = {
            "application/pdf": PDFDocumentParser(),
            "text/html": HTMLDocumentParser(),
            "application/xhtml+xml": HTMLDocumentParser(),
            **{
                media_type: PlainTextDocumentParser()
                for media_type in (
                    "text/plain",
                    "text/yaml",
                    "application/yaml",
                    "application/x-yaml",
                    "application/octet-stream",
                )
            },
        }
        self._managed = ManagedDocumentService(EvidenceIngress(artifact_store), self._parsers)

    async def audit_documents(
        self,
        session: AsyncSession,
        *,
        document_ids: Sequence[str] = (),
        limit: int = 20,
    ) -> list[DocumentQualityAudit]:
        if not 1 <= limit <= 100:
            raise ValueError("document audit limit must be between 1 and 100")
        selected = set(document_ids)
        if len(selected) > limit:
            raise ValueError("document selection exceeds limit")
        ranking = select(
            DocumentRevisionModel.document_revision_id,
            func.row_number()
            .over(
                partition_by=DocumentRevisionModel.document_id,
                order_by=(
                    DocumentRevisionModel.created_at.desc(),
                    DocumentRevisionModel.document_revision_id.desc(),
                ),
            )
            .label("rank"),
        )
        if selected:
            ranking = ranking.where(DocumentRevisionModel.document_id.in_(selected))
        ranked = ranking.subquery()
        query = (
            select(DocumentRevisionModel, DocumentModel.source_id)
            .join(DocumentModel, DocumentModel.document_id == DocumentRevisionModel.document_id)
            .join(
                ranked, ranked.c.document_revision_id == DocumentRevisionModel.document_revision_id
            )
            .where(ranked.c.rank == 1)
            .order_by(
                DocumentRevisionModel.created_at.desc(),
                DocumentRevisionModel.document_revision_id.desc(),
            )
            .limit(limit)
        )
        rows = (await session.execute(query)).all()
        if selected - {revision.document_id for revision, _ in rows}:
            raise LookupError("one or more selected documents have no retained revision")
        audits = []
        for revision, source_id in rows:
            chunks = list(
                await session.scalars(
                    select(DocumentChunkModel)
                    .where(DocumentChunkModel.document_revision_id == revision.document_revision_id)
                    .order_by(DocumentChunkModel.ordinal)
                )
            )
            stored = revision.metadata_json.get("content_quality")
            audit = DocumentQualityAudit(
                document_id=revision.document_id,
                document_revision_id=revision.document_revision_id,
                observation_id=revision.observation_id,
                source_id=source_id,
                parser_name=revision.parser_name,
                parser_version=revision.parser_version,
                stored_quality=stored if isinstance(stored, dict) else None,
                stored_chunk_quality=assess_document_quality(
                    "\n".join(
                        "\n".join(filter(None, (chunk.section, chunk.text))) for chunk in chunks
                    ),
                    title=revision.title,
                ).to_metadata(),
                publication={
                    "stored_published_at": revision.published_at.isoformat()
                    if revision.published_at
                    else None
                },
            )
            try:
                replay = await self._loader.load(session, revision.observation_id)
                parser = self._parsers.get(replay.envelope.media_type)
                if parser is None:
                    audit.status = "unsupported_media_type"
                else:
                    audit.current_parser_version = parser.VERSION
                    sections = parser.parse(replay.envelope.content_bytes())
                    audit.retained_quality = assess_document_quality(
                        "\n".join(
                            "\n".join(filter(None, (section.section, section.text)))
                            for section in sections
                        ),
                        title=revision.title,
                        canonical_url=replay.envelope.canonical_url,
                    ).to_metadata()
                    refreshed = _refresh_article_metadata(replay.envelope)
                    audit.publication.update(
                        {
                            key: value
                            for key, value in refreshed.request_metadata.items()
                            if key
                            in {
                                "published_date",
                                "published_at_origin",
                                "published_at_precision",
                                "published_at_raw",
                                "title_origin",
                            }
                        }
                    )
                    audit.publication["retained_published_at"] = (
                        refreshed.published_at.isoformat() if refreshed.published_at else None
                    )
            except (ArtifactStoreUnavailable, RuntimeError, LookupError, ValueError) as exc:
                audit.status = "retained_evidence_unreadable"
                audit.error_kind = type(exc).__name__
            audits.append(audit)
        return audits

    async def reparse_revision(
        self,
        session: AsyncSession,
        *,
        document_revision_id: str,
        source: SourceDefinition,
    ) -> ManagedDocumentResult:
        revision = await session.get(DocumentRevisionModel, document_revision_id)
        if revision is None:
            raise LookupError("document revision not found")
        replay = await self._loader.load(session, revision.observation_id)
        if replay.envelope.source_id != source.source_id:
            raise ValueError("source does not own document revision")
        return await self._managed.ingest(
            session,
            source,
            _refresh_article_metadata(replay.envelope),
        )


def _refresh_article_metadata(envelope: IngestEnvelope) -> IngestEnvelope:
    if envelope.media_type not in {"text/html", "application/xhtml+xml"}:
        return envelope
    article = extract_article_metadata(envelope.content_bytes(), page_url=envelope.canonical_url)
    metadata = dict(envelope.request_metadata)
    if article.title:
        if metadata.get("title"):
            metadata.setdefault("discovery_title", metadata["title"])
        metadata["title"] = article.title
    metadata.update(article.metadata)
    published_at = (
        article.published_at if "published_at_origin" in article.metadata else envelope.published_at
    )
    return envelope.model_copy(update={"request_metadata": metadata, "published_at": published_at})
