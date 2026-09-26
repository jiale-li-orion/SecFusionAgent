from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.ingestion.evidence import EvidenceIngress, ObservationAck
from packages.monitoring.acquisition.service import AcquisitionService
from packages.sources.contracts import (
    AcquisitionTrigger,
    IngestEnvelope,
    QuerySpec,
    RetentionMode,
    SourceAdapter,
    SourceDefinition,
)


class TimeBoundedQueryResult(BaseModel):
    envelope: IngestEnvelope


class TimeBoundedEvidenceService:
    """Query external providers without durable promotion until the result is consumed."""

    def __init__(self, acquisition: AcquisitionService, evidence_ingress: EvidenceIngress) -> None:
        self._acquisition = acquisition
        self._evidence_ingress = evidence_ingress

    async def query(
        self,
        source: SourceDefinition,
        adapter: SourceAdapter,
        spec: QuerySpec,
        *,
        parent_run_id: str | None,
        trigger: AcquisitionTrigger = AcquisitionTrigger.INVESTIGATION,
    ) -> list[TimeBoundedQueryResult]:
        if source.retention_mode is not RetentionMode.TIME_BOUNDED:
            raise ValueError(
                f"time-bounded query service cannot own {source.retention_mode.value} source"
            )
        envelopes = await self._acquisition.query(
            source,
            adapter,
            spec,
            parent_run_id=parent_run_id,
            trigger=trigger,
        )
        return [TimeBoundedQueryResult(envelope=envelope) for envelope in envelopes]

    async def promote(
        self,
        session: AsyncSession,
        source: SourceDefinition,
        result: TimeBoundedQueryResult,
    ) -> ObservationAck:
        if source.retention_mode is not RetentionMode.TIME_BOUNDED:
            raise ValueError("only time-bounded query results use explicit query-result promotion")
        if result.envelope.source_id != source.source_id:
            raise ValueError("source does not own query result")
        return await self._evidence_ingress.accept(session, source, result.envelope)
