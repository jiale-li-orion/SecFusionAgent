from __future__ import annotations

from packages.intelligence.incident.contracts import (
    IncidentSignalExtractor,
    IncidentSignalResult,
)
from packages.intelligence.incident.correlator import IncidentCorrelator
from packages.sources.contracts import IngestEnvelope, RetentionMode, SourceDefinition


class IncidentSignalIngress:
    def __init__(
        self,
        correlator: IncidentCorrelator,
        extractors: dict[str, IncidentSignalExtractor],
    ) -> None:
        self._correlator = correlator
        self._extractors = extractors

    async def accept(
        self,
        source: SourceDefinition,
        envelope: IngestEnvelope,
    ) -> IncidentSignalResult:
        if source.retention_mode is not RetentionMode.INCIDENT_SIGNAL:
            raise ValueError(f"source {source.source_id} is not configured for incident_signal")
        extractor = self._extractors.get(source.adapter_type)
        if extractor is None:
            raise ValueError(f"no incident extractor for adapter_type={source.adapter_type}")
        signal = extractor.extract(source, envelope)
        return await self._correlator.accept(signal)
