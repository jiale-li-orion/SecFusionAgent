import asyncio
from pathlib import Path

import httpx

from packages.intelligence.incident.factory import create_incident_signal_extractors
from packages.intelligence.normalization.factory import (
    create_durable_bug_normalizer,
    create_hot_bug_normalizer,
)
from packages.shared.config import Settings
from packages.sources.adapters.factory import create_source_adapter
from packages.sources.contracts import RetentionMode
from packages.sources.registry.loader import load_source_definitions


def test_every_hot_window_source_has_hot_and_durable_normalization() -> None:
    sources = load_source_definitions(Path("config/sources"))
    hot_sources = [
        source for source in sources if source.retention_mode is RetentionMode.HOT_WINDOW
    ]
    assert hot_sources
    for source in hot_sources:
        assert create_hot_bug_normalizer(source) is not None
        assert create_durable_bug_normalizer(source) is not None


def test_every_incident_signal_adapter_has_runtime_extractor() -> None:
    sources = load_source_definitions(Path("config/sources"))
    incident_adapters = {
        source.adapter_type
        for source in sources
        if source.retention_mode is RetentionMode.INCIDENT_SIGNAL
    }
    assert incident_adapters
    assert incident_adapters <= set(create_incident_signal_extractors())


def test_every_source_definition_can_be_constructed_by_runtime_adapter_factory() -> None:
    sources = load_source_definitions(Path("config/sources"))
    client = httpx.AsyncClient()
    try:
        for source in sources:
            assert create_source_adapter(source, client, Settings()) is not None
    finally:
        asyncio.run(client.aclose())
