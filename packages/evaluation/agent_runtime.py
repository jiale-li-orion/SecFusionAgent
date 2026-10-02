from __future__ import annotations

from pydantic import BaseModel, Field


class AgentCapabilityCall(BaseModel):
    capability_id: str
    arguments_digest: str


class AgentRuntimeGold(BaseModel):
    expected_task_success: bool
    allowed_target_refs: list[str] = Field(default_factory=list)
    expected_fixed_version: str | None = None
    allowed_reasoning_relation_source_refs: list[str] = Field(default_factory=list)
    allowed_reasoning_claim_source_refs: list[str] = Field(default_factory=list)
    required_capability_ids: list[str] = Field(default_factory=list)
    allowed_capability_ids: list[str] = Field(default_factory=list)
    expected_argument_digests: dict[str, list[str]] = Field(default_factory=dict)
    required_event_types: list[str] = Field(default_factory=list)
    forbidden_event_types: list[str] = Field(default_factory=list)
    acceptable_stop_reasons: list[str] = Field(default_factory=list)
    expected_continuation: bool | None = None


class AgentRuntimeObservation(BaseModel):
    task_success: bool
    capability_calls: list[AgentCapabilityCall] = Field(default_factory=list)
    event_types: list[str] = Field(default_factory=list)
    stop_reason: str | None = None
    timed_out: bool = False
    wall_latency_seconds: float | None = Field(default=None, ge=0)
    planning_iteration_count: int = Field(default=0, ge=0)
    no_progress_iteration_count: int = Field(default=0, ge=0)
    continuation_requested: bool = False
    recoverable_failure_count: int = Field(default=0, ge=0)
    recovered_failure_count: int = Field(default=0, ge=0)
    policy_request_count: int = Field(default=0, ge=0)
    unnecessary_denied_request_count: int = Field(default=0, ge=0)
    fallback_count: int = Field(default=0, ge=0)
    fallback_success_count: int = Field(default=0, ge=0)
    critical_evidence_need_count: int = Field(default=0, ge=0)
    critical_evidence_need_recalled_count: int = Field(default=0, ge=0)
    opened_gap_count: int = Field(default=0, ge=0)
    false_gap_count: int = Field(default=0, ge=0)
    acquisition_count: int = Field(default=0, ge=0)
    useful_acquisition_count: int = Field(default=0, ge=0)
    redundant_acquisition_count: int = Field(default=0, ge=0)
    source_role_requirement_count: int = Field(default=0, ge=0)
    source_role_satisfied_count: int = Field(default=0, ge=0)
    freshness_requirement_count: int = Field(default=0, ge=0)
    freshness_satisfied_count: int = Field(default=0, ge=0)
    integrated_assertion_count: int = Field(default=0, ge=0)
    wrong_entity_attachment_count: int = Field(default=0, ge=0)
    version_scoped_assertion_count: int = Field(default=0, ge=0)
    wrong_version_attachment_count: int = Field(default=0, ge=0)
    evidence_ref_assertion_count: int = Field(default=0, ge=0)
    invalid_evidence_ref_count: int = Field(default=0, ge=0)
    conflict_group_count: int = Field(default=0, ge=0)
    collapsed_conflict_count: int = Field(default=0, ge=0)
    delegation_count: int = Field(default=0, ge=0)
    useful_child_task_count: int = Field(default=0, ge=0)
    budget_adherent_child_task_count: int = Field(default=0, ge=0)
    stale_child_result_count: int = Field(default=0, ge=0)
    budget_deadline_boundary_count: int = Field(default=0, ge=0)
    correct_budget_deadline_stop_count: int = Field(default=0, ge=0)


class AgentRuntimeScore(BaseModel):
    task_success: float
    capability_selection_correctness: float | None = Field(default=None, ge=0, le=1)
    argument_correctness: float | None = Field(default=None, ge=0, le=1)
    trajectory_conformance: float | None = Field(default=None, ge=0, le=1)
    recovery_success_rate: float | None = Field(default=None, ge=0, le=1)
    timeout_rate: float = Field(ge=0, le=1)
    wall_latency_seconds: float | None = Field(default=None, ge=0)
    capability_invocation_count: int = Field(ge=0)
    critical_evidence_need_recall: float | None = Field(default=None, ge=0, le=1)
    false_gap_rate: float | None = Field(default=None, ge=0, le=1)
    useful_acquisition_precision: float | None = Field(default=None, ge=0, le=1)
    redundant_acquisition_rate: float | None = Field(default=None, ge=0, le=1)
    source_role_satisfaction: float | None = Field(default=None, ge=0, le=1)
    freshness_satisfaction: float | None = Field(default=None, ge=0, le=1)
    wrong_entity_attachment_rate: float | None = Field(default=None, ge=0, le=1)
    wrong_version_attachment_rate: float | None = Field(default=None, ge=0, le=1)
    invalid_evidence_ref_rate: float | None = Field(default=None, ge=0, le=1)
    conflict_collapse_rate: float | None = Field(default=None, ge=0, le=1)
    unnecessary_denied_request_rate: float | None = Field(default=None, ge=0, le=1)
    fallback_success_rate: float | None = Field(default=None, ge=0, le=1)
    delegation_precision: float | None = Field(default=None, ge=0, le=1)
    child_task_usefulness: float | None = Field(default=None, ge=0, le=1)
    parent_child_budget_adherence: float | None = Field(default=None, ge=0, le=1)
    stale_child_result_rate: float | None = Field(default=None, ge=0, le=1)
    stop_correctness: float | None = Field(default=None, ge=0, le=1)
    no_progress_iteration_rate: float | None = Field(default=None, ge=0, le=1)
    budget_deadline_stop_correctness: float | None = Field(default=None, ge=0, le=1)
    unnecessary_continuation_rate: float | None = Field(default=None, ge=0, le=1)


def score_agent_runtime(
    *,
    gold: AgentRuntimeGold,
    observation: AgentRuntimeObservation,
) -> AgentRuntimeScore:
    actual_capabilities = [item.capability_id for item in observation.capability_calls]
    allowed = set(gold.allowed_capability_ids)
    required = set(gold.required_capability_ids)
    selection_evaluable = bool(allowed or required)
    selection_correct = (
        (not allowed or set(actual_capabilities) <= allowed)
        and required <= set(actual_capabilities)
        if selection_evaluable
        else None
    )

    argument_checks: list[bool] = []
    for call in observation.capability_calls:
        expected = gold.expected_argument_digests.get(call.capability_id)
        if expected:
            argument_checks.append(call.arguments_digest in set(expected))

    trajectory_evaluable = bool(gold.required_event_types or gold.forbidden_event_types)
    events = set(observation.event_types)
    trajectory_correct = (
        set(gold.required_event_types) <= events
        and not (set(gold.forbidden_event_types) & events)
        if trajectory_evaluable
        else None
    )
    stop_correct = (
        observation.stop_reason in set(gold.acceptable_stop_reasons)
        if gold.acceptable_stop_reasons
        else None
    )
    unnecessary_continuation = (
        float(observation.continuation_requested and not gold.expected_continuation)
        if gold.expected_continuation is not None
        else None
    )

    return AgentRuntimeScore(
        task_success=float(observation.task_success == gold.expected_task_success),
        capability_selection_correctness=(
            float(selection_correct) if selection_correct is not None else None
        ),
        argument_correctness=_bool_mean(argument_checks),
        trajectory_conformance=(
            float(trajectory_correct) if trajectory_correct is not None else None
        ),
        recovery_success_rate=_ratio(
            observation.recovered_failure_count,
            observation.recoverable_failure_count,
        ),
        timeout_rate=float(observation.timed_out),
        wall_latency_seconds=observation.wall_latency_seconds,
        capability_invocation_count=len(observation.capability_calls),
        critical_evidence_need_recall=_ratio(
            observation.critical_evidence_need_recalled_count,
            observation.critical_evidence_need_count,
        ),
        false_gap_rate=_ratio(observation.false_gap_count, observation.opened_gap_count),
        useful_acquisition_precision=_ratio(
            observation.useful_acquisition_count,
            observation.acquisition_count,
        ),
        redundant_acquisition_rate=_ratio(
            observation.redundant_acquisition_count,
            observation.acquisition_count,
        ),
        source_role_satisfaction=_ratio(
            observation.source_role_satisfied_count,
            observation.source_role_requirement_count,
        ),
        freshness_satisfaction=_ratio(
            observation.freshness_satisfied_count,
            observation.freshness_requirement_count,
        ),
        wrong_entity_attachment_rate=_ratio(
            observation.wrong_entity_attachment_count,
            observation.integrated_assertion_count,
        ),
        wrong_version_attachment_rate=_ratio(
            observation.wrong_version_attachment_count,
            observation.version_scoped_assertion_count,
        ),
        invalid_evidence_ref_rate=_ratio(
            observation.invalid_evidence_ref_count,
            observation.evidence_ref_assertion_count,
        ),
        conflict_collapse_rate=_ratio(
            observation.collapsed_conflict_count,
            observation.conflict_group_count,
        ),
        unnecessary_denied_request_rate=_ratio(
            observation.unnecessary_denied_request_count,
            observation.policy_request_count,
        ),
        fallback_success_rate=_ratio(
            observation.fallback_success_count,
            observation.fallback_count,
        ),
        delegation_precision=_ratio(
            observation.useful_child_task_count,
            observation.delegation_count,
        ),
        child_task_usefulness=_ratio(
            observation.useful_child_task_count,
            observation.delegation_count,
        ),
        parent_child_budget_adherence=_ratio(
            observation.budget_adherent_child_task_count,
            observation.delegation_count,
        ),
        stale_child_result_rate=_ratio(
            observation.stale_child_result_count,
            observation.delegation_count,
        ),
        stop_correctness=float(stop_correct) if stop_correct is not None else None,
        no_progress_iteration_rate=_ratio(
            observation.no_progress_iteration_count,
            observation.planning_iteration_count,
        ),
        budget_deadline_stop_correctness=_ratio(
            observation.correct_budget_deadline_stop_count,
            observation.budget_deadline_boundary_count,
        ),
        unnecessary_continuation_rate=unnecessary_continuation,
    )


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _bool_mean(values: list[bool]) -> float | None:
    return sum(values) / len(values) if values else None
