from __future__ import annotations

import json
from pathlib import Path

from packages.sources.inventory import load_source_inventory
from packages.sources.registry.loader import load_source_definitions
from packages.sources.resolver_registry import create_dynamic_source_resolvers


def test_source_inventory_has_explicit_owner_for_every_concrete_commitment() -> None:
    inventory = load_source_inventory()
    assert len(inventory.entries) == 99
    keys = [(item.category, item.name) for item in inventory.entries]
    assert len(keys) == len(set(keys))
    assert {item.category for item in inventory.entries} == {
        "vulnerability",
        "development",
        "academic",
        "vendor",
        "independent",
        "normative",
        "assets",
        "incidents",
    }

    configured = {item.source_id for item in load_source_definitions(Path("config/sources"))}
    referenced: set[str] = set()
    for item in inventory.entries:
        if item.mode == "dynamic_resolution":
            assert item.dynamic_owner
        else:
            assert item.source_ids
        for source_id in item.source_ids:
            assert source_id in configured, f"inventory source id is not configured: {source_id}"
            referenced.add(source_id)
    assert referenced == configured


def test_every_source_definition_has_a_live_probe_owner() -> None:
    configured = {item.source_id for item in load_source_definitions(Path("config/sources"))}
    probe_script = Path("scripts/probe_live_sources.py").read_text()
    missing = sorted(source_id for source_id in configured if source_id not in probe_script)
    assert missing == []


def test_grouped_inventory_members_still_exist_in_group_configuration() -> None:
    inventory = load_source_inventory()
    target_repo_config = json.loads(Path("config/sources/github-target-repos.json").read_text())
    repos = set(target_repo_config["discovery_method"]["repos"])
    expected_repos = {
        item.name
        for item in inventory.entries
        if item.category == "development"
        and item.mode == "grouped_member"
        and item.source_ids == ["github-target-repos"]
    }
    assert expected_repos <= repos

    iso_config = json.loads(Path("config/sources/iso-ai-standards.json").read_text())
    document_ids = {item["document_id"] for item in iso_config["discovery_method"]["documents"]}
    assert "ISO-IEC-5259-SERIES" in document_ids
    assert "ISO-IEC-TR-24028-2020" in document_ids


def test_dynamic_inventory_owners_have_executable_resolvers() -> None:
    inventory = load_source_inventory()
    expected = {
        item.dynamic_owner
        for item in inventory.entries
        if item.mode == "dynamic_resolution" and item.dynamic_owner is not None
    }
    assert expected == set(create_dynamic_source_resolvers())
