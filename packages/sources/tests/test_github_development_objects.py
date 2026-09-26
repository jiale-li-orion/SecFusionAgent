import json
from pathlib import Path

import httpx
import pytest

from packages.sources.adapters.github_repo import GitHubRepoAdapter
from packages.sources.contracts import AcquisitionTrigger, QuerySpec
from packages.sources.registry.loader import load_source_definitions

SOURCE = next(
    item
    for item in load_source_definitions(Path("config/sources"))
    if item.source_id == "github-target-repos"
).model_copy(
    update={
        "discovery_method": {"base_url": "https://api.github.test", "repos": ["vllm-project/vllm"]}
    }
)

FIXTURES = {
    "/repos/vllm-project/vllm/issues/8421": json.loads(
        Path("tests/fixtures/github_issue.json").read_text()
    ),
    "/repos/vllm-project/vllm/pulls/9123": json.loads(
        Path("tests/fixtures/github_pull_request.json").read_text()
    ),
    "/repos/vllm-project/vllm/commits/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa": json.loads(
        Path("tests/fixtures/github_commit.json").read_text()
    ),
    "/repos/vllm-project/vllm/releases/tags/v0.11.1": json.loads(
        Path("tests/fixtures/github_release.json").read_text()
    ),
    "/repos/vllm-project/vllm/releases": [
        json.loads(Path("tests/fixtures/github_release.json").read_text())
    ],
}


@pytest.mark.asyncio
async def test_github_repo_query_fetches_typed_development_objects() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = FIXTURES.get(request.url.path)
        if payload is None:
            return httpx.Response(404, request=request)
        return httpx.Response(200, json=payload, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = GitHubRepoAdapter(client)
        issue = await adapter.query(
            SOURCE,
            QuerySpec(
                filters={
                    "repo_full_name": "vllm-project/vllm",
                    "object_type": "issue",
                    "issue_number": 8421,
                }
            ),
            acquisition_run_id="issue-run",
            trigger=AcquisitionTrigger.ON_DEMAND,
        )
        pull = await adapter.query(
            SOURCE,
            QuerySpec(
                filters={
                    "repo_full_name": "vllm-project/vllm",
                    "object_type": "pull_request",
                    "pull_number": 9123,
                }
            ),
            acquisition_run_id="pr-run",
            trigger=AcquisitionTrigger.ON_DEMAND,
        )
        commit = await adapter.query(
            SOURCE,
            QuerySpec(
                filters={
                    "repo_full_name": "vllm-project/vllm",
                    "object_type": "commit",
                    "commit_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                }
            ),
            acquisition_run_id="commit-run",
            trigger=AcquisitionTrigger.ON_DEMAND,
        )
        release = await adapter.query(
            SOURCE,
            QuerySpec(
                filters={
                    "repo_full_name": "vllm-project/vllm",
                    "object_type": "release",
                    "tag": "v0.11.1",
                }
            ),
            acquisition_run_id="release-run",
            trigger=AcquisitionTrigger.ON_DEMAND,
        )
        releases = await adapter.query(
            SOURCE,
            QuerySpec(
                filters={
                    "repo_full_name": "vllm-project/vllm",
                    "object_type": "releases",
                    "limit": 5,
                }
            ),
            acquisition_run_id="releases-run",
            trigger=AcquisitionTrigger.ON_DEMAND,
        )

    assert issue[0].external_object_id == "vllm-project/vllm#issue-8421"
    assert issue[0].request_metadata["object_type"] == "issue"
    assert pull[0].external_object_id == "vllm-project/vllm#pull-9123"
    assert pull[0].external_revision == "2026-09-24T10:00:00+00:00"
    assert commit[0].external_revision == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert release[0].external_object_id == "vllm-project/vllm@release-101001"
    assert releases[0].request_metadata["object_type"] == "release"
