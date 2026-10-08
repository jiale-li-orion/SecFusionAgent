"""Durable replay identity for Product commands with atomic domain writes."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from apps.application.errors import ApplicationError
from packages.shared.db import Base


class IdempotencyConflictError(ApplicationError):
    code = "idempotency_conflict"


class ProductCommandRecordModel(Base):
    __tablename__ = "product_command_records"

    principal_scope: Mapped[str] = mapped_column(String(256), primary_key=True)
    operation: Mapped[str] = mapped_column(String(128), primary_key=True)
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    response_ref: Mapped[str | None] = mapped_column(String(256))
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def command_digest(payload: dict[str, Any]) -> str:
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


async def claim_command(
    session: AsyncSession,
    *,
    principal: str,
    operation: str,
    key: str | None,
    digest: str,
) -> tuple[ProductCommandRecordModel | None, bool]:
    if key is None:
        return None, False
    if not key or len(key) > 128:
        raise ValueError("Idempotency-Key must contain 1-128 characters")
    identity = (principal, operation, key)
    existing = await session.get(ProductCommandRecordModel, identity)
    if existing is None:
        try:
            async with session.begin_nested():
                record = ProductCommandRecordModel(
                    principal_scope=principal,
                    operation=operation,
                    key=key,
                    request_digest=digest,
                    response_ref=None,
                    response_payload=None,
                    status="pending",
                    created_at=datetime.now(UTC),
                )
                session.add(record)
                await session.flush()
            return record, False
        except IntegrityError:
            existing = await session.get(
                ProductCommandRecordModel, identity, populate_existing=True
            )
    if existing is None:
        raise IdempotencyConflictError("command is still being admitted")
    if existing.request_digest != digest:
        raise IdempotencyConflictError("Idempotency-Key was used with another request")
    if existing.status == "failed":
        raise IdempotencyConflictError("the original command failed; submit a new command")
    if existing.status != "completed" or not existing.response_ref:
        raise IdempotencyConflictError("command is still in progress")
    return existing, True


def complete_command(
    record: ProductCommandRecordModel | None,
    response_ref: str,
    response_payload: dict[str, Any] | None = None,
) -> None:
    if record is not None:
        record.response_ref = response_ref
        record.response_payload = response_payload
        record.status = "completed"
