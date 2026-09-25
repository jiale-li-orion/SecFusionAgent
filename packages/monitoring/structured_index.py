from __future__ import annotations

from pydantic import BaseModel, JsonValue
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.intelligence.structured.service import StructuredIndexService, StructuredIngestResult
from packages.sources.contracts import (
    AcquisitionTrigger,
    SourceAdapter,
    SourceDefinition,
    SourceState,
)


class StructuredIndexCollectionResult(BaseModel):
    source_id: str
    accepted: list[StructuredIngestResult]
    next_cursor: dict[str, JsonValue]


class StructuredIndexCollector:
    def __init__(
        self,
        adapter: SourceAdapter,
        service: StructuredIndexService,
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
    ) -> StructuredIndexCollectionResult:
        batch = await self._adapter.discover(source, state)
        accepted: list[StructuredIngestResult] = []
        for ref in batch.items:
            envelope = await self._adapter.fetch(
                source,
                ref,
                acquisition_run_id=acquisition_run_id,
                trigger=trigger,
            )
            async with self._session_factory() as session, session.begin():
                accepted.append(await self._service.ingest(session, source, envelope))
        return StructuredIndexCollectionResult(
            source_id=source.source_id,
            accepted=accepted,
            next_cursor=batch.next_cursor,
        )
