import asyncio
from pathlib import Path

import httpx

from apps.worker.celery_app import celery_app
from packages.enrichment.graph.fix_boundary import DeterministicFixBoundaryService
from packages.enrichment.graph.github_references import GitHubReferenceGraphService
from packages.enrichment.normative.service import NormativeKnowledgeService
from packages.enrichment.planner import VulnerabilityEnrichmentPlanner
from packages.enrichment.providers.factory import create_configured_ai_provider
from packages.enrichment.semantic.documents import DocumentSemanticService
from packages.enrichment.service import VulnerabilityEnrichmentService
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.knowledge.write import EvidenceBackedKnowledgeWriter
from packages.intelligence.projections.service import CurrentProjectionService
from packages.intelligence.retrieval.indexing import DocumentIndexService
from packages.intelligence.storage.document_models import DocumentRevisionModel
from packages.intelligence.storage.evidence_models import ObservationModel
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


@celery_app.task(name="secfusion.indexing.document_revision")
def index_document_revision(payload: dict[str, object]) -> int:
    return asyncio.run(_index_document_revision(payload))


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
                results = await service.rebuild_knowledge_object_views(
                    session,
                    object_id=object_id,
                    upstream_revision=revision,
                )
                changed += sum(1 for result in results if result.changed)
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
    provider_ids = [
        "cisa-kev",
        "github-global-advisories",
        "osv-vulnerabilities",
        "github-target-repos",
    ]
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
            graph_results = await GitHubReferenceGraphService(
                factory,
                AcquisitionService(factory),
                EvidenceIngress(artifact_store),
                EvidenceBackedKnowledgeWriter(),
                source_definitions,
                adapters,
            ).enrich_cve(
                cve_id,
                parent_run_id=parent_run_id,
            )
            fix_results = await DeterministicFixBoundaryService(
                factory,
                AcquisitionService(factory),
                EvidenceIngress(artifact_store),
                EvidenceBackedKnowledgeWriter(),
                source_definitions,
                adapters,
            ).enrich_cve(
                cve_id,
                parent_run_id=parent_run_id,
            )
            return len(results) + len(graph_results) + len(fix_results)
    finally:
        await engine.dispose()


async def _index_document_revision(payload: dict[str, object]) -> int:
    document_revision_id = payload.get("document_revision_id")
    if not isinstance(document_revision_id, str) or not document_revision_id:
        raise ValueError("document.index.requested payload requires document_revision_id")
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session, session.begin():
            lexical = await DocumentIndexService().build_lexical_index(
                session, document_revision_id=document_revision_id
            )
        if not settings.model_base_url:
            return len(lexical.indexed_chunk_ids)

        async with httpx.AsyncClient(timeout=settings.model_timeout_seconds) as client:
            provider = create_configured_ai_provider(settings, client)
            if provider is None:
                return len(lexical.indexed_chunk_ids)

            if settings.embedding_model_name:
                async with factory() as session, session.begin():
                    await DocumentIndexService().build_dense_index(
                        session,
                        document_revision_id=document_revision_id,
                        provider=provider,
                    )

            if settings.model_name:
                async with factory() as session:
                    revision = await session.get(DocumentRevisionModel, document_revision_id)
                    if revision is None:
                        raise LookupError(f"document revision not found: {document_revision_id}")
                    observation = await session.get(ObservationModel, revision.observation_id)
                    if observation is None:
                        raise RuntimeError("document revision exists without observation")
                    source_id = observation.source_id
                source_definitions = {
                    item.source_id: item
                    for item in load_source_definitions(Path(settings.source_registry_path))
                }
                source = source_definitions.get(source_id)
                if source is None:
                    raise LookupError(f"source definition not found: {source_id}")
                async with factory() as session, session.begin():
                    if source.source_class == "normative_knowledge":
                        await NormativeKnowledgeService(provider).extract(
                            session,
                            source=source,
                            document_revision_id=document_revision_id,
                        )
                    else:
                        await DocumentSemanticService(provider).extract(
                            session,
                            source=source,
                            document_revision_id=document_revision_id,
                        )
        return len(lexical.indexed_chunk_ids)
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
