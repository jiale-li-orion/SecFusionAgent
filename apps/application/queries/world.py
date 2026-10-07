from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.application.views.world import (
    WorldKnowledgeChangeListView,
    WorldKnowledgeChangeView,
)
from packages.intelligence.storage.knowledge_models import KnowledgeChangeModel


async def list_world_knowledge_changes(
    session: AsyncSession,
    *,
    limit: int = 12,
) -> WorldKnowledgeChangeListView:
    changes = list(
        await session.scalars(
            select(KnowledgeChangeModel)
            .order_by(
                KnowledgeChangeModel.revision.desc(),
                KnowledgeChangeModel.committed_at.desc(),
            )
            .limit(limit)
        )
    )
    return WorldKnowledgeChangeListView(
        items=[
            WorldKnowledgeChangeView(
                change_id=change.change_id,
                revision=change.revision,
                committed_at=change.committed_at,
                object_ids=_changed_ids(change, "objects"),
                claim_ids=_changed_ids(change, "claims"),
                relation_ids=_changed_ids(change, "relations"),
                cause_processing_run_id=change.cause_processing_run_id,
                cause_observation_id=change.cause_observation_id,
            )
            for change in changes
        ]
    )


def _changed_ids(change: KnowledgeChangeModel, key: str) -> list[str]:
    value = change.changed_ids.get(key, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
