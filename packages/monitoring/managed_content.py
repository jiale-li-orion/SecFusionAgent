from __future__ import annotations

import asyncio
from math import isfinite

from pydantic import BaseModel, Field, JsonValue
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.intelligence.documents.service import ManagedDocumentResult, ManagedDocumentService
from packages.sources.contracts import (
    AcquisitionTrigger,
    SourceAdapter,
    SourceDefinition,
    SourceState,
)


class ManagedContentCollectionResult(BaseModel):
    source_id: str
    accepted: list[ManagedDocumentResult]
    next_cursor: dict[str, JsonValue]
    rate_limit_state: dict[str, JsonValue] = Field(default_factory=dict)


class ManagedContentCollector:
    def __init__(
        self,
        adapter: SourceAdapter,
        service: ManagedDocumentService,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._adapter = adapter
        self._service = service
        self._session_factory = session_factory

    async def collect(
        self,
        source: SourceDefinition,
        state: SourceState,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger = AcquisitionTrigger.SCHEDULED,
    ) -> ManagedContentCollectionResult:
        raw_interval = source.rate_limit_policy.get("polite_interval_seconds", 0)
        if isinstance(raw_interval, bool) or not isinstance(raw_interval, (int, float, str)):
            raise ValueError("polite_interval_seconds must be a nonnegative number")
        interval = float(raw_interval)
        if not isfinite(interval) or interval < 0:
            raise ValueError("polite_interval_seconds must be a finite nonnegative number")
        batch = await self._adapter.discover(source, state)
        accepted: list[ManagedDocumentResult] = []
        for index, ref in enumerate(batch.items):
            if index and interval:
                await asyncio.sleep(interval)
            envelope = await self._adapter.fetch(
                source,
                ref,
                acquisition_run_id=acquisition_run_id,
                trigger=trigger,
            )
            async with self._session_factory() as session, session.begin():
                accepted.append(await self._service.ingest(session, source, envelope))
        return ManagedContentCollectionResult(
            source_id=source.source_id,
            accepted=accepted,
            next_cursor=batch.next_cursor,
            rate_limit_state=batch.rate_limit_state,
        )
