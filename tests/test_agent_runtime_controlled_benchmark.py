from __future__ import annotations

import pytest

from scripts.run_agent_runtime_controlled_benchmark import (
    _probe_conflict_preservation,
    _probe_episode_recovery,
    _probe_health_ranked_fallback,
)


@pytest.mark.asyncio
async def test_health_ranked_fallback_uses_next_eligible_binding() -> None:
    result = await _probe_health_ranked_fallback()
    assert result.metrics["agent.fallback_success_rate"] == 1.0
    assert result.diagnostics["selected_binding_id"] == result.diagnostics["fallback_binding_id"]


@pytest.mark.asyncio
async def test_conflicting_evidence_is_preserved_in_conflict_state() -> None:
    result = await _probe_conflict_preservation()
    assert result.metrics["agent.conflict_collapse_rate"] == 0.0
    assert result.diagnostics["conflict_bucket_size"] == 1
    assert result.diagnostics["confirmed_bucket_size"] == 0


@pytest.mark.asyncio
async def test_failed_episode_can_recover_on_same_case_and_evidence_need() -> None:
    result = await _probe_episode_recovery()
    assert result.metrics["agent.recovery_success_rate"] == 1.0
    assert result.diagnostics["failed_run_status"] == "failed"
    assert result.diagnostics["recovery_run_status"] == "completed"
    assert result.diagnostics["same_case"] is True
