from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from packages.intelligence.documents.service import ManagedDocumentResult, ManagedDocumentService
from packages.monitoring.managed_content import ManagedContentCollector
from packages.monitoring.tests.test_scheduler_and_run_state import _database
from packages.sources.contracts import DiscoveredRef, DiscoveryBatch, SourceState
from packages.sources.registry.loader import load_source_definitions


@pytest.mark.parametrize("interval", [0, 3])
@pytest.mark.asyncio
async def test_managed_collection_obeys_source_interval_between_fetches(
    monkeypatch, interval
) -> None:
    engine, factory = await _database()
    source = next(
        d for d in load_source_definitions(Path("config/sources")) if d.source_id == "metr-research"
    )
    source = source.model_copy(update={"rate_limit_policy": {"polite_interval_seconds": interval}})
    calls: list[object] = []

    async def sleep(seconds):
        calls.append(("sleep", seconds))

    result = ManagedDocumentResult(
        document_id="doc",
        document_revision_id="rev",
        object_id="obj",
        observation_id="obs",
        chunk_count=1,
        replay=False,
        knowledge_revision=1,
        insight_candidate_id="insight",
    )

    async def fetch(*args, **kwargs):
        calls.append("fetch")
        return object()

    adapter = SimpleNamespace(
        discover=AsyncMock(
            return_value=DiscoveryBatch(
                items=[DiscoveredRef(external_object_id=str(i)) for i in range(3)],
                next_cursor={"done": True},
            )
        ),
        fetch=fetch,
    )
    service = Mock(spec=ManagedDocumentService, ingest=AsyncMock(return_value=result))
    monkeypatch.setattr("asyncio.sleep", sleep)
    try:
        collected = await ManagedContentCollector(adapter, service, factory).collect(
            source, SourceState(), acquisition_run_id="paced"
        )
        expected = (
            ["fetch", ("sleep", 3.0), "fetch", ("sleep", 3.0), "fetch"]
            if interval
            else ["fetch"] * 3
        )
        assert calls == expected
        assert len(collected.accepted) == 3
        assert collected.next_cursor == {"done": True}
    finally:
        await engine.dispose()
