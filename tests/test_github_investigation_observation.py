from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from apps.github_investigation_observation import (
    GitHubInvestigationExecutor,
    _repo_for_object,
    _selection,
    github_capability_registry,
    github_investigation_source,
)
from packages.intelligence.storage.knowledge_models import ObjectModel
from packages.runtime.capability.contracts import CapabilityResultStatus
from packages.shared.config import Settings

PULL_FIXTURE = json.loads(Path("tests/fixtures/github_pull_request.json").read_text())


def _repo() -> ObjectModel:
    return ObjectModel(
        object_id="target-1",
        object_type="Repo",
        canonical_key="github:vllm-project/vllm",
        properties={"full_name": "vllm-project/vllm"},
        created_revision=1,
    )


def test_github_selection_stays_in_bound_registered_repository() -> None:
    repo = _repo()
    assert _repo_for_object(repo, {"vllm-project/vllm"}) == "vllm-project/vllm"
    assert _selection(
        repo, "vllm-project/vllm", "https://github.com/vllm-project/vllm/pull/9123"
    ) == {"object_type": "pull_request", "pull_number": 9123}
    with pytest.raises(PermissionError, match="bound repository"):
        _selection(repo, "vllm-project/vllm", "https://github.com/other/repo/pull/1")
    with pytest.raises(PermissionError, match="registered source"):
        _repo_for_object(repo, {"other/repo"})


def test_bound_pull_request_reads_its_own_record_without_query_text() -> None:
    pull = ObjectModel(
        object_id="pull-1",
        object_type="PullRequest",
        canonical_key="github:vllm-project/vllm:pull:9123",
        properties={"repo_full_name": "vllm-project/vllm", "number": 9123},
        created_revision=1,
    )
    repo = _repo_for_object(pull, {"vllm-project/vllm"})
    assert _selection(pull, repo, None) == {
        "object_type": "pull_request", "pull_number": 9123,
    }
    pull.properties = {"repo_full_name": "vllm-project/vllm"}
    with pytest.raises(ValueError, match="exact number"):
        _selection(pull, repo, None)


@pytest.mark.asyncio
async def test_github_pull_read_includes_changed_file_patch_and_provenance() -> None:
    source = github_investigation_source(Settings())
    registry = github_capability_registry()
    _, implementation = registry.resolve_binding(
        registry.contract("github.read_development_record", 1)
    )
    requests: list[str] = []

    def transport(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if request.url.path.endswith("/files"):
            return httpx.Response(
                200,
                json=[
                    {
                        "filename": "src/fix.py",
                        "status": "modified",
                        "additions": 1,
                        "deletions": 1,
                        "patch": "@@ -1 +1 @@\n-vulnerable\n+checked",
                    }
                ],
            )
        return httpx.Response(200, json=PULL_FIXTURE)

    session = MagicMock()
    session.get = AsyncMock(return_value=_repo())
    session.flush = AsyncMock()
    artifacts = MagicMock()
    artifacts.write = AsyncMock(return_value=SimpleNamespace(artifact_ref="artifact:pr-with-files"))
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        result = await GitHubInvestigationExecutor(
            session=session,
            execution_id="execution:test",
            task_run_id="task:test",
            allowed_object_ids={"target-1"},
            source=source,
            client=client,
            token=None,
            artifacts=artifacts,
        ).execute(
            implementation,
            native_arguments={
                "object_id": "target-1",
                "query_text": "https://github.com/vllm-project/vllm/pull/9123",
            },
            timeout_seconds=15,
        )
    assert requests == [
        "/repos/vllm-project/vllm/pulls/9123",
        "/repos/vllm-project/vllm/pulls/9123/files",
    ]
    assert result.status is CapabilityResultStatus.SUCCEEDED
    assert result.raw_artifact_ref == "artifact:pr-with-files"
    assert result.provenance["source_id"] == "github-target-repos"
    assert result.cost["provider_requests"] == 2
    assert any("src/fix.py" in item["statement"] for item in result.extracted_candidates)
    assert session.add.call_args.args[0].status == "success"


@pytest.mark.asyncio
async def test_github_pull_read_rejects_unbound_target_before_network() -> None:
    source = github_investigation_source(Settings())
    registry = github_capability_registry()
    _, implementation = registry.resolve_binding(
        registry.contract("github.read_development_record", 1)
    )
    transport = httpx.MockTransport(lambda _: httpx.Response(200))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(PermissionError, match="TaskContract"):
            await GitHubInvestigationExecutor(
                session=MagicMock(),
                execution_id="execution:test",
                task_run_id="task:test",
                allowed_object_ids={"target-1"},
                source=source,
                client=client,
                token=None,
                artifacts=MagicMock(),
            ).execute(
                implementation,
                native_arguments={"object_id": "other-target"},
                timeout_seconds=15,
            )
