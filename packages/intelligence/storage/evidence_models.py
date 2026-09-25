from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base


class ObservationModel(Base):
    __tablename__ = "observations"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_observations_idempotency_key"),)

    observation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("sources.source_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    acquisition_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("acquisition_runs.run_id", ondelete="SET NULL"), index=True
    )
    external_object_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    external_revision: Mapped[str | None] = mapped_column(String(256), index=True)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceArtifactModel(Base):
    __tablename__ = "evidence_artifacts"
    __table_args__ = (
        UniqueConstraint(
            "observation_id",
            "content_hash",
            name="uq_evidence_artifact_observation_hash",
        ),
    )

    artifact_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    observation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("observations.observation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    media_type: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    access_rights: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    trust_class: Mapped[str] = mapped_column(
        String(64), nullable=False, default="external_untrusted"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
