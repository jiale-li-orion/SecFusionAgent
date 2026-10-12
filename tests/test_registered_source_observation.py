from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from apps.registered_source_observation import (
    RegisteredDocumentExecutor,
    _best_index_match,
    registered_research_sources,
    registered_source_registry,
)
from packages.runtime.capability.contracts import CapabilityResultStatus
from packages.shared.config import Settings
from packages.sources.contracts import DiscoveredRef


def test_registered_source_index_requires_title_overlap() -> None:
    items = [
        DiscoveredRef(
            external_object_id="paper-1",
            canonical_url="https://openai.com/research/frontier-security",
            locator={"title": "Frontier security research"},
        ),
        DiscoveredRef(
            external_object_id="paper-2",
            canonical_url="https://openai.com/research/model-evaluation",
            locator={"title": "Model evaluation"},
        ),
    ]
    assert _best_index_match(items, "frontier security") == items[0]
    assert _best_index_match(items, "unrelated incident") is None


@pytest.mark.asyncio
async def test_registered_document_read_returns_auditable_excerpt_and_raw_artifact() -> None:
    source = registered_research_sources(Settings())["openai-research"]
    registry = registered_source_registry({source.source_id: source})
    _, implementation = registry.resolve_binding(
        registry.contract("source.read_registered_document", 1)
    )
    page = (
        "<html><body><nav>ignore navigation</nav><article><h1>Frontier security</h1>"
        "<p>Our research describes the vulnerability investigation and evidence from "
        "the affected model deployment. Researchers verified the impact and published "
        "the remediation timeline.</p></article></body></html>"
    )
    requested: list[str] = []

    def transport(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, text=page, headers={"content-type": "text/html"})

    session = MagicMock()
    session.flush = AsyncMock()
    artifacts = MagicMock()
    artifacts.write = AsyncMock(return_value=SimpleNamespace(artifact_ref="artifact:raw-page"))
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        result = await RegisteredDocumentExecutor(
            session=session,
            execution_id="execution:test",
            task_run_id="task:test",
            allowed_object_ids={"target-1"},
            sources={source.source_id: source},
            client=client,
            artifacts=artifacts,
        ).execute(
            implementation,
            native_arguments={
                "object_id": "target-1",
                "source_id": source.source_id,
                "query_text": "https://openai.com/research/frontier-security",
            },
            timeout_seconds=15,
        )
    assert requested == ["https://openai.com/research/frontier-security"]
    assert result.status is CapabilityResultStatus.SUCCEEDED
    assert result.raw_artifact_ref == "artifact:raw-page"
    assert result.provenance["source_id"] == "openai-research"
    assert "vulnerability investigation" in result.extracted_candidates[0]["statement"]
    assert "ignore navigation" not in result.extracted_candidates[0]["statement"]
    assert session.add.call_args.args[0].status == "success"


@pytest.mark.asyncio
async def test_registered_document_read_cannot_escape_bound_target() -> None:
    source = registered_research_sources(Settings())["openai-research"]
    registry = registered_source_registry({source.source_id: source})
    _, implementation = registry.resolve_binding(
        registry.contract("source.read_registered_document", 1)
    )
    transport = httpx.MockTransport(lambda _: httpx.Response(200))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(PermissionError, match="TaskContract"):
            await RegisteredDocumentExecutor(
                session=MagicMock(),
                execution_id="execution:test",
                task_run_id="task:test",
                allowed_object_ids={"target-1"},
                sources={source.source_id: source},
                client=client,
                artifacts=MagicMock(),
            ).execute(
                implementation,
                native_arguments={
                    "object_id": "other-target",
                    "source_id": source.source_id,
                    "query_text": "https://openai.com/research/frontier-security",
                },
                timeout_seconds=15,
            )
