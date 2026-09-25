import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest

from packages.intelligence.hot_cache.contracts import HotBugRecord
from packages.intelligence.normalization.hot_bug import HotBugIngress
from packages.intelligence.normalization.nvd import NVDHotBugNormalizer
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope
from packages.sources.registry.loader import load_source_definitions

FIXTURE = Path("tests/fixtures/nvd_cve_page.json")
PAGE = json.loads(FIXTURE.read_text(encoding="utf-8"))


class FakeHotBugCache:
    def __init__(self) -> None:
        self.records: dict[tuple[str, str], HotBugRecord] = {}
        self.ttls: dict[tuple[str, str], int] = {}

    async def get(self, source_id: str, external_object_id: str) -> HotBugRecord | None:
        return self.records.get((source_id, external_object_id))

    async def admit(self, record: HotBugRecord, *, ttl_seconds: int) -> None:
        key = (record.source_id, record.external_object_id)
        self.records[key] = record
        self.ttls[key] = ttl_seconds

    async def touch(self, source_id: str, external_object_id: str) -> None:
        return None

    async def pin(self, source_id: str, external_object_id: str) -> None:
        return None

    async def unpin(self, source_id: str, external_object_id: str) -> None:
        return None

    async def evict(self, source_id: str, external_object_id: str) -> None:
        self.records.pop((source_id, external_object_id), None)


def _envelope(payload: dict[str, object], revision: str) -> IngestEnvelope:
    source = next(
        item
        for item in load_source_definitions(Path("config/sources"))
        if item.source_id == "nvd-cves-2"
    )
    cve = payload["cve"]
    assert isinstance(cve, dict)
    return IngestEnvelope.for_json_payload(
        acquisition_run_id="run-1",
        trigger=AcquisitionTrigger.SCHEDULED,
        source_id=source.source_id,
        external_object_id=str(cve["id"]),
        payload=payload,
        canonical_url="https://nvd.nist.gov/vuln/detail/CVE-2026-42424",
        published_at=datetime(2026, 9, 25, 0, 15, tzinfo=UTC),
        updated_at=datetime.fromisoformat(revision),
        external_revision=revision,
    )


@pytest.mark.asyncio
async def test_hot_ingress_detects_new_and_material_update() -> None:
    first_payload = PAGE["vulnerabilities"][0]
    cache = FakeHotBugCache()
    source = next(
        item
        for item in load_source_definitions(Path("config/sources"))
        if item.source_id == "nvd-cves-2"
    )
    now = datetime(2026, 9, 25, 2, 0, tzinfo=UTC)
    ingress = HotBugIngress(
        cache,
        {"nvd": NVDHotBugNormalizer()},
        ttl_seconds=600,
        now=lambda: now,
    )

    first = await ingress.accept(source, _envelope(first_payload, "2026-09-25T01:45:00+00:00"))
    assert "new_record" in first.priority_signals
    assert "critical_severity" in first.priority_signals
    assert "cvss_score" in first.changed_fields

    updated_payload = deepcopy(first_payload)
    cve = updated_payload["cve"]
    cve["lastModified"] = "2026-09-25T02:15:00.000"
    cve["metrics"]["cvssMetricV31"][0]["cvssData"]["baseScore"] = 8.8
    second = await ingress.accept(
        source,
        _envelope(updated_payload, "2026-09-25T02:15:00+00:00"),
    )

    assert "material_update" in second.priority_signals
    assert "critical_severity" not in second.priority_signals
    assert {"cvss_score", "last_modified"}.issubset(second.changed_fields)
    assert cache.ttls[(source.source_id, "CVE-2026-42424")] == 600
