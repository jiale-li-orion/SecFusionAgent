import asyncio
from pathlib import Path

import httpx

from apps.worker.celery_app import celery_app
from packages.enrichment.planner import VulnerabilityEnrichmentPlanner
from packages.enrichment.service import VulnerabilityEnrichmentService
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.knowledge.write import EvidenceBackedKnowledgeWriter
from packages.intelligence.projections.service import CurrentProjectionService
from packages.intelligence.storage.factory import create_s3_artifact_store
from packages.monitoring.acquisition.service import AcquisitionService
from packages.monitoring.runtime import execute_collection_run
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.sources.adapters.factory import create_source_adapter
from packages.sources.registry.loader import load_source_definitions


@celery_app.task(name="secfusion.collection.run")
def run_collection(run_id: str) -> str:
    return asyncio.run(execute_collection_run(run_id, get_settings()))


@celery_app.task(name="secfusion.projection.knowledge_changed")
def rebuild_knowledge_projections(payload: dict[str, object]) -> int:
    return asyncio.run(_rebuild_knowledge_projections(payload))


@celery_app.task(name="secfusion.projection.incident_changed")
def rebuild_incident_projection(payload: dict[str, object]) -> int:
    return asyncio.run(_rebuild_incident_projection(payload))


@celery_app.task(name="secfusion.enrichment.vulnerability")
def enrich_vulnerability(payload: dict[str, object]) -> int:
    return asyncio.run(_enrich_vulnerability(payload))


async def _rebuild_knowledge_projections(payload: dict[str, object]) -> int:
    revision = payload.get("revision")
    object_ids = payload.get("object_ids")
    if not isinstance(revision, int) or not isinstance(object_ids, list):
        raise ValueError("knowledge.changed payload requires revision and object_ids")
    normalized_ids = [item for item in object_ids if isinstance(item, str)]
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    service = CurrentProjectionService()
    changed = 0
    try:
        async with factory() as session, session.begin():
            for object_id in normalized_ids:
                result = await service.rebuild_knowledge_object(
                    session,
                    object_id=object_id,
                    upstream_revision=revision,
                )
                if result is not None and result.changed:
                    changed += 1
        return changed
    finally:
        await engine.dispose()


async def _enrich_vulnerability(payload: dict[str, object]) -> int:
    cve_id = payload.get("cve_id")
    parent_run_id = payload.get("parent_run_id")
    if not isinstance(cve_id, str):
        raise ValueError("enrichment.requested payload requires cve_id")
    if parent_run_id is not None and not isinstance(parent_run_id, str):
        raise ValueError("enrichment.requested parent_run_id must be a string")

    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    artifact_store = create_s3_artifact_store(settings)
    await artifact_store.ensure_bucket()
    source_definitions = {
        item.source_id: item
        for item in load_source_definitions(Path(settings.source_registry_path))
    }
    provider_ids = ["cisa-kev", "github-global-advisories", "osv-vulnerabilities"]
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            adapters = {
                source_id: create_source_adapter(
                    source_definitions[source_id],
                    client,
                    settings,
                )
                for source_id in provider_ids
            }
            service = VulnerabilityEnrichmentService(
                factory,
                AcquisitionService(factory),
                EvidenceIngress(artifact_store),
                EvidenceBackedKnowledgeWriter(),
                VulnerabilityEnrichmentPlanner(),
                source_definitions,
                adapters,
            )
            results = await service.enrich_cve(
                cve_id,
                parent_run_id=parent_run_id,
            )
            return len(results)
    finally:
        await engine.dispose()


async def _rebuild_incident_projection(payload: dict[str, object]) -> int:
    revision = payload.get("revision")
    incident_id = payload.get("incident_id")
    if not isinstance(revision, int) or not isinstance(incident_id, str):
        raise ValueError("incident.changed payload requires revision and incident_id")
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    service = CurrentProjectionService()
    try:
        async with factory() as session, session.begin():
            result = await service.rebuild_incident(
                session,
                incident_id=incident_id,
                upstream_revision=revision,
            )
        return int(result is not None and result.changed)
    finally:
        await engine.dispose()
