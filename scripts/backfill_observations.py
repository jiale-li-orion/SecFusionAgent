from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from redis.asyncio import Redis
from sqlalchemy import select

from packages.enrichment.runtime.post_ingress import ObservationProcessingRuntime
from packages.intelligence.incident.correlator import IncidentCorrelator
from packages.intelligence.incident.factory import create_incident_signal_extractors
from packages.intelligence.incident.ingress import IncidentSignalIngress
from packages.intelligence.incident.promotion import (
    IncidentPromotionPolicy,
    IncidentPromotionService,
)
from packages.intelligence.incident.redis import RedisIncidentSignalStore
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.retrieval.indexing import DocumentIndexService
from packages.intelligence.storage.document_models import DocumentChunkModel, DocumentRevisionModel
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.factory import create_s3_artifact_store
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.sources.contracts import RetentionMode
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions


def _priority(retention_mode: RetentionMode) -> int:
    return {
        RetentionMode.HOT_WINDOW: 0,
        RetentionMode.SELECTIVE_INDEX: 1,
        RetentionMode.DURABLE_MANAGED: 1,
        RetentionMode.TIME_BOUNDED: 2,
        RetentionMode.INCIDENT_SIGNAL: 3,
    }[retention_mode]


async def _index_pending_documents(factory) -> int:
    async with factory() as session:
        pending = list(
            await session.scalars(
                select(DocumentRevisionModel.document_revision_id)
                .join(
                    DocumentChunkModel,
                    DocumentChunkModel.document_revision_id
                    == DocumentRevisionModel.document_revision_id,
                )
                .where(DocumentChunkModel.index_status == "pending")
                .distinct()
            )
        )
    indexed = 0
    service = DocumentIndexService()
    for revision_id in pending:
        async with factory() as session, session.begin():
            result = await service.build_lexical_index(session, document_revision_id=revision_id)
            indexed += len(result.indexed_chunk_ids)
    return indexed


async def _run(source_id: str | None, observation_id: str | None, index_documents: bool) -> None:
    settings = get_settings()
    definitions = load_source_definitions(Path(settings.source_registry_path))
    sources = {item.source_id: item for item in definitions}
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    store = create_s3_artifact_store(settings)
    await store.ensure_bucket()
    redis = Redis.from_url(settings.redis_hot_cache_url)
    incident_store = RedisIncidentSignalStore(redis)
    incident_ingress = IncidentSignalIngress(
        IncidentCorrelator(
            incident_store,
            ttl_seconds=settings.incident_signal_ttl_seconds,
        ),
        create_incident_signal_extractors(),
    )
    incident_promotion = IncidentPromotionService(
        incident_store,
        # Promotion may replay an already-fixed signal Observation; EvidenceIngress
        # absorbs the duplicate and preserves the same evidence identity.
        EvidenceIngress(store),
        IncidentPromotionPolicy(),
    )
    runtime = ObservationProcessingRuntime(
        store,
        incident_ingress=incident_ingress,
        incident_promotion=incident_promotion,
        source_definitions=sources,
    )
    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, definitions)
        async with factory() as session:
            query = select(ObservationModel)
            if source_id is not None:
                query = query.where(ObservationModel.source_id == source_id)
            if observation_id is not None:
                query = query.where(ObservationModel.observation_id == observation_id)
            rows = list(await session.scalars(query.order_by(ObservationModel.created_at)))

        rows.sort(
            key=lambda row: (
                _priority(sources[row.source_id].retention_mode),
                row.created_at,
                row.observation_id,
            )
        )
        counts: dict[str, int] = {}
        for row in rows:
            source = sources.get(row.source_id)
            if source is None:
                print(f"{row.observation_id} {row.source_id} blocked source_definition_missing")
                counts["blocked"] = counts.get("blocked", 0) + 1
                continue
            async with factory() as session, session.begin():
                result = await runtime.process(session, source, row.observation_id)
            counts[result.status.value] = counts.get(result.status.value, 0) + 1
            detail = f" detail={result.detail}" if result.detail else ""
            print(
                f"{result.observation_id} {result.source_id} "
                f"{result.handler} {result.status.value} "
                f"metadata_complete={result.metadata_complete}{detail}"
            )
        if index_documents:
            indexed = await _index_pending_documents(factory)
            print(f"lexical_indexed_chunks={indexed}")
        print("summary", " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    finally:
        await redis.aclose()
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay durable Observations through their M3 post-ingress owner"
    )
    parser.add_argument("--source-id")
    parser.add_argument("--observation-id")
    parser.add_argument("--index-documents", action="store_true")
    args = parser.parse_args()
    asyncio.run(_run(args.source_id, args.observation_id, args.index_documents))


if __name__ == "__main__":
    main()
