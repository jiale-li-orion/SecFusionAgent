from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.monitoring.storage.models import AcquisitionRunModel
from packages.sources.contracts import (
    AcquisitionTrigger,
    IngestEnvelope,
    QuerySpec,
    SourceAdapter,
    SourceDefinition,
)


class AcquisitionService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._now = now or (lambda: datetime.now(UTC))

    async def query(
        self,
        source: SourceDefinition,
        adapter: SourceAdapter,
        spec: QuerySpec,
        *,
        parent_run_id: str | None,
        trigger: AcquisitionTrigger = AcquisitionTrigger.ON_DEMAND,
    ) -> list[IngestEnvelope]:
        run_id = str(uuid4())
        started_at = self._now()
        async with self._session_factory() as session, session.begin():
            session.add(
                AcquisitionRunModel(
                    run_id=run_id,
                    source_id=source.source_id,
                    trigger=trigger.value,
                    parent_run_id=parent_run_id,
                    query_spec=spec.model_dump(mode="json"),
                    status="running",
                    cursor_in={},
                    cursor_out={},
                    attempt=1,
                    created_at=started_at,
                    started_at=started_at,
                )
            )

        try:
            results = await adapter.query(
                source,
                spec,
                acquisition_run_id=run_id,
                trigger=trigger,
            )
        except Exception as exc:
            async with self._session_factory() as session, session.begin():
                run = await session.get(AcquisitionRunModel, run_id)
                if run is None:
                    raise RuntimeError("on-demand acquisition run disappeared") from exc
                run.status = "failed"
                run.finished_at = self._now()
                run.error_code = exc.__class__.__name__
                run.error_detail = str(exc)[:4000]
            raise

        async with self._session_factory() as session, session.begin():
            run = await session.get(AcquisitionRunModel, run_id)
            if run is None:
                raise RuntimeError("on-demand acquisition run disappeared")
            run.status = "success" if results else "no_change"
            run.finished_at = self._now()
            run.cursor_out = {"result_count": len(results)}
        return results
