from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.knowledge.contracts import EnrichmentMapper
from packages.intelligence.knowledge.write import EvidenceBackedKnowledgeWriter
from packages.intelligence.normalization.canonical import NormalizationResult
from packages.sources.contracts import IngestEnvelope, SourceDefinition


class StructuredIngestResult(BaseModel):
    observation_id: str
    normalization: NormalizationResult
    replay: bool


class StructuredIndexService:
    def __init__(
        self,
        evidence_ingress: EvidenceIngress,
        writer: EvidenceBackedKnowledgeWriter,
        mappers: dict[str, EnrichmentMapper],
    ) -> None:
        self._evidence_ingress = evidence_ingress
        self._writer = writer
        self._mappers = mappers

    async def ingest(
        self,
        session: AsyncSession,
        source: SourceDefinition,
        envelope: IngestEnvelope,
    ) -> StructuredIngestResult:
        mapper = self._mappers.get(source.adapter_type)
        if mapper is None:
            raise ValueError(f"no structured mapper for adapter_type={source.adapter_type}")
        observation = await self._evidence_ingress.accept(session, source, envelope)
        candidate = mapper.map(envelope)
        normalization = await self._writer.apply(
            session,
            source=source,
            observation=observation,
            candidate=candidate,
            processor_name=mapper.PROCESSOR_NAME,
            processor_version=mapper.PROCESSOR_VERSION,
        )
        return StructuredIngestResult(
            observation_id=observation.observation_id,
            normalization=normalization,
            replay=observation.replay,
        )
