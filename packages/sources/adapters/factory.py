from __future__ import annotations

import httpx

from packages.shared.config import Settings
from packages.sources.adapters.nvd import NVDAdapter
from packages.sources.contracts import SourceAdapter, SourceDefinition


def create_source_adapter(
    source: SourceDefinition,
    client: httpx.AsyncClient,
    settings: Settings,
) -> SourceAdapter:
    if source.adapter_type == "nvd":
        return NVDAdapter(client, api_key=settings.nvd_api_key)
    raise ValueError(f"unsupported source adapter_type={source.adapter_type!r}")
