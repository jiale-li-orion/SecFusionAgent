from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class LoopStopReason(StrEnum):
    GOAL_SATISFIED = "goal_satisfied"
    EVIDENCE_SUFFICIENT = "evidence_sufficient"
    BUDGET_EXHAUSTED = "budget_exhausted"
    DEADLINE_REACHED = "deadline_reached"
    PROVIDER_BLOCKED = "provider_blocked"
    CAPABILITY_DENIED = "capability_denied"
    POLICY_DENIED = "policy_denied"
    EXTERNAL_FAILURE = "external_failure"
    NO_PROGRESS = "no_progress"
    WAITING_FOR_WORLD_UPDATE = "waiting_for_world_update"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


class BoundedLoopConfig(BaseModel):
    loop_id: str
    execution_id: str
    max_iterations: int = Field(ge=1)
    deadline_at: datetime
    budget_ref: str
    no_progress_limit: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_deadline(self) -> BoundedLoopConfig:
        if self.deadline_at.tzinfo is None:
            raise ValueError("BoundedLoop deadline_at must be timezone-aware")
        return self


class LoopGate(BaseModel):
    allowed: bool
    iteration: int
    stop_reason: LoopStopReason | None = None


class BoundedLoop:
    """Operation-level loop guard independent of any model/tool primitive."""

    def __init__(self, config: BoundedLoopConfig) -> None:
        self.config = config
        self._completed_iterations = 0
        self._last_progress_signature: str | None = None
        self._no_progress_count = 0
        self._terminal_reason: LoopStopReason | None = None

    @property
    def completed_iterations(self) -> int:
        return self._completed_iterations

    @property
    def no_progress_count(self) -> int:
        return self._no_progress_count

    @property
    def terminal_reason(self) -> LoopStopReason | None:
        return self._terminal_reason

    def before_iteration(
        self,
        *,
        now: datetime,
        budget_available: bool = True,
    ) -> LoopGate:
        if now.tzinfo is None:
            raise ValueError("BoundedLoop now must be timezone-aware")
        if self._terminal_reason is not None:
            return LoopGate(
                allowed=False,
                iteration=self._completed_iterations,
                stop_reason=self._terminal_reason,
            )
        if now >= self.config.deadline_at:
            self._terminal_reason = LoopStopReason.DEADLINE_REACHED
        elif not budget_available:
            self._terminal_reason = LoopStopReason.BUDGET_EXHAUSTED
        elif self._completed_iterations >= self.config.max_iterations:
            self._terminal_reason = LoopStopReason.BUDGET_EXHAUSTED
        elif self._no_progress_count >= self.config.no_progress_limit:
            self._terminal_reason = LoopStopReason.NO_PROGRESS
        if self._terminal_reason is not None:
            return LoopGate(
                allowed=False,
                iteration=self._completed_iterations,
                stop_reason=self._terminal_reason,
            )
        return LoopGate(allowed=True, iteration=self._completed_iterations + 1)

    def complete_iteration(self, progress_signature: str | None) -> LoopGate:
        if self._terminal_reason is not None:
            raise RuntimeError("cannot complete iteration after loop termination")
        self._completed_iterations += 1
        if progress_signature is None or progress_signature == self._last_progress_signature:
            self._no_progress_count += 1
        else:
            self._last_progress_signature = progress_signature
            self._no_progress_count = 0
        if self._no_progress_count >= self.config.no_progress_limit:
            self._terminal_reason = LoopStopReason.NO_PROGRESS
        return LoopGate(
            allowed=self._terminal_reason is None,
            iteration=self._completed_iterations,
            stop_reason=self._terminal_reason,
        )

    def stop(self, reason: LoopStopReason) -> LoopGate:
        self._terminal_reason = reason
        return LoopGate(
            allowed=False,
            iteration=self._completed_iterations,
            stop_reason=reason,
        )
