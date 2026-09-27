from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base


class SkillVersionModel(Base):
    __tablename__ = "skill_versions"
    __table_args__ = (UniqueConstraint("skill_id", "version", name="uq_skill_versions_identity"),)

    skill_version_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    skill_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    namespace: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    manifest_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    procedure_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    provenance_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_ref: Mapped[str | None] = mapped_column(String(256), index=True)
    supersedes: Mapped[str | None] = mapped_column(String(256), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
