from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from packages.intelligence.hot_cache.contracts import HotBugRecord
from packages.intelligence.normalization.hot_bug import HotBugIngress
from packages.intelligence.normalization.nvd import NVDHotBugNormalizer
from packages.monitoring.hot_window import HotWindowCollector
from packages.sources.contracts import (
    AcquisitionTrigger,
    DiscoveredRef,
    DiscoveryBatch,
    IngestEnvelope,
    QuerySpec,
    SourceDefinition,
    SourceState,
)
from packages.sources.registry.loader import load_source_definitions


class MemoryCache:
    def __init__(self) -> None:
        self.records: dict[tuple[str, str], HotBugRecord] = {}

    async def get(self, source_id: str, external_object_id: str) -> HotBugRecord | None:
        return self.records.get((source_id, external_object_id))

    async def admit(self, record: HotBugRecord, *, ttl_seconds: int) -> None:
        self.records[(record.source_id, record.external_object_id)] = record

    async def touch(self, source_id: str, external_object_id: str) -> None:
        return None

    async def pin(self, source_id: str, external_object_id: str) -> None:
        return None

    async def unpin(self, source_id: str, external_object_id: str) -> None:
        return None

    async def evict(self, source_id: str, external_object_id: str) -> None:
        self.records.pop((source_id, external_object_id), None)


class StubAdapter:
    def __init__(self, payloads: list[dict[str, Any]], *, fail_on: int | None = None) -> None:
        self.payloads = payloads
        self.fail_on = fail_on

    async def discover(self, source: SourceDefinition, state: SourceState) -> DiscoveryBatch:
        return DiscoveryBatch(
            items=[
                DiscoveredRef(
                    external_object_id=payload["cve"]["id"],
                    external_revision=payload["cve"]["lastModified"],
                    inline_payload=payload,
                )
                for payload in self.payloads
            ],
            next_cursor={"last_modified": "2026-09-25T03:00:00+00:00"},
        )

    async def fetch(
        self,
        source: SourceDefinition,
        ref: DiscoveredRef,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> IngestEnvelope:
        index = next(
            i
            for i, payload in enumerate(self.payloads)
            if payload["cve"]["id"] == ref.external_object_id
        )
        if self.fail_on == index:
            raise RuntimeError("synthetic fetch failure")
        assert ref.inline_payload is not None
        return IngestEnvelope.for_json_payload(
            acquisition_run_id=acquisition_run_id,
            trigger=trigger,
            source_id=source.source_id,
            external_object_id=ref.external_object_id,
            payload=ref.inline_payload,
            canonical_url=None,
            published_at=None,
            updated_at=datetime.fromisoformat(str(ref.external_revision)),
            external_revision=ref.external_revision,
        )

    async def query(
        self,
        source: SourceDefinition,
        spec: QuerySpec,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> list[IngestEnvelope]:
        raise NotImplementedError


def _payload(cve_id: str, modified: str) -> dict[str, Any]:
    return {
        "cve": {
            "id": cve_id,
            "lastModified": modified,
            "published": "2026-09-25T00:00:00+00:00",
            "descriptions": [{"lang": "en", "value": "fixture"}],
            "references": [],
        }
    }


@pytest.mark.asyncio
async def test_checkpoint_cursor_is_returned_only_after_full_batch_succeeds() -> None:
    source = next(
        item
        for item in load_source_definitions(Path("config/sources"))
        if item.source_id == "nvd-cves-2"
    )
    cache = MemoryCache()
    ingress = HotBugIngress(
        cache,
        {"nvd": NVDHotBugNormalizer()},
        ttl_seconds=600,
        now=lambda: datetime(2026, 9, 25, 3, 0, tzinfo=UTC),
    )
    payloads = [
        _payload("CVE-2026-40001", "2026-09-25T01:00:00+00:00"),
        _payload("CVE-2026-40002", "2026-09-25T02:00:00+00:00"),
    ]

    failing = HotWindowCollector(StubAdapter(payloads, fail_on=1), ingress)
    with pytest.raises(RuntimeError, match="synthetic fetch failure"):
        await failing.collect(
            source,
            SourceState(cursor={"last_modified": "old"}),
            acquisition_run_id="r1",
        )
    assert (source.source_id, "CVE-2026-40001") in cache.records
    assert (source.source_id, "CVE-2026-40002") not in cache.records

    replay = HotWindowCollector(StubAdapter(payloads), ingress)
    result = await replay.collect(
        source,
        SourceState(cursor={"last_modified": "old"}),
        acquisition_run_id="r2",
    )
    assert result.next_cursor == {"last_modified": "2026-09-25T03:00:00+00:00"}
    assert len(result.accepted) == 2
    assert len(cache.records) == 2
