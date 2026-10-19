from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from hashlib import sha256

from pydantic import JsonValue
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.intelligence.hot_cache.contracts import HotNormalizationResult
from packages.monitoring.storage.models import HotAdmissionReceiptModel
from packages.sources.contracts import IngestEnvelope, SourceDefinition


class HotAdmissionReceiptService:
    """Commit each completed hot admission independently of its run's outcome.

    The unique receipt digest and atomic conflict-ignore preserve the first
    committed receipt across concurrent writers and replay. No pre-deployment
    first-seen time is inferred, and a later replay cannot rewrite timestamps.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def record(
        self,
        source: SourceDefinition,
        envelope: IngestEnvelope,
        result: HotNormalizationResult,
        *,
        cursor_in: Mapping[str, JsonValue],
        cursor_out: Mapping[str, JsonValue],
    ) -> None:
        if (
            source.source_id != envelope.source_id
            or result.source_id != envelope.source_id
            or result.external_object_id != envelope.external_object_id
            or result.external_revision != envelope.external_revision
        ):
            raise ValueError("hot admission result does not match the source envelope")
        identity = (
            ["revision", envelope.external_revision]
            if envelope.external_revision
            else ["content_hash", envelope.content_hash]
        )
        receipt_id = sha256(
            json.dumps(
                [source.source_id, envelope.external_object_id, identity],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        values = {
            "receipt_id": receipt_id,
            "source_id": source.source_id,
            "external_object_id": envelope.external_object_id,
            "external_revision": envelope.external_revision,
            "content_hash": envelope.content_hash,
            "published_at": _utc(envelope.published_at),
            "updated_at": _utc(envelope.updated_at),
            "fetched_at": _utc(envelope.observed_at),
            "available_at": _utc(result.available_at),
            "acquisition_run_id": envelope.acquisition_run_id,
            "trigger": envelope.trigger.value,
            # Match the registry's SourceModel.definition_hash contract.
            "source_definition_hash": sha256(
                source.model_dump_json(exclude_none=False).encode("utf-8")
            ).hexdigest(),
            "input_backfill_pending": cursor_in.get("backfill_pending") is True,
            "output_backfill_pending": cursor_out.get("backfill_pending") is True,
        }
        async with self._session_factory() as session, session.begin():
            dialect = session.get_bind().dialect.name
            if dialect not in {"postgresql", "sqlite"}:
                raise ValueError(f"unsupported hot admission storage dialect: {dialect}")
            statement = (
                pg_insert(HotAdmissionReceiptModel)
                if dialect == "postgresql"
                else sqlite_insert(HotAdmissionReceiptModel)
            ).values(**values)
            await session.execute(statement.on_conflict_do_nothing(index_elements=["receipt_id"]))


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("hot admission timestamps must include a timezone")
    return value.astimezone(UTC)
