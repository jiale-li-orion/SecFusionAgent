from datetime import UTC, datetime, timedelta

from packages.runtime.execution import BoundedLoop, BoundedLoopConfig, LoopStopReason

NOW = datetime(2026, 9, 27, 9, 0, tzinfo=UTC)


def _loop(*, max_iterations: int = 3, no_progress_limit: int = 2) -> BoundedLoop:
    return BoundedLoop(
        BoundedLoopConfig(
            loop_id="loop-1",
            execution_id="exec-1",
            max_iterations=max_iterations,
            deadline_at=NOW + timedelta(minutes=1),
            budget_ref="budget:1",
            no_progress_limit=no_progress_limit,
        )
    )


def test_loop_stops_on_operation_deadline_before_primitive_executes() -> None:
    loop = _loop()
    gate = loop.before_iteration(now=NOW + timedelta(minutes=1))
    assert gate.allowed is False
    assert gate.stop_reason is LoopStopReason.DEADLINE_REACHED
    assert loop.completed_iterations == 0


def test_loop_stops_on_budget_before_next_iteration() -> None:
    loop = _loop()
    assert loop.before_iteration(now=NOW, budget_available=False).stop_reason is (
        LoopStopReason.BUDGET_EXHAUSTED
    )


def test_no_progress_is_based_on_state_signature_not_model_turn_count() -> None:
    loop = _loop(no_progress_limit=2)
    assert loop.before_iteration(now=NOW).allowed is True
    assert loop.complete_iteration("state:a").allowed is True
    assert loop.before_iteration(now=NOW).allowed is True
    assert loop.complete_iteration("state:a").allowed is True
    assert loop.before_iteration(now=NOW).allowed is True
    result = loop.complete_iteration("state:a")
    assert result.allowed is False
    assert result.stop_reason is LoopStopReason.NO_PROGRESS


def test_max_iterations_is_operation_budget_stop() -> None:
    loop = _loop(max_iterations=2, no_progress_limit=5)
    assert loop.before_iteration(now=NOW).allowed is True
    loop.complete_iteration("state:1")
    assert loop.before_iteration(now=NOW).allowed is True
    loop.complete_iteration("state:2")
    gate = loop.before_iteration(now=NOW)
    assert gate.allowed is False
    assert gate.stop_reason is LoopStopReason.BUDGET_EXHAUSTED
