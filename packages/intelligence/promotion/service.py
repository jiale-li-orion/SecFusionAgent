from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.hot_cache.contracts import HotBugCache
from packages.intelligence.ingestion.evidence import EvidenceIngress, ObservationAck
from packages.intelligence.normalization.canonical import (
    DurableNormalizer,
    NormalizationResult,
)
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope, SourceDefinition


class HotRecordMissing(LookupError):
    pass


class PromotionResult(BaseModel):
    observation: ObservationAck
    normalization: NormalizationResult


class PromotionService:
    def __init__(
        self,
        cache: HotBugCache,
        evidence_ingress: EvidenceIngress,
        normalizers: dict[str, DurableNormalizer],
    ) -> None:
        self._cache = cache
        self._evidence_ingress = evidence_ingress
        self._normalizers = normalizers

    async def promote_hot_bug(
        self,
        session: AsyncSession,
        source: SourceDefinition,
        external_object_id: str,
    ) -> PromotionResult:
        record = await self._cache.get(source.source_id, external_object_id)
        if record is None:
            raise HotRecordMissing(
                f"hot record not found for {source.source_id}:{external_object_id}"
            )
        normalizer = self._normalizers.get(source.adapter_type)
        if normalizer is None:
            raise ValueError(f"no durable normalizer for adapter_type={source.adapter_type}")

        await self._cache.pin(source.source_id, external_object_id)
        try:
            envelope = IngestEnvelope.for_json_payload(
                acquisition_run_id=record.acquisition_run_id,
                trigger=AcquisitionTrigger.PROMOTION,
                source_id=record.source_id,
                external_object_id=record.external_object_id,
                payload=record.raw_payload,
                canonical_url=record.canonical_url,
                published_at=record.published_at,
                updated_at=record.updated_at,
                external_revision=record.external_revision,
                request_metadata={"promoted_from": record.cache_key},
                observed_at=record.fetched_at,
            )
            if envelope.content_hash != record.content_hash:
                raise RuntimeError("hot record payload hash no longer matches its recorded hash")
            observation = await self._evidence_ingress.accept(session, source, envelope)
            normalization = await normalizer.normalize(session, source, envelope, observation)
            return PromotionResult(observation=observation, normalization=normalization)
        finally:
            await self._cache.unpin(source.source_id, external_object_id)
