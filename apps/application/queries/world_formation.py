from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.application.queries.world import world_source_names
from apps.application.views.world import WorldFormationView, WorldProcessingView
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import KnowledgeRevisionModel
from packages.intelligence.storage.models import ProcessingRunModel


async def read_world_formation(session: AsyncSession) -> WorldFormationView:
    """Actual processing and linked commits, not an inferred animation queue."""
    names = world_source_names()
    rows = (await session.execute(
        select(ProcessingRunModel, KnowledgeRevisionModel, ObservationModel)
        .outerjoin(KnowledgeRevisionModel,
                   KnowledgeRevisionModel.cause_processing_run_id == ProcessingRunModel.run_id)
        .outerjoin(ObservationModel,
                   ObservationModel.observation_id == KnowledgeRevisionModel.cause_observation_id)
        .where(ProcessingRunModel.processor_type == "enrichment")
        .order_by(ProcessingRunModel.started_at.desc())
        .limit(12)
    )).all()
    running = list(await session.scalars(
        select(ProcessingRunModel).where(
            ProcessingRunModel.status.in_(("running", "started")),
            ProcessingRunModel.processor_type == "enrichment",
        ).order_by(ProcessingRunModel.started_at.desc()).limit(12)
    ))
    seen: set[str] = set()
    items = []
    for process, revision, observation in [*( (p, None, None) for p in running), *rows]:
        if process.run_id in seen:
            continue
        seen.add(process.run_id)
        items.append(WorldProcessingView(
            run_id=process.run_id, processor_name=process.processor_name,
            status=process.status, started_at=process.started_at, finished_at=process.finished_at,
            source_name=names.get(observation.source_id) if observation else None,
            external_object_id=observation.external_object_id if observation else None,
            committed_at=revision.committed_at if revision else None,
            revision=revision.revision if revision else None,
        ))
    return WorldFormationView(generated_at=datetime.now(UTC), processing=items)
