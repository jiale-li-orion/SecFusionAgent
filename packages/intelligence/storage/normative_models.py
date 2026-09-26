from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base


class NormativeDocumentModel(Base):
    __tablename__ = "normative_documents"
    __table_args__ = (
        UniqueConstraint("document_id", name="uq_normative_document_managed_document"),
    )

    normative_document_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.document_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NormativeDocumentRevisionModel(Base):
    __tablename__ = "normative_document_revisions"
    __table_args__ = (
        UniqueConstraint(
            "document_revision_id",
            name="uq_normative_revision_document_revision",
        ),
    )

    normative_revision_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    normative_document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("normative_documents.normative_document_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_revision_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_revisions.document_revision_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    processing_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("processing_runs.run_id", ondelete="SET NULL"),
        index=True,
    )
    issuer: Mapped[str | None] = mapped_column(Text)
    jurisdiction: Mapped[str | None] = mapped_column(String(256), index=True)
    document_type: Mapped[str | None] = mapped_column(String(128), index=True)
    binding_status: Mapped[str | None] = mapped_column(String(128), index=True)
    publication_date: Mapped[date | None] = mapped_column(Date)
    effective_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str | None] = mapped_column(String(64), index=True)
    external_version: Mapped[str | None] = mapped_column(String(256))
    official_url: Mapped[str | None] = mapped_column(Text)
    access_rights: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    full_text_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    supersedes_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    amends_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    references: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    metadata_facts: Mapped[list[dict[str, object]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NormativeRequirementModel(Base):
    __tablename__ = "normative_requirements"

    requirement_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    normative_revision_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("normative_document_revisions.normative_revision_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    processing_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("processing_runs.run_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_clause: Mapped[str | None] = mapped_column(Text)
    modality: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    object_text: Mapped[str] = mapped_column(Text, nullable=False)
    condition_text: Mapped[str | None] = mapped_column(Text)
    exception_text: Mapped[str | None] = mapped_column(Text)
    jurisdiction: Mapped[str | None] = mapped_column(String(256), index=True)
    applicability: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    applicability_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="not_evaluated",
        index=True,
    )
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    risk_mapping: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    evidence_locator: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    evidence_quote: Mapped[str] = mapped_column(Text, nullable=False)
    lifecycle: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="accepted",
        index=True,
    )
    superseded_by_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("processing_runs.run_id", ondelete="SET NULL"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NormativeControlModel(Base):
    __tablename__ = "normative_controls"
    __table_args__ = (UniqueConstraint("canonical_key", name="uq_normative_control_canonical_key"),)

    control_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    canonical_key: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NormativeControlEvidenceModel(Base):
    __tablename__ = "normative_control_evidence"

    control_evidence_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    control_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("normative_controls.control_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    normative_revision_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("normative_document_revisions.normative_revision_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    processing_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("processing_runs.run_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    evidence_locator: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    evidence_quote: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RequirementControlMappingModel(Base):
    __tablename__ = "requirement_control_mappings"
    __table_args__ = (
        UniqueConstraint(
            "requirement_id",
            "control_id",
            "relation_type",
            name="uq_requirement_control_relation",
        ),
    )

    mapping_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    requirement_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("normative_requirements.requirement_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    control_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("normative_controls.control_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    evidence_locator: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    evidence_quote: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
