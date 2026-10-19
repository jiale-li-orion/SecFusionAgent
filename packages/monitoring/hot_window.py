from __future__ import annotations

from pydantic import BaseModel, Field, JsonValue

from packages.intelligence.hot_cache.contracts import HotNormalizationResult
from packages.intelligence.normalization.hot_bug import HotBugIngress
from packages.monitoring.hot_admission import HotAdmissionReceiptService
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
    rate_limit_state: dict[str, JsonValue] = Field(default_factory=dict)


class HotWindowCollector:
    """Run one checkpointed M1 -> M2 hot-window collection.

    The caller may commit ``next_cursor`` only after this method returns. If a
    fetch, ingress or receipt commit fails, the previous source cursor is
    retained. Earlier receipts remain durable even if the run fails or Redis
    later evicts its payloads; replay is absorbed by both owners' idempotency.
    """

    def __init__(
        self,
        adapter: SourceAdapter,
        ingress: HotBugIngress,
        receipts: HotAdmissionReceiptService,
    ) -> None:
        self._adapter = adapter
        self._ingress = ingress
        self._receipts = receipts

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
            result = await self._ingress.accept(source, envelope)
            await self._receipts.record(
                source, envelope, result, cursor_in=state.cursor, cursor_out=batch.next_cursor
            )
            accepted.append(result)
        return HotWindowCollectionResult(
            source_id=source.source_id,
            accepted=accepted,
            next_cursor=batch.next_cursor,
            rate_limit_state=batch.rate_limit_state,
        )
