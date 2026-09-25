from __future__ import annotations

import httpx

from packages.shared.config import Settings
from packages.sources.adapters.arxiv import ArxivAdapter
from packages.sources.adapters.cisa_kev import CISAKEVAdapter
from packages.sources.adapters.github_advisory import GitHubGlobalAdvisoryAdapter
from packages.sources.adapters.github_repo import GitHubRepoAdapter
from packages.sources.adapters.nvd import NVDAdapter
from packages.sources.adapters.osv import OSVAdapter
from packages.sources.adapters.rss_incident import RSSIncidentAdapter
from packages.sources.contracts import SourceAdapter, SourceDefinition


def create_source_adapter(
    source: SourceDefinition,
    client: httpx.AsyncClient,
    settings: Settings,
) -> SourceAdapter:
    if source.adapter_type == "nvd":
        return NVDAdapter(client, api_key=settings.nvd_api_key)
    if source.adapter_type == "osv":
        return OSVAdapter(client)
    if source.adapter_type == "github_global_advisory":
        return GitHubGlobalAdvisoryAdapter(client, token=settings.github_token)
    if source.adapter_type == "github_repo":
        return GitHubRepoAdapter(client, token=settings.github_token)
    if source.adapter_type == "cisa_kev":
        return CISAKEVAdapter(client)
    if source.adapter_type == "arxiv":
        return ArxivAdapter(client)
    if source.adapter_type == "rss_incident":
        return RSSIncidentAdapter(client)
    raise ValueError(f"unsupported source adapter_type={source.adapter_type!r}")
