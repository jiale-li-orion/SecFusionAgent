from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, cast

from sqlalchemy import text

from apps.runtime_models import register_runtime_models
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory

_COUNT_TABLES = (
    "sources",
    "source_state",
    "acquisition_runs",
    "observations",
    "evidence_artifacts",
    "knowledge_revisions",
    "objects",
    "claims",
    "relations",
    "evidence_links",
    "documents",
    "document_revisions",
    "document_chunks",
    "incidents",
)


async def data_plane_status() -> dict[str, Any]:
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            counts: dict[str, int] = {}
            for table in _COUNT_TABLES:
                value = await session.scalar(text(f"SELECT count(*) FROM {table}"))
                counts[table] = int(value or 0)

            knowledge_head = await session.scalar(
                text("SELECT max(revision) FROM knowledge_revisions")
            )
            latest_knowledge_commit = await session.scalar(
                text("SELECT max(committed_at) FROM knowledge_revisions")
            )
            latest_observation = await session.scalar(
                text("SELECT max(observed_at) FROM observations")
            )
            latest_scheduled_success = await session.scalar(
                text(
                    "SELECT max(finished_at) FROM acquisition_runs "
                    "WHERE trigger = 'scheduled' AND status IN ('success', 'no_change')"
                )
            )
            acquisition_status_rows = (
                await session.execute(
                    text(
                        "SELECT status, count(*) FROM acquisition_runs "
                        "GROUP BY status ORDER BY status"
                    )
                )
            ).all()
            recent_source_successes = (
                await session.execute(
                    text(
                        "SELECT source_id, last_success_at, consecutive_failures, next_due_at "
                        "FROM source_state WHERE last_success_at IS NOT NULL "
                        "ORDER BY last_success_at DESC NULLS LAST LIMIT 10"
                    )
                )
            ).all()
            return {
                "knowledge_head_revision": int(knowledge_head or 0),
                "latest_knowledge_commit_at": (
                    latest_knowledge_commit.isoformat() if latest_knowledge_commit else None
                ),
                "latest_observation_at": (
                    latest_observation.isoformat() if latest_observation else None
                ),
                "latest_scheduled_success_at": (
                    latest_scheduled_success.isoformat() if latest_scheduled_success else None
                ),
                "counts": counts,
                "acquisition_status_counts": {
                    str(status): cast(int, count) for status, count in acquisition_status_rows
                },
                "recent_source_successes": [
                    {
                        "source_id": str(source_id),
                        "last_success_at": cast(datetime, last_success_at).isoformat(),
                        "consecutive_failures": cast(int, consecutive_failures),
                        "next_due_at": (
                            cast(datetime, next_due_at).isoformat() if next_due_at else None
                        ),
                    }
                    for (
                        source_id,
                        last_success_at,
                        consecutive_failures,
                        next_due_at,
                    ) in recent_source_successes
                ],
            }
    finally:
        await engine.dispose()


def main() -> None:
    print(json.dumps(asyncio.run(data_plane_status()), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
