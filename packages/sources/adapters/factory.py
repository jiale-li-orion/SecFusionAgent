from __future__ import annotations

import httpx

from packages.shared.config import Settings
from packages.sources.adapters.arxiv import ArxivAdapter
from packages.sources.adapters.cisa_kev import CISAKEVAdapter
from packages.sources.adapters.cnnvd import CNNVDAdapter
from packages.sources.adapters.cvelist_v5 import CVEListV5Adapter
from packages.sources.adapters.direct_document import DirectDocumentAdapter
from packages.sources.adapters.github_advisory import GitHubGlobalAdvisoryAdapter
from packages.sources.adapters.github_repo import GitHubRepoAdapter
from packages.sources.adapters.html_incident import HTMLIncidentAdapter
from packages.sources.adapters.html_index import HTMLIndexAdapter
from packages.sources.adapters.internet_asset import (
    CensysAssetAdapter,
    FOFAAssetAdapter,
    ZoomEyeAssetAdapter,
)
from packages.sources.adapters.nvd import NVDAdapter
from packages.sources.adapters.oscs import OSCSAdapter
from packages.sources.adapters.oss_security import OssSecurityAdapter
from packages.sources.adapters.osv import OSVAdapter
from packages.sources.adapters.rss_incident import RSSIncidentAdapter
from packages.sources.adapters.scholarly_search import ScholarlySearchAdapter
from packages.sources.adapters.shodan import ShodanAdapter
from packages.sources.adapters.slowmist_hacked import SlowMistHackedAdapter
from packages.sources.adapters.x_user_signal import XUserSignalAdapter
from packages.sources.contracts import SourceAdapter, SourceDefinition


def create_source_adapter(
    source: SourceDefinition,
    client: httpx.AsyncClient,
    settings: Settings,
) -> SourceAdapter:
    if source.adapter_type == "cvelist_v5":
        return CVEListV5Adapter(client)
    if source.adapter_type == "cnnvd":
        return CNNVDAdapter(client)
    if source.adapter_type == "direct_document":
        return DirectDocumentAdapter(client)
    if source.adapter_type == "scholarly_search":
        return ScholarlySearchAdapter(
            client, semantic_scholar_api_key=settings.semantic_scholar_api_key
        )
    if source.adapter_type == "nvd":
        return NVDAdapter(client, api_key=settings.nvd_api_key)
    if source.adapter_type == "osv":
        return OSVAdapter(client)
    if source.adapter_type == "oscs":
        return OSCSAdapter(client)
    if source.adapter_type == "oss_security":
        return OssSecurityAdapter(client)
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
    if source.adapter_type == "html_index":
        return HTMLIndexAdapter(client)
    if source.adapter_type == "html_incident":
        return HTMLIncidentAdapter(client)
    if source.adapter_type == "shodan":
        return ShodanAdapter(client, api_key=settings.shodan_api_key)
    if source.adapter_type == "slowmist_hacked":
        return SlowMistHackedAdapter(client)
    if source.adapter_type == "x_user_signal":
        return XUserSignalAdapter(client, bearer_token=settings.x_bearer_token)
    if source.adapter_type == "censys_asset":
        return CensysAssetAdapter(
            client,
            pat=settings.censys_pat,
            organization_id=settings.censys_organization_id,
        )
    if source.adapter_type == "fofa_asset":
        return FOFAAssetAdapter(client, api_key=settings.fofa_api_key)
    if source.adapter_type == "zoomeye_asset":
        return ZoomEyeAssetAdapter(client, api_key=settings.zoomeye_api_key)
    raise ValueError(f"unsupported source adapter_type={source.adapter_type!r}")
