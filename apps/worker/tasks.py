import asyncio
from math import ceil
from pathlib import Path

import httpx
from sqlalchemy import select

from apps.application.commands.finalize_investigation import (
    FinalizationBusyError,
    FinalizeInvestigationUseCase,
)
from apps.enrichment_runtime import create_configured_enrichment_runtime
from apps.investigation_runtime import create_configured_investigation_runtime
from apps.model_runtime import create_recorded_model_provider, record_model_provider
from apps.runtime_artifacts import create_runtime_artifact_service
from apps.task_admission import create_task_contract_service
from apps.watch_runtime import RuntimeWatchWakeAdmission
from apps.worker.celery_app import celery_app
from packages.enrichment.normative.service import NormativeKnowledgeService
from packages.enrichment.providers.factory import create_configured_ai_provider
from packages.enrichment.runtime.state_models import EnrichmentAttemptModel
from packages.enrichment.runtime.tasks import ensure_background_vulnerability_enrichment_run
from packages.enrichment.semantic.documents import DocumentSemanticService
from packages.intelligence.projections.service import CurrentProjectionService
from packages.intelligence.retrieval.indexing import DocumentIndexService
from packages.intelligence.storage.document_models import DocumentRevisionModel
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.factory import create_artifact_store
from packages.investigation.runtime.watch import WatchWakeService
from packages.investigation.state.world_change import KnowledgeChangeNotice, WorldChangeService
from packages.monitoring.runtime import execute_collection_run
from packages.runtime.execution.service import ExecutionRunService
from packages.runtime.model import ModelRetryPolicy
from packages.runtime.policy.loader import load_runtime_policy
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.sources.registry.loader import load_source_definitions
from packages.task_runtime.contracts.models import TERMINAL_TASK_RUN_STATUSES, TaskRunStatus
from packages.task_runtime.scheduler import QueuedRoleExecutor
from packages.task_runtime.storage.service import get_task_run


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


@celery_app.task(name="secfusion.enrichment.run")
def run_enrichment(run_id: str) -> str:
    return asyncio.run(_run_enrichment(run_id))


@celery_app.task(name="secfusion.indexing.document_revision")
def index_document_revision(payload: dict[str, object]) -> int:
    return asyncio.run(_index_document_revision(payload))


@celery_app.task(
    name="secfusion.investigation.run",
    autoretry_for=(FinalizationBusyError,),
    default_retry_delay=5,
    retry_kwargs={"max_retries": ceil((get_settings().model_timeout_seconds + 30) / 5) + 2},
)
def run_investigation(run_id: str) -> str:
    return asyncio.run(_run_investigation(run_id))


async def _run_investigation(run_id: str) -> str:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    execution_service = ExecutionRunService()
    try:

        async def execute_role(claimed_run_id: str) -> object:
            async with factory() as session, session.begin():
                claimed = await get_task_run(session, claimed_run_id)
                await execution_service.start(session, claimed.execution_envelope_ref)
            try:
                async with httpx.AsyncClient(timeout=settings.model_timeout_seconds) as client:
                    runtime_artifacts = await create_runtime_artifact_service(settings)
                    runtime = create_configured_investigation_runtime(
                        settings,
                        factory,
                        client,
                        execution_service=execution_service,
                        artifact_service=runtime_artifacts,
                    )
                    outcome = await runtime.run(claimed_run_id)
            except Exception as exc:
                async with factory() as session, session.begin():
                    claimed = await get_task_run(session, claimed_run_id)
                    await execution_service.finish(
                        session,
                        claimed.execution_envelope_ref,
                        status="failed",
                        stop_reason=f"investigation_runtime_error:{type(exc).__name__}",
                    )
                raise
            if outcome.run_status in {
                TaskRunStatus.COMPLETED,
                TaskRunStatus.FAILED,
                TaskRunStatus.CANCELLED,
                TaskRunStatus.TIMED_OUT,
                TaskRunStatus.BLOCKED,
            }:
                async with factory() as session, session.begin():
                    claimed = await get_task_run(session, claimed_run_id)
                    await execution_service.finish(
                        session,
                        claimed.execution_envelope_ref,
                        status=outcome.run_status.value,
                        stop_reason=outcome.result.stop_reason,
                    )
            return outcome

        result = await QueuedRoleExecutor(
            factory,
            {"InvestigationRole": execute_role},
            stream_name=settings.task_event_stream_name,
        ).execute(run_id)
        if result.final_status is TaskRunStatus.COMPLETED:
            async with httpx.AsyncClient(timeout=settings.model_timeout_seconds) as client:
                artifacts = await create_runtime_artifact_service(settings)
                provider = create_recorded_model_provider(
                    settings,
                    factory,
                    client,
                    artifact_service=artifacts,
                )
                if provider is not None:
                    await FinalizeInvestigationUseCase(factory, settings, provider).execute(run_id)
        return result.final_status.value
    finally:
        await engine.dispose()


async def _run_enrichment(run_id: str) -> str:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    execution_service = ExecutionRunService()
    artifact_store = create_artifact_store(settings)
    await artifact_store.ensure_bucket()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            runtime = create_configured_enrichment_runtime(
                settings,
                factory,
                client,
                artifact_store,
            )

            async def execute_role(claimed_run_id: str) -> object:
                async with factory() as session, session.begin():
                    claimed = await get_task_run(session, claimed_run_id)
                    await execution_service.start(session, claimed.execution_envelope_ref)
                try:
                    outcome = await runtime.run(claimed_run_id)
                except Exception as exc:
                    async with factory() as session, session.begin():
                        claimed = await get_task_run(session, claimed_run_id)
                        await execution_service.finish(
                            session,
                            claimed.execution_envelope_ref,
                            status="failed",
                            stop_reason=f"enrichment_runtime_error:{type(exc).__name__}",
                        )
                    raise
                if outcome.run_status in TERMINAL_TASK_RUN_STATUSES:
                    async with factory() as session, session.begin():
                        claimed = await get_task_run(session, claimed_run_id)
                        await execution_service.finish(
                            session,
                            claimed.execution_envelope_ref,
                            status=outcome.run_status.value,
                            stop_reason=outcome.result.stop_reason,
                        )
                return outcome

            result = await QueuedRoleExecutor(
                factory,
                {"EnrichmentRole": execute_role},
                stream_name=settings.task_event_stream_name,
            ).execute(run_id)
            return result.final_status.value
    finally:
        await engine.dispose()


async def _rebuild_knowledge_projections(payload: dict[str, object]) -> int:
    revision = payload.get("revision")
    object_ids = payload.get("object_ids")
    claim_ids = payload.get("claim_ids", [])
    relation_ids = payload.get("relation_ids", [])
    if not isinstance(revision, int) or not isinstance(object_ids, list):
        raise ValueError("knowledge.changed payload requires revision and object_ids")
    if not isinstance(claim_ids, list) or not isinstance(relation_ids, list):
        raise ValueError("knowledge.changed claim_ids/relation_ids must be lists")
    normalized_ids = [item for item in object_ids if isinstance(item, str)]
    normalized_claim_ids = [item for item in claim_ids if isinstance(item, str)]
    normalized_relation_ids = [item for item in relation_ids if isinstance(item, str)]
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    service = CurrentProjectionService()
    watch_policy = load_runtime_policy(settings.runtime_policy_path)
    watch_wake = WatchWakeService(
        admission_port=RuntimeWatchWakeAdmission(watch_policy),
        stream_name=settings.task_event_stream_name,
    )
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
            impacts = await WorldChangeService().process(
                session,
                KnowledgeChangeNotice(
                    revision=revision,
                    object_ids=normalized_ids,
                    claim_ids=normalized_claim_ids,
                    relation_ids=normalized_relation_ids,
                ),
            )
            for impact in impacts:
                await watch_wake.spawn_for_world_change(
                    session,
                    impact=impact,
                    trigger_ref=f"knowledge-revision:{revision}",
                )
        return changed
    finally:
        await engine.dispose()


async def _enrich_vulnerability(payload: dict[str, object]) -> int:
    cve_id = payload.get("cve_id")
    object_id = payload.get("object_id")
    trigger_ref = payload.get("trigger_ref") or payload.get("parent_run_id")
    if not isinstance(cve_id, str):
        raise ValueError("enrichment.requested payload requires cve_id")
    if not isinstance(object_id, str) or not object_id:
        raise ValueError("enrichment.requested payload requires object_id")
    if not isinstance(trigger_ref, str) or not trigger_ref:
        raise ValueError("enrichment.requested payload requires trigger_ref provenance")

    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    artifact_store = create_artifact_store(settings)
    task_admission = create_task_contract_service(load_runtime_policy(settings.runtime_policy_path))
    await artifact_store.ensure_bucket()
    try:
        async with factory() as session, session.begin():
            task_run_id = await ensure_background_vulnerability_enrichment_run(
                session,
                object_id=object_id,
                cve_id=cve_id,
                trigger_ref=trigger_ref,
                stream_name=settings.task_event_stream_name,
                task_contract_service=task_admission,
            )
            task_run = await get_task_run(session, task_run_id)
            if task_run.status in TERMINAL_TASK_RUN_STATUSES:
                attempted = set(
                    await session.scalars(
                        select(EnrichmentAttemptModel.operator_id).where(
                            EnrichmentAttemptModel.task_run_id == task_run_id
                        )
                    )
                )
                return len(attempted)

        async with httpx.AsyncClient(timeout=30.0) as client:
            outcome = await create_configured_enrichment_runtime(
                settings,
                factory,
                client,
                artifact_store,
            ).run(task_run_id)
            return len(outcome.result.attempted_operators)
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
                recorded_provider = record_model_provider(
                    factory,
                    provider,
                    retry_policy=ModelRetryPolicy(
                        max_attempts=settings.model_max_attempts,
                        base_delay_seconds=settings.model_retry_base_seconds,
                        max_delay_seconds=settings.model_retry_max_seconds,
                    ),
                )
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
                        await NormativeKnowledgeService(recorded_provider).extract(
                            session,
                            source=source,
                            document_revision_id=document_revision_id,
                        )
                if source.source_class != "normative_knowledge":
                    semantic = DocumentSemanticService(recorded_provider)
                    async with factory() as session:
                        prepared = await semantic.prepare(
                            session,
                            source=source,
                            document_revision_id=document_revision_id,
                        )
                    inferred = await semantic.infer(prepared, source=source)
                    async with factory() as session, session.begin():
                        await semantic.commit(
                            session,
                            source=source,
                            prepared=prepared,
                            inferred=inferred,
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
