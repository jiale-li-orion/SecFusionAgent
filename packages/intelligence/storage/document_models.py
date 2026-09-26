from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base


class DocumentModel(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("source_id", "external_object_id", name="uq_document_source_external"),
    )

    document_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    object_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("objects.object_id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    external_object_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DocumentRevisionModel(Base):
    __tablename__ = "document_revisions"
    __table_args__ = (UniqueConstraint("observation_id", name="uq_document_revision_observation"),)

    document_revision_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.document_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    observation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("observations.observation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_revision: Mapped[str | None] = mapped_column(String(256), index=True)
    title: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    parser_name: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DocumentChunkModel(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_revision_id",
            "ordinal",
            name="uq_document_chunk_revision_ordinal",
        ),
    )

    chunk_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_revision_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_revisions.document_revision_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str | None] = mapped_column(String(256))
    page_number: Mapped[int | None] = mapped_column(Integer, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    locator: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    chunker_version: Mapped[str] = mapped_column(String(32), nullable=False)
    index_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    embedding: Mapped[list[float] | None] = mapped_column(Vector().with_variant(JSON(), "sqlite"))
    embedding_model: Mapped[str | None] = mapped_column(String(128))
    embedding_version: Mapped[str | None] = mapped_column(String(128))


class InsightCandidateModel(Base):
    __tablename__ = "insight_candidates"

    insight_candidate_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_revision_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_revisions.document_revision_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    change_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    evidence_maturity: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    promotion_state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    related_object_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    related_claim_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    related_relation_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
