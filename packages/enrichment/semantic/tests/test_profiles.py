from pathlib import Path

from packages.enrichment.semantic.profiles import (
    authority_instruction,
    semantic_profile_for_source,
)
from packages.sources.registry.loader import load_source_definitions

SOURCES = {item.source_id: item for item in load_source_definitions(Path("config/sources"))}


def test_every_durable_managed_source_has_a_semantic_profile() -> None:
    durable = [
        source for source in SOURCES.values() if source.retention_mode.value == "durable_managed"
    ]
    assert durable
    assert all(semantic_profile_for_source(source).profile_id for source in durable)


def test_normative_profile_preserves_applicability_and_policy_boundary() -> None:
    source = SOURCES["eu-ai-act"]
    profile = semantic_profile_for_source(source)
    assert profile.profile_id == "normative"
    assert "jurisdiction" in profile.instruction
    assert "binding_status" in profile.instruction
    assert "applicability" in profile.instruction
    assert "runtime policy" in profile.instruction
    assert "authority_scope" in authority_instruction(source)


def test_vendor_profile_does_not_convert_first_party_statement_to_independent_evidence() -> None:
    source = SOURCES["aws-security-bulletins"]
    profile = semantic_profile_for_source(source)
    instruction = f"{profile.instruction} {authority_instruction(source)}"
    assert profile.profile_id == "vendor"
    assert "first-party" in instruction
    assert "independent" in instruction
    assert "product" in instruction


def test_incident_forensic_profile_keeps_upstream_corroboration_boundary() -> None:
    source = SOURCES["chainalysis-research"]
    profile = semantic_profile_for_source(source)
    assert profile.profile_id == "incident_forensic"
    assert "upstream source" in profile.instruction
    assert "independent corroboration" in profile.instruction
