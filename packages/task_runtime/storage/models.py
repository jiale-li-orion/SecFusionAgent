from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base


class TaskContractVersionModel(Base):
    __tablename__ = "task_contract_versions"
    __table_args__ = (
        UniqueConstraint(
            "task_contract_id",
            "contract_revision",
            name="uq_task_contract_revision",
        ),
    )

    task_contract_version_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_contract_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    contract_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    principal: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    on_behalf_of: Mapped[str | None] = mapped_column(String(256), index=True)
    task_kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    effect_ceiling: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_revision: Mapped[str] = mapped_column(String(128), nullable=False)
    contract_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ContextManifestVersionModel(Base):
    __tablename__ = "context_manifest_versions"
    __table_args__ = (
        UniqueConstraint(
            "context_id",
            "context_revision",
            name="uq_context_manifest_revision",
        ),
    )

    context_manifest_version_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    context_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    context_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_context_id: Mapped[str | None] = mapped_column(String(128), index=True)
    task_contract_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("task_contract_versions.task_contract_version_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    role_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    case_ref: Mapped[str | None] = mapped_column(String(256), index=True)
    knowledge_revision: Mapped[int | None] = mapped_column(Integer, index=True)
    manifest_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TaskRunModel(Base):
    __tablename__ = "task_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_contract_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("task_contract_versions.task_contract_version_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    task_contract_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    task_contract_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    context_manifest_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("context_manifest_versions.context_manifest_version_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    context_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    context_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    case_id: Mapped[str | None] = mapped_column(String(36), index=True)
    parent_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("task_runs.run_id", ondelete="SET NULL"),
        index=True,
    )
    role_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    role_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    base_context_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    execution_envelope_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    result_ref: Mapped[str | None] = mapped_column(String(512))
    stop_reason: Mapped[str | None] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class TaskEventModel(Base):
    __tablename__ = "task_events"
    __table_args__ = (
        UniqueConstraint("task_run_id", "seq", name="uq_task_event_seq"),
        UniqueConstraint(
            "task_run_id",
            "idempotency_key",
            name="uq_task_event_idempotency",
        ),
    )

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("task_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_run_id: Mapped[str | None] = mapped_column(String(36), index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    producer: Mapped[str] = mapped_column(String(128), nullable=False)
    base_context_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_ref: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)
    emitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class TaskEventDeliveryModel(Base):
    __tablename__ = "task_event_deliveries"

    event_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("task_events.event_id", ondelete="CASCADE"),
        primary_key=True,
    )
    stream_name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    redis_message_id: Mapped[str | None] = mapped_column(String(128))
    last_error: Mapped[str | None] = mapped_column(Text)
