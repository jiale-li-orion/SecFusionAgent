from __future__ import annotations

from dataclasses import dataclass

from packages.sources.contracts import RetentionMode, SourceDefinition

HOT_WINDOW_ADAPTERS = frozenset({"nvd", "cvelist_v5"})
SELECTIVE_INDEX_ADAPTERS = frozenset({"github_repo"})
INCIDENT_SIGNAL_ADAPTERS = frozenset(
    {"rss_incident", "html_incident", "slowmist_hacked", "x_user_signal"}
)

VULNERABILITY_ENRICHMENT_SOURCES = frozenset(
    {"cisa-kev", "github-global-advisories", "osv-vulnerabilities"}
)
VULNERABILITY_REFERENCE_SOURCES = frozenset({"cnnvd-vulnerabilities", "cnvd-vulnerabilities"})
GENERIC_EXTERNAL_QUERY_SOURCES = frozenset(
    {
        "crossref-search",
        "openalex-search",
        "openreview-search",
        "semantic-scholar-search",
        "oscs-community",
    }
)
DURABLE_MANAGED_ADAPTERS = frozenset({"arxiv", "html_index", "direct_document", "oss_security"})
TIME_BOUNDED_ADAPTERS = frozenset(
    {
        "cisa_kev",
        "cnnvd",
        "html_index",
        "scholarly_search",
        "github_global_advisory",
        "oscs",
        "osv",
        "shodan",
        "censys_asset",
        "fofa_asset",
        "zoomeye_asset",
    }
)


@dataclass(frozen=True)
class SourceLifecycleIssue:
    source_id: str
    code: str
    detail: str


def audit_source_lifecycles(
    definitions: list[SourceDefinition],
) -> list[SourceLifecycleIssue]:
    issues: list[SourceLifecycleIssue] = []
    for source in definitions:
        allowed = _allowed_adapters(source.retention_mode)
        if source.adapter_type not in allowed:
            issues.append(
                SourceLifecycleIssue(
                    source.source_id,
                    "unsupported_retention_adapter",
                    f"{source.retention_mode.value} does not own adapter {source.adapter_type!r}",
                )
            )

        if source.retention_mode is RetentionMode.TIME_BOUNDED:
            owner = time_bounded_processing_owner(source)
            if owner is None:
                issues.append(
                    SourceLifecycleIssue(
                        source.source_id,
                        "time_bounded_has_no_consumer",
                        "time-bounded query result has no explicit downstream processing owner",
                    )
                )

        schedule_enabled = source.schedule_policy.get("enabled", True) is not False
        if source.retention_mode is RetentionMode.TIME_BOUNDED and schedule_enabled:
            issues.append(
                SourceLifecycleIssue(
                    source.source_id,
                    "time_bounded_must_be_on_demand",
                    (
                        "time_bounded source would be scheduled into a runtime path "
                        "that is intentionally on-demand"
                    ),
                )
            )

        if source.retention_mode is RetentionMode.DURABLE_MANAGED:
            configured = source.discovery_method.get("allowed_media_types")
            if isinstance(configured, list):
                media_types = {item for item in configured if isinstance(item, str)}
                unsupported = media_types - {
                    "text/html",
                    "application/xhtml+xml",
                    "application/pdf",
                    "text/plain",
                    "text/yaml",
                    "application/yaml",
                    "application/x-yaml",
                    "application/octet-stream",
                }
                if unsupported:
                    issues.append(
                        SourceLifecycleIssue(
                            source.source_id,
                            "unsupported_managed_media_type",
                            f"managed-content runtime has no parser for {sorted(unsupported)!r}",
                        )
                    )
    return issues


def time_bounded_processing_owner(source: SourceDefinition) -> str | None:
    if source.source_class == "internet_asset_intelligence":
        return "AssetObservationService"
    if source.source_id in VULNERABILITY_ENRICHMENT_SOURCES:
        return "VulnerabilityEnrichmentService"
    if source.source_id in VULNERABILITY_REFERENCE_SOURCES:
        return "ExternalVulnerabilityReferenceService"
    if source.source_id in GENERIC_EXTERNAL_QUERY_SOURCES:
        return "TimeBoundedEvidenceService"
    return None


def _allowed_adapters(mode: RetentionMode) -> frozenset[str]:
    if mode is RetentionMode.HOT_WINDOW:
        return HOT_WINDOW_ADAPTERS
    if mode is RetentionMode.SELECTIVE_INDEX:
        return SELECTIVE_INDEX_ADAPTERS
    if mode is RetentionMode.INCIDENT_SIGNAL:
        return INCIDENT_SIGNAL_ADAPTERS
    if mode is RetentionMode.DURABLE_MANAGED:
        return DURABLE_MANAGED_ADAPTERS
    if mode is RetentionMode.TIME_BOUNDED:
        return TIME_BOUNDED_ADAPTERS
    raise AssertionError(f"unhandled retention mode: {mode}")
