from __future__ import annotations

from pydantic import BaseModel, JsonValue
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.intelligence.incident.contracts import IncidentSignalResult
from packages.intelligence.incident.ingress import IncidentSignalIngress
from packages.intelligence.incident.promotion import (
    IncidentNotPromotable,
    IncidentPromotionResult,
    IncidentPromotionService,
)
from packages.sources.contracts import (
    AcquisitionTrigger,
    SourceAdapter,
    SourceDefinition,
    SourceState,
)


class IncidentCollectionResult(BaseModel):
    source_id: str
    accepted: list[IncidentSignalResult]
    promoted: list[IncidentPromotionResult]
    next_cursor: dict[str, JsonValue]


class IncidentSignalCollector:
    def __init__(
        self,
        adapter: SourceAdapter,
        ingress: IncidentSignalIngress,
        promotion: IncidentPromotionService,
        session_factory: async_sessionmaker[AsyncSession],
        source_definitions: dict[str, SourceDefinition],
    ) -> None:
        self._adapter = adapter
        self._ingress = ingress
        self._promotion = promotion
        self._session_factory = session_factory
        self._source_definitions = source_definitions

    async def collect(
        self,
        source: SourceDefinition,
        state: SourceState,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger = AcquisitionTrigger.SCHEDULED,
    ) -> IncidentCollectionResult:
        batch = await self._adapter.discover(source, state)
        accepted: list[IncidentSignalResult] = []
        promoted: list[IncidentPromotionResult] = []
        promoted_candidates: set[str] = set()
        for ref in batch.items:
            envelope = await self._adapter.fetch(
                source,
                ref,
                acquisition_run_id=acquisition_run_id,
                trigger=trigger,
            )
            result = await self._ingress.accept(source, envelope)
            accepted.append(result)
            if not result.material_change or result.incident_candidate_id in promoted_candidates:
                continue
            try:
                async with self._session_factory() as session, session.begin():
                    promotion = await self._promotion.promote(
                        session,
                        candidate_id=result.incident_candidate_id,
                        sources=self._source_definitions,
                    )
            except IncidentNotPromotable:
                continue
            promoted.append(promotion)
            promoted_candidates.add(result.incident_candidate_id)
        return IncidentCollectionResult(
            source_id=source.source_id,
            accepted=accepted,
            promoted=promoted,
            next_cursor=batch.next_cursor,
        )
