from __future__ import annotations

from datetime import UTC, datetime

from packages.sources.contracts import AcquisitionTrigger
from scripts.run_m1_benchmark import _monitoring_latency_query


def test_monitoring_latency_query_only_accepts_scheduled_acquisition() -> None:
    query = _monitoring_latency_query(
        datetime(2026, 9, 26, tzinfo=UTC),
        datetime(2026, 9, 28, tzinfo=UTC),
    )
    compiled = query.compile()
    values = set(compiled.params.values())
    assert "acquisition_trigger" in str(compiled)
    assert AcquisitionTrigger.SCHEDULED.value in values
    assert AcquisitionTrigger.ON_DEMAND.value not in values
    assert AcquisitionTrigger.PROMOTION.value not in values
