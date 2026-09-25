from __future__ import annotations

from pydantic import BaseModel, JsonValue

from packages.intelligence.hot_cache.contracts import HotNormalizationResult
from packages.intelligence.normalization.hot_bug import HotBugIngress
from packages.sources.contracts import (
    AcquisitionTrigger,
    SourceAdapter,
    SourceDefinition,
    SourceState,
)


class HotWindowCollectionResult(BaseModel):
    source_id: str
    accepted: list[HotNormalizationResult]
    next_cursor: dict[str, JsonValue]


class HotWindowCollector:
    """Run one checkpointed M1 -> M2 hot-window collection.

    The caller may commit ``next_cursor`` only after this method returns. If a
    fetch or ingress step fails, already-admitted records remain in Redis and
    the previous source cursor is retained; replay is absorbed by idempotency.
    """

    def __init__(self, adapter: SourceAdapter, ingress: HotBugIngress) -> None:
        self._adapter = adapter
        self._ingress = ingress

    async def collect(
        self,
        source: SourceDefinition,
        state: SourceState,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger = AcquisitionTrigger.SCHEDULED,
    ) -> HotWindowCollectionResult:
        batch = await self._adapter.discover(source, state)
        accepted: list[HotNormalizationResult] = []
        for ref in batch.items:
            envelope = await self._adapter.fetch(
                source,
                ref,
                acquisition_run_id=acquisition_run_id,
                trigger=trigger,
            )
            accepted.append(await self._ingress.accept(source, envelope))
        return HotWindowCollectionResult(
            source_id=source.source_id,
            accepted=accepted,
            next_cursor=batch.next_cursor,
        )
