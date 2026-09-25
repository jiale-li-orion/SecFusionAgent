from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.sources.contracts import SourceDefinition
from packages.sources.storage.models import SourceModel


async def sync_source_definitions(
    session: AsyncSession,
    definitions: list[SourceDefinition],
) -> list[str]:
    """Synchronize version-controlled source definitions into runtime state.

    Runtime cursor/health is intentionally kept in `source_state`; syncing a
    definition never rewrites that state.
    """

    now = datetime.now(UTC)
    for definition in definitions:
        row = await session.get(SourceModel, definition.source_id)
        payload = definition.model_dump(mode="json")
        definition_hash = sha256(
            definition.model_dump_json(exclude_none=False).encode("utf-8")
        ).hexdigest()
        values = {
            **payload,
            "source_role": definition.source_role.value,
            "retention_mode": definition.retention_mode.value,
            "definition_hash": definition_hash,
            "managed_by": "config",
            "updated_at": now,
            "enabled": True,
        }
        if row is None:
            session.add(SourceModel(**values))
        else:
            for key, value in values.items():
                setattr(row, key, value)

    configured = {definition.source_id for definition in definitions}
    result = await session.scalars(select(SourceModel).where(SourceModel.managed_by == "config"))
    for row in result:
        if row.source_id not in configured:
            row.enabled = False
            row.updated_at = now
    return sorted(configured)
