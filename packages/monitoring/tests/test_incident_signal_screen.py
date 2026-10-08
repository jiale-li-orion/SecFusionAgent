from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest

from packages.intelligence.incident.relevance import should_collect_incident_headline
from packages.monitoring.incident_signal import IncidentSignalCollector
from packages.sources.contracts import (
    AcquisitionTrigger,
    DiscoveredRef,
    DiscoveryBatch,
    IngestEnvelope,
    RetentionMode,
    SourceDefinition,
    SourceRole,
    SourceState,
)


def test_broad_news_gate_keeps_reported_attacks_and_drops_market_headlines() -> None:
    assert not should_collect_incident_headline(
        "blockbeats-newsflash", "Soda Labs完成300万美元种子轮融资"
    )
    assert should_collect_incident_headline(
        "blockbeats-newsflash", "韩国五大商业银行遭黑客攻击, 三家出现客户信息泄露"
    )
    assert not should_collect_incident_headline(
        "bleepingcomputer-news", "Ransomware has a new target. Is your backup ready?"
    )
    assert should_collect_incident_headline(
        "bleepingcomputer-news", "FBI: Ongoing FortiBleed attacks lock out FortiGate admins"
    )


@pytest.mark.asyncio
async def test_collector_advances_cursor_without_creating_general_news_candidate() -> None:
    class MarketAdapter:
        async def discover(self, *_args: object) -> DiscoveryBatch:
            return DiscoveryBatch(
                items=[DiscoveredRef(external_object_id="finance-1")],
                next_cursor={"page": 2},
            )

        async def fetch(
            self, source: SourceDefinition, ref: DiscoveredRef, **_kwargs: object
        ) -> IngestEnvelope:
            return IngestEnvelope.for_json_payload(
                acquisition_run_id="run-market",
                trigger=AcquisitionTrigger.SCHEDULED,
                source_id=source.source_id,
                external_object_id=ref.external_object_id,
                payload={"title": "Soda Labs完成300万美元种子轮融资"},
                canonical_url=None,
                published_at=None,
                updated_at=None,
                external_revision=None,
                observed_at=datetime(2026, 10, 9, tzinfo=UTC),
            )

    source = SourceDefinition(
        source_id="blockbeats-newsflash",
        adapter_type="html_incident",
        source_class="incident_news",
        source_role=SourceRole.SIGNAL,
        source_family="blockbeats",
        access_mode="public",
        update_semantics="append",
        retention_mode=RetentionMode.INCIDENT_SIGNAL,
    )
    unused = cast(Any, object())
    result = await IncidentSignalCollector(
        cast(Any, MarketAdapter()), unused, unused, unused, {source.source_id: source}
    ).collect(source, SourceState(), acquisition_run_id="run-market")
    assert result.accepted == []
    assert result.promoted == []
    assert result.screened_out == 1
    assert result.next_cursor == {"page": 2}
