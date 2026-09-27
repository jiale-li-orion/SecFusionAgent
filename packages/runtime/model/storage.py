from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base


class ModelRequestModel(Base):
    __tablename__ = "model_requests"

    model_request_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    request_owner_ref: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    execution_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("execution_runs.execution_id", ondelete="SET NULL"), index=True
    )
    task_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("task_runs.run_id", ondelete="SET NULL"), index=True
    )
    case_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("investigation_cases.case_id", ondelete="SET NULL"), index=True
    )
    processing_run_id: Mapped[str | None] = mapped_column(String(128), index=True)
    prompt_assembly_id: Mapped[str | None] = mapped_column(String(128), index=True)
    prompt_revision: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    request_schema_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    request_artifact_ref: Mapped[str | None] = mapped_column(String(256))
    requested_model: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    provider_policy_ref: Mapped[str | None] = mapped_column(String(256))
    budget_ref: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("budget_accounts.account_id", ondelete="SET NULL"), index=True
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class ModelAttemptModel(Base):
    __tablename__ = "model_attempts"
    __table_args__ = (
        UniqueConstraint("model_request_id", "ordinal", name="uq_model_attempt_request_ordinal"),
    )

    model_attempt_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    model_request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("model_requests.model_request_id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    adapter_revision: Mapped[str] = mapped_column(String(128), nullable=False)
    actual_model: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    provider_request_id: Mapped[str | None] = mapped_column(String(256), index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    failure_class: Mapped[str | None] = mapped_column(String(128), index=True)
    failure_detail: Mapped[str | None] = mapped_column(Text)
    response_schema_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    response_artifact_ref: Mapped[str | None] = mapped_column(String(256))
    usage_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    cost_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    cache_usage_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    response_metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(BigInteger)


class PromptAssemblyRecordModel(Base):
    __tablename__ = "prompt_assembly_records"

    assembly_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    assembly_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    execution_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("execution_runs.execution_id", ondelete="CASCADE"), index=True
    )
    task_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("task_runs.run_id", ondelete="CASCADE"), index=True
    )
    task_contract_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    context_manifest_ref: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    context_manifest_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    role_revision: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    platform_invariant_revision: Mapped[str] = mapped_column(String(128), nullable=False)
    execution_profile_revision: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_context_revision: Mapped[str] = mapped_column(String(256), nullable=False)
    state_projection_revision: Mapped[str | None] = mapped_column(String(256))
    percept_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    materialized_skill_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    materialized_capability_view_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    materialized_fragment_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    ordered_fragment_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    materialized_ref_set_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    cache_handle_hints_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    fragment_manifest_json: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    request_artifact_ref: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
