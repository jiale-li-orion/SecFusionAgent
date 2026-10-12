import json
from pathlib import Path

import httpx
import pytest

from packages.sources.adapters.github_repo import GitHubRepoAdapter
from packages.sources.contracts import AcquisitionTrigger, QuerySpec, SourceState
from packages.sources.errors import SourceRateLimited
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
        remaining = 45 - len(requests)
        return httpx.Response(
            200,
            json=FIXTURE,
            headers={
                "X-RateLimit-Limit": "60",
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Used": str(60 - remaining),
                "X-RateLimit-Reset": "1790877600",
            },
            request=request,
        )

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
        assert first.rate_limit_state == {
            "provider": "github",
            "requests_made": 1,
            "limit": 60,
            "remaining": 44,
            "used": 16,
            "reset_epoch": 1790877600,
        }

        second = await adapter.discover(SOURCE, SourceState(cursor=first.next_cursor))
        assert second.items == []
        assert second.rate_limit_state["requests_made"] == 1
        assert second.rate_limit_state["remaining"] == 43

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


@pytest.mark.asyncio
async def test_github_repo_rate_limit_exposes_provider_reset(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={
                "X-RateLimit-Limit": "60",
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": "1790877600",
            },
            request=request,
        )

    class _FixedDateTime:
        @classmethod
        def now(cls, tz):
            from datetime import datetime

            return datetime.fromtimestamp(1790874000, tz=tz)

    monkeypatch.setattr("packages.sources.adapters.github_repo.datetime", _FixedDateTime)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = GitHubRepoAdapter(client)
        with pytest.raises(SourceRateLimited) as captured:
            await adapter.discover(SOURCE, SourceState())
    assert captured.value.retry_after_seconds == 3600


@pytest.mark.asyncio
async def test_github_repo_can_read_bounded_pull_request_files() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        assert request.url.params["per_page"] == "100"
        return httpx.Response(
            200,
            json=[{"filename": "src/fix.py", "patch": "@@ -1 +1 @@\n-bad\n+fixed"}],
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await GitHubRepoAdapter(client).query(
            SOURCE,
            QuerySpec(
                filters={
                    "repo_full_name": "vllm-project/vllm",
                    "object_type": "pull_request_files",
                    "pull_number": 42,
                }
            ),
            acquisition_run_id="pull-files-run",
            trigger=AcquisitionTrigger.INVESTIGATION,
        )
    assert paths == ["/repos/vllm-project/vllm/pulls/42/files"]
    assert result[0].canonical_url == "https://github.com/vllm-project/vllm/pull/42/files"
    assert result[0].json_payload["files"][0]["filename"] == "src/fix.py"
