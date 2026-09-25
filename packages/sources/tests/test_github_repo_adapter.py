import json
from pathlib import Path

import httpx
import pytest

from packages.sources.adapters.github_repo import GitHubRepoAdapter
from packages.sources.contracts import AcquisitionTrigger, SourceState
from packages.sources.registry.loader import load_source_definitions

FIXTURE = json.loads(Path("tests/fixtures/github_repo.json").read_text())
SOURCE = next(
    item
    for item in load_source_definitions(Path("config/sources"))
    if item.source_id == "github-target-repos"
).model_copy(
    update={
        "discovery_method": {"base_url": "https://api.github.test", "repos": ["vllm-project/vllm"]}
    }
)


@pytest.mark.asyncio
async def test_github_repo_discovery_uses_repo_revision_cursor() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=FIXTURE, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = GitHubRepoAdapter(client)
        first = await adapter.discover(SOURCE, SourceState())
        assert len(first.items) == 1
        ref = first.items[0]
        assert ref.external_object_id == "vllm-project/vllm"
        assert ref.external_revision == (
            "updated=2026-09-25T09:00:00+00:00;pushed=2026-09-25T08:55:00+00:00"
        )
        assert first.next_cursor["repo_revisions"] == {"vllm-project/vllm": ref.external_revision}

        second = await adapter.discover(SOURCE, SourceState(cursor=first.next_cursor))
        assert second.items == []

        envelope = await adapter.fetch(
            SOURCE,
            ref,
            acquisition_run_id="repo-run",
            trigger=AcquisitionTrigger.SCHEDULED,
        )
    assert len(requests) == 2
    assert envelope.external_object_id == "vllm-project/vllm"
    assert envelope.json_payload["default_branch"] == "main"
    assert envelope.content_hash
