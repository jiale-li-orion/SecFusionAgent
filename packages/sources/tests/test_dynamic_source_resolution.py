from __future__ import annotations

import pytest

from packages.sources.resolution import SourceResolutionRequest
from packages.sources.resolver_registry import (
    create_dynamic_source_resolvers,
    get_dynamic_source_resolver,
)


def test_publication_resolver_routes_to_configured_scholarly_indexes() -> None:
    plan = get_dynamic_source_resolver("publication_resolver").resolve(
        SourceResolutionRequest(query="agent memory poisoning", limit=7)
    )
    assert {item.source_id for item in plan.provider_queries} == {
        "crossref-search",
        "openalex-search",
        "openreview-search",
        "semantic-scholar-search",
    }
    assert all(
        item.query_spec.filters["query"] == "agent memory poisoning"
        for item in plan.provider_queries
    )
    assert all(item.query_spec.filters["limit"] == 7 for item in plan.provider_queries)


def test_github_incident_followup_builds_advisory_and_development_queries() -> None:
    plan = get_dynamic_source_resolver("github_incident_followup_resolver").resolve(
        SourceResolutionRequest(
            cve_id="CVE-2026-42424",
            repo_full_name="vllm-project/vllm",
            object_type="commit",
            commit_sha="a" * 40,
        )
    )
    by_source = {item.source_id: item.query_spec.filters for item in plan.provider_queries}
    assert by_source["github-global-advisories"] == {"cve_id": "CVE-2026-42424"}
    assert by_source["github-target-repos"] == {
        "repo_full_name": "vllm-project/vllm",
        "object_type": "commit",
        "commit_sha": "a" * 40,
    }


def test_explicit_url_resolvers_only_normalize_public_https_targets() -> None:
    resolver = get_dynamic_source_resolver("incident_primary_source_resolver")
    plan = resolver.resolve(
        SourceResolutionRequest(
            candidate_urls=[
                "https://status.example.com/incidents/42#update",
                "https://status.example.com/incidents/42",
            ]
        )
    )
    assert [item.url for item in plan.direct_urls] == ["https://status.example.com/incidents/42"]
    assert plan.direct_urls[0].source_role_hint == "primary"

    for invalid in (
        "http://example.com/advisory",
        "https://localhost/admin",
        "https://127.0.0.1/private",
        "https://169.254.169.254/latest/meta-data",
        "https://user:pass@example.com/advisory",
    ):
        with pytest.raises(ValueError):
            resolver.resolve(SourceResolutionRequest(candidate_urls=[invalid]))


def test_dynamic_resolver_registry_names_are_unique() -> None:
    registry = create_dynamic_source_resolvers()
    assert len(registry) == 6
