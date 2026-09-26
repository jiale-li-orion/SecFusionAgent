from pathlib import Path

from packages.sources.contracts import RetentionMode
from packages.sources.lifecycle_audit import (
    audit_source_lifecycles,
    time_bounded_processing_owner,
)
from packages.sources.registry.loader import load_source_definitions


def test_all_configured_sources_have_executable_lifecycle_ownership() -> None:
    definitions = load_source_definitions(Path("config/sources"))
    assert audit_source_lifecycles(definitions) == []


def test_every_time_bounded_source_has_a_downstream_processing_owner() -> None:
    definitions = load_source_definitions(Path("config/sources"))
    owners = {
        source.source_id: time_bounded_processing_owner(source)
        for source in definitions
        if source.retention_mode is RetentionMode.TIME_BOUNDED
    }
    assert owners
    assert all(owner is not None for owner in owners.values())
