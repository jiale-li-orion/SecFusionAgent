from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.application.intelligence_preferences import object_label
from apps.application.queries.world import world_source_names
from apps.application.views.world import (
    WorldAffectedObjectView,
    WorldFormationView,
    WorldProcessingView,
)
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    KnowledgeChangeModel,
    KnowledgeRevisionModel,
    ObjectModel,
    RelationModel,
)
from packages.intelligence.storage.models import ProcessingRunModel


async def read_world_formation(session: AsyncSession) -> WorldFormationView:
    """Actual processing and exactly linked commits; no association by timestamp."""
    names = world_source_names()
    query = select(ProcessingRunModel).where(ProcessingRunModel.processor_type == "enrichment")
    running = list(
        await session.scalars(
            query.where(ProcessingRunModel.status.in_(("running", "started")))
            .order_by(ProcessingRunModel.started_at.desc(), ProcessingRunModel.run_id)
            .limit(12)
        )
    )
    recent = list(
        await session.scalars(
            query.order_by(ProcessingRunModel.started_at.desc(), ProcessingRunModel.run_id).limit(
                12
            )
        )
    )
    processes = {row.run_id: row for row in [*running, *recent]}
    if not processes:
        return WorldFormationView(generated_at=datetime.now(UTC))

    rows = (
        await session.execute(
            select(KnowledgeRevisionModel, ObservationModel)
            .outerjoin(
                ObservationModel,
                ObservationModel.observation_id == KnowledgeRevisionModel.cause_observation_id,
            )
            .where(KnowledgeRevisionModel.cause_processing_run_id.in_(processes))
            .order_by(KnowledgeRevisionModel.revision.desc())
        )
    ).all()
    revisions_by_run = defaultdict(list)
    for revision, observation in rows:
        revisions_by_run[revision.cause_processing_run_id].append((revision, observation))
    changes = list(
        await session.scalars(
            select(KnowledgeChangeModel).where(
                KnowledgeChangeModel.revision.in_([revision.revision for revision, _ in rows])
            )
        )
    )
    changes_by_revision = defaultdict(list)
    changed_ids: dict[str, set[str]] = {kind: set() for kind in ("objects", "claims", "relations")}
    for change in changes:
        changes_by_revision[change.revision].append(change)
        for kind in changed_ids:
            changed_ids[kind].update(change.changed_ids.get(kind, []))

    # Claims can change an existing object without including it in changed_ids.objects.
    claim_subjects = dict(
        (
            await session.execute(
                select(ClaimModel.claim_id, ClaimModel.subject_id).where(
                    ClaimModel.claim_id.in_(changed_ids["claims"])
                )
            )
        ).all()
    )
    relation_endpoints = {
        relation_id: (source_id, target_id)
        for relation_id, source_id, target_id in (
            await session.execute(
                select(
                    RelationModel.relation_id,
                    RelationModel.source_object_id,
                    RelationModel.target_object_id,
                ).where(RelationModel.relation_id.in_(changed_ids["relations"]))
            )
        ).all()
    }
    object_ids = (
        changed_ids["objects"]
        | set(claim_subjects.values())
        | {endpoint for endpoints in relation_endpoints.values() for endpoint in endpoints}
    )
    objects = {
        obj.object_id: obj
        for obj in await session.scalars(
            select(ObjectModel).where(ObjectModel.object_id.in_(object_ids))
        )
    }
    items = []
    for process in processes.values():
        revisions = revisions_by_run[process.run_id]
        latest_revision, latest_observation = revisions[0] if revisions else (None, None)
        run_changes = [
            change for rev, _ in revisions for change in changes_by_revision[rev.revision]
        ]
        ids = {
            kind: {item for change in run_changes for item in change.changed_ids.get(kind, [])}
            for kind in changed_ids
        }
        affected = (
            ids["objects"]
            | {claim_subjects[claim_id] for claim_id in ids["claims"] if claim_id in claim_subjects}
            | {
                endpoint
                for relation_id in ids["relations"]
                for endpoint in relation_endpoints.get(relation_id, ())
            }
        )
        items.append(
            WorldProcessingView(
                run_id=process.run_id,
                processor_name=process.processor_name,
                status=process.status,
                started_at=process.started_at,
                finished_at=process.finished_at,
                source_name=names.get(latest_observation.source_id) if latest_observation else None,
                external_object_id=latest_observation.external_object_id
                if latest_observation
                else None,
                committed_at=latest_revision.committed_at if latest_revision else None,
                revision=latest_revision.revision if latest_revision else None,
                commit_count=len(revisions),
                change_count=len(run_changes),
                object_count=len(ids["objects"]),
                claim_count=len(ids["claims"]),
                relation_count=len(ids["relations"]),
                commit_status=(
                    "committed"
                    if revisions
                    else "pending"
                    if process.status in ("running", "started")
                    else "no_commit"
                ),
                results_complete=(
                    (bool(revisions) or process.status not in ("running", "started"))
                    and all(changes_by_revision[rev.revision] for rev, _ in revisions)
                ),
                affected_objects=[
                    WorldAffectedObjectView(
                        object_id=object_id,
                        label=object_label(objects[object_id])
                        if object_id in objects
                        else object_id,
                        object_type=objects[object_id].object_type
                        if object_id in objects
                        else None,
                    )
                    for object_id in sorted(affected)
                ],
            )
        )
    return WorldFormationView(generated_at=datetime.now(UTC), processing=items)
