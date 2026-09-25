from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base


class SourceModel(Base):
    __tablename__ = "sources"

    source_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    adapter_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_class: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    authority_scope: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source_role: Mapped[str] = mapped_column(String(32), nullable=False)
    source_family: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    upstream_source: Mapped[str | None] = mapped_column(String(256))
    access_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    update_semantics: Mapped[str] = mapped_column(String(128), nullable=False)
    discovery_method: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    time_semantics: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    identity_semantics: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    auth_ref: Mapped[str | None] = mapped_column(String(256))
    rate_limit_policy: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    access_rights: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    retention_mode: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    schedule_policy: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    definition_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    managed_by: Mapped[str] = mapped_column(String(32), nullable=False, default="config")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
