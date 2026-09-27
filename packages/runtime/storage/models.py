from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base


class ExecutionRunModel(Base):
    __tablename__ = "execution_runs"

    execution_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    parent_execution_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("execution_runs.execution_id", ondelete="RESTRICT"), index=True
    )
    task_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("task_runs.run_id", ondelete="CASCADE"), index=True
    )
    envelope_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    stop_reason: Mapped[str | None] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class BudgetAccountModel(Base):
    __tablename__ = "budget_accounts"

    account_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    parent_account_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("budget_accounts.account_id", ondelete="RESTRICT"), index=True
    )
    task_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("task_runs.run_id", ondelete="SET NULL"), index=True
    )
    limits: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BudgetReservationModel(Base):
    __tablename__ = "budget_reservations"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "reservation_group_id",
            "resource_type",
            name="uq_budget_reservation_group_resource",
        ),
    )

    reservation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    reservation_group_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("budget_accounts.account_id", ondelete="CASCADE"), index=True
    )
    child_account_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("budget_accounts.account_id", ondelete="RESTRICT"), index=True
    )
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    amount_reserved: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    amount_committed: Mapped[Decimal] = mapped_column(
        Numeric(24, 6), nullable=False, default=Decimal("0")
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CapabilityInvocationModel(Base):
    __tablename__ = "capability_invocations"
    __table_args__ = (
        UniqueConstraint("task_run_id", "request_id", name="uq_capability_invocation_task_request"),
    )

    invocation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("task_runs.run_id", ondelete="CASCADE"), index=True
    )
    case_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("investigation_cases.case_id", ondelete="SET NULL"), index=True
    )
    request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    capability_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    contract_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    binding_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    binding_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_impl_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    implementation_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    request_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    plan_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    policy_decision_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    policy_decision_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    arguments_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    result_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    observation_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    failure_code: Mapped[str | None] = mapped_column(String(128), index=True)
    failure_detail: Mapped[str | None] = mapped_column(Text)


class RuntimeArtifactModel(Base):
    __tablename__ = "runtime_artifacts"
    __table_args__ = (
        UniqueConstraint(
            "execution_id",
            "logical_name",
            "content_hash",
            name="uq_runtime_artifact_execution_name_hash",
        ),
    )

    artifact_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    execution_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("execution_runs.execution_id", ondelete="CASCADE"), index=True
    )
    producer_kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    producer_ref: Mapped[str | None] = mapped_column(String(256), index=True)
    logical_name: Mapped[str] = mapped_column(String(256), nullable=False)
    media_type: Mapped[str] = mapped_column(String(128), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    trust_class: Mapped[str] = mapped_column(
        String(64), nullable=False, default="execution_untrusted", index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SandboxInstanceModel(Base):
    __tablename__ = "sandbox_instances"
    __table_args__ = (
        UniqueConstraint("execution_id", "request_id", name="uq_sandbox_instance_request"),
    )

    instance_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    execution_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("execution_runs.execution_id", ondelete="CASCADE"), index=True
    )
    task_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("task_runs.run_id", ondelete="CASCADE"), index=True
    )
    request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    profile_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    backend: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    backend_handle_ref: Mapped[str | None] = mapped_column(String(256))
    request_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    lease_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    policy_decision_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    policy_decision_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    destroyed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    failure_code: Mapped[str | None] = mapped_column(String(128), index=True)


class SandboxExecutionModel(Base):
    __tablename__ = "sandbox_executions"
    __table_args__ = (
        UniqueConstraint("instance_id", "operation_id", name="uq_sandbox_execution_operation"),
    )

    sandbox_execution_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    instance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sandbox_instances.instance_id", ondelete="CASCADE"), index=True
    )
    operation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    request_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    result_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    timeout_seconds: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    failure_code: Mapped[str | None] = mapped_column(String(128), index=True)
