from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base


class KnowledgeRevisionModel(Base):
    __tablename__ = "knowledge_revisions"

    revision: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cause_processing_run_id: Mapped[str | None] = mapped_column(String(36), index=True)
    cause_observation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("observations.observation_id", ondelete="SET NULL"), index=True
    )
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ObjectModel(Base):
    __tablename__ = "objects"
    __table_args__ = (
        UniqueConstraint("object_type", "canonical_key", name="uq_objects_type_canonical_key"),
    )

    object_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    canonical_key: Mapped[str] = mapped_column(String(512), nullable=False)
    properties: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_revision: Mapped[int] = mapped_column(
        Integer, ForeignKey("knowledge_revisions.revision", ondelete="RESTRICT"), nullable=False
    )
    superseded_revision: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("knowledge_revisions.revision", ondelete="RESTRICT")
    )


class ExternalIdentifierModel(Base):
    __tablename__ = "external_identifiers"
    __table_args__ = (
        UniqueConstraint("namespace", "value", name="uq_external_identifiers_namespace_value"),
    )

    external_identifier_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    namespace: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    object_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("objects.object_id", ondelete="CASCADE"), nullable=False, index=True
    )


class ClaimModel(Base):
    __tablename__ = "claims"

    claim_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    subject_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("objects.object_id", ondelete="CASCADE"), nullable=False, index=True
    )
    predicate: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    value: Mapped[object] = mapped_column(JSON, nullable=False)
    qualifier: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    origin: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    processing_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("processing_runs.run_id", ondelete="SET NULL"), index=True
    )
    created_revision: Mapped[int] = mapped_column(
        Integer, ForeignKey("knowledge_revisions.revision", ondelete="RESTRICT"), nullable=False
    )
    superseded_revision: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("knowledge_revisions.revision", ondelete="RESTRICT")
    )


class RelationModel(Base):
    __tablename__ = "relations"

    relation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_object_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("objects.object_id", ondelete="CASCADE"), nullable=False, index=True
    )
    relation_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_object_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("objects.object_id", ondelete="CASCADE"), nullable=False, index=True
    )
    qualifier: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    origin: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    processing_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("processing_runs.run_id", ondelete="SET NULL"), index=True
    )
    created_revision: Mapped[int] = mapped_column(
        Integer, ForeignKey("knowledge_revisions.revision", ondelete="RESTRICT"), nullable=False
    )
    superseded_revision: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("knowledge_revisions.revision", ondelete="RESTRICT")
    )


class EvidenceLinkModel(Base):
    __tablename__ = "evidence_links"
    __table_args__ = (
        UniqueConstraint(
            "target_kind",
            "target_id",
            "observation_id",
            "locator_hash",
            name="uq_evidence_link_target",
        ),
    )

    evidence_link_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    target_kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    observation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("observations.observation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("evidence_artifacts.artifact_id", ondelete="SET NULL"), index=True
    )
    locator: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    locator_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class KnowledgeChangeModel(Base):
    __tablename__ = "knowledge_changes"

    change_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    revision: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledge_revisions.revision", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    changed_ids: Mapped[dict[str, list[str]]] = mapped_column(JSON, nullable=False)
    cause_processing_run_id: Mapped[str | None] = mapped_column(String(36), index=True)
    cause_observation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("observations.observation_id", ondelete="SET NULL"), index=True
    )
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
