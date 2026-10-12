from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.investigation_runtime import InvestigationExternalObservationPort
from packages.investigation.perception.contracts import (
    PerceptionOperation,
    PerceptionRequest,
    PerceptionStepResult,
    PerceptionTarget,
)
from packages.investigation.perception.planner import PerceptionPlanner


@pytest.mark.asyncio
@pytest.mark.parametrize("source_ids", [[], ["nvd-cves-2", "github-target-repos"]])
async def test_external_read_requires_one_explicit_source(source_ids: list[str]) -> None:
    nvd = MagicMock(execute=AsyncMock())
    registered = MagicMock(execute=AsyncMock())
    github = MagicMock(execute=AsyncMock())
    request = PerceptionRequest(
        request_id="read:1",
        operation=PerceptionOperation.OBSERVE_EXTERNAL,
        target=PerceptionTarget(object_id="target-1", source_ids=source_ids),
    )
    step = PerceptionPlanner().plan(request).steps[0]

    result = await InvestigationExternalObservationPort(nvd, registered, github).execute(
        task_run_id="task-1", request=request, step=step,
    )

    assert result.unresolved == ["external_observation_requires_one_source_id"]
    nvd.execute.assert_not_awaited()
    registered.execute.assert_not_awaited()
    github.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_external_read_routes_explicit_github_source() -> None:
    nvd = MagicMock(execute=AsyncMock())
    registered = MagicMock(execute=AsyncMock())
    github = MagicMock(execute=AsyncMock(return_value=PerceptionStepResult(
        unresolved=["github_read_requires_bound_object"]
    )))
    request = PerceptionRequest(
        request_id="read:github",
        operation=PerceptionOperation.OBSERVE_EXTERNAL,
        target=PerceptionTarget(source_ids=["github-target-repos"]),
    )
    step = PerceptionPlanner().plan(request).steps[0]

    result = await InvestigationExternalObservationPort(nvd, registered, github).execute(
        task_run_id="task-1", request=request, step=step,
    )

    assert result.unresolved == ["github_read_requires_bound_object"]
    github.execute.assert_awaited_once()
    nvd.execute.assert_not_awaited()
    registered.execute.assert_not_awaited()
