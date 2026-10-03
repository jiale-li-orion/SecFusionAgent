from __future__ import annotations

from dataclasses import dataclass

from packages.evaluation.benchmark.metrics import CORE_METRICS, metric_definition


@dataclass(frozen=True, slots=True)
class EvaluationMetricGroup:
    group_id: str
    source: str
    owner: str
    purpose: str
    metric_names: tuple[str, ...]
    implementation: str = "contract_only"
    next_denominator: str | None = None


EVALUATION_METRIC_GROUPS: tuple[EvaluationMetricGroup, ...] = (
    EvaluationMetricGroup(
        group_id="m1.competition",
        source="Requirements M1 / competition monitoring performance",
        owner="M1 + M7",
        purpose="coverage and publication-to-available monitoring latency",
        metric_names=(
            "m1.source_category_count",
            "m1.source_delivery_coverage",
            "m1.monitoring.evaluable_coverage",
            "m1.monitoring.p50_seconds",
            "m1.monitoring.p95_seconds",
            "m1.monitoring.max_seconds",
            "m1.monitoring.within_6h_rate",
        ),
        implementation="runner_ready",
    ),
    EvaluationMetricGroup(
        group_id="m6.session",
        source="Requirements M6 multi-turn QA / TD3 session trace",
        owner="M6 + M7",
        purpose=(
            "multi-turn context continuity, target carry and retrieval reuse/invocation behavior"
        ),
        metric_names=(
            "m6.session_context_chain_correctness",
            "m6.session_target_carry_correctness",
            "m6.session_retrieval_overlap_rate",
            "m6.session_retrieval_invocation_coverage",
            "m6.session_retrieval_reuse_rate",
        ),
        implementation="runner_ready",
        next_denominator=(
            "Multi-turn RETRIEVE sessions whose initial and follow-up turns both resolve non-empty "
            "document-chunk refs; empty-result cache reuse does not define retrieval overlap."
        ),
    ),
    EvaluationMetricGroup(
        group_id="m2.diagnostics",
        source="Requirements M2 + M1-M3 Review Addendum",
        owner="M2 + M7",
        purpose="parser, replay, identity, evidence and conflict-preservation diagnostics",
        metric_names=(
            "m2.parser_field_accuracy",
            "m2.replay_suppression_accuracy",
            "m2.entity_resolution_precision",
            "m2.entity_resolution_recall",
            "m2.evidence_correctness",
            "m2.conflict_preservation",
        ),
        implementation="runner_ready",
    ),
    EvaluationMetricGroup(
        group_id="m3.competition",
        source="Requirements M3 / competition enrichment performance",
        owner="M3 + M7",
        purpose="evidence-aware closed-set enrichment quality without dimension masking",
        metric_names=(
            "m3.micro_precision",
            "m3.micro_recall",
            "m3.dimension_macro_precision",
            "m3.dimension_macro_recall",
            "m3.true_positive",
            "m3.false_positive",
            "m3.false_negative",
        ),
        implementation="runner_ready",
    ),
    EvaluationMetricGroup(
        group_id="m6.qa",
        source="Requirements M6 / TD3 sections 19-20",
        owner="M6 + M7",
        purpose="answer, evidence, multi-hop, abstention/conflict, completion and latency",
        metric_names=(
            "m6.answer_accuracy",
            "m6.groundedness",
            "m6.citation_correctness",
            "m6.citation_completeness",
            "m6.multi_hop_correctness",
            "m6.unknown_correctness",
            "m6.conflict_handling",
            "m6.completion_correctness",
            "m6.interactive_latency_seconds",
        ),
        implementation="runner_ready",
    ),
    EvaluationMetricGroup(
        group_id="m6.long_investigation",
        source="Requirements M6 + TD3 latency split",
        owner="M5/M6 + M7",
        purpose="durable long-investigation completion and time-to-final-decision",
        metric_names=(
            "m6.investigation_final_decision_completion",
            "m6.investigation_time_to_first_status_seconds",
            "m6.investigation_time_to_final_decision_seconds",
            "m6.investigation_role_episode_count",
            "m6.investigation_open_need_count_at_measurement",
            "agent.task_success",
        ),
        implementation="runner_ready",
    ),
    EvaluationMetricGroup(
        group_id="m5.requirements_runtime",
        source="Requirements M5 acceptance",
        owner="M5 + M7",
        purpose="task/tool/trajectory/recovery/timeout/latency/cost dimensions stay separate",
        metric_names=(
            "agent.task_success",
            "agent.capability_selection_correctness",
            "agent.argument_correctness",
            "agent.trajectory_conformance",
            "agent.recovery_success_rate",
            "agent.timeout_rate",
            "agent.wall_latency_seconds",
            "runtime.model_provider_cost",
            "runtime.capability_call_count",
        ),
        implementation="runner_ready",
        next_denominator=(
            "Frozen Agent cases that naturally exercise CapabilityBroker selection/arguments and "
            "recoverable failures; monetary cost remains absent until the provider reports it "
            "exactly."
        ),
    ),
    EvaluationMetricGroup(
        group_id="m5.gap_acquisition",
        source="TD3 Agent Runtime Metrics: Gap Identification + Acquisition",
        owner="M5 + M7",
        purpose="whether the Agent asks for and acquires the right missing evidence",
        metric_names=(
            "agent.critical_evidence_need_recall",
            "agent.false_gap_rate",
            "agent.useful_acquisition_precision",
            "agent.redundant_acquisition_rate",
            "agent.source_role_satisfaction",
            "agent.freshness_satisfaction",
        ),
        implementation="runner_ready",
        next_denominator=(
            "Frozen cases where the Agent itself must identify/open a critical EvidenceNeed and "
            "perform an acquisition under pre-frozen source-role and freshness constraints."
        ),
    ),
    EvaluationMetricGroup(
        group_id="m5.state_integration",
        source="TD3 Agent Runtime Metrics: State Integration",
        owner="M4/M5 + M7",
        purpose="wrong target/version/evidence and conflict-collapse diagnosis",
        metric_names=(
            "agent.wrong_entity_attachment_rate",
            "agent.wrong_version_attachment_rate",
            "agent.invalid_evidence_ref_rate",
            "agent.conflict_collapse_rate",
        ),
        implementation="runner_ready",
        next_denominator=(
            "Frozen conflict-bearing Investigation cases whose competing durable assertions are "
            "known before Agent state integration."
        ),
    ),
    EvaluationMetricGroup(
        group_id="m5.planning_tool",
        source="TD3 Agent Runtime Metrics: Planning / Tool",
        owner="M5 + M7",
        purpose="capability/tool choice, arguments, policy denial and fallback behavior",
        metric_names=(
            "agent.capability_selection_correctness",
            "agent.argument_correctness",
            "agent.unnecessary_denied_request_rate",
            "agent.fallback_success_rate",
            "agent.capability_invocation_count",
        ),
        implementation="runner_ready",
        next_denominator=(
            "External-capability Agent cases with pre-frozen acceptable capability ids, canonical "
            "argument digests, policy-denial expectations and primary/fallback binding outcomes."
        ),
    ),
    EvaluationMetricGroup(
        group_id="m5.delegation",
        source="TD3 Agent Runtime Metrics: Delegation",
        owner="M5 + M7",
        purpose="child-task usefulness, budget and freshness discipline",
        metric_names=(
            "agent.delegation_precision",
            "agent.child_task_usefulness",
            "agent.parent_child_budget_adherence",
            "agent.stale_child_result_rate",
        ),
        implementation="runner_ready",
        next_denominator=(
            "Cases where missing evidence legitimately requires child-task delegation; freeze "
            "child usefulness, parent budget ceiling and context-staleness expectations before "
            "execution."
        ),
    ),
    EvaluationMetricGroup(
        group_id="m5.stop",
        source="TD3 Agent Runtime Metrics: Stop",
        owner="M5/M6 + M7",
        purpose="stop/continue correctness and no-progress/budget behavior",
        metric_names=(
            "agent.stop_correctness",
            "agent.no_progress_iteration_rate",
            "agent.budget_deadline_stop_correctness",
            "agent.unnecessary_continuation_rate",
        ),
        implementation="runner_ready",
        next_denominator=(
            "Short-budget/deadline or repeated-no-progress Investigation cases with expected "
            "bounded stop/continue behavior frozen before execution."
        ),
    ),
    EvaluationMetricGroup(
        group_id="runtime.economics",
        source="TD3 sections 8, 9, 20 and 26",
        owner="TD3 measurement",
        purpose="exact model/cache/tool/retrieval execution cost and volume observations",
        metric_names=(
            "runtime.model_attempt_count",
            "runtime.model_input_tokens",
            "runtime.model_output_tokens",
            "runtime.model_reasoning_tokens",
            "runtime.model_cached_input_tokens",
            "runtime.model_provider_cost",
            "runtime.capability_call_count",
            "runtime.capability_external_cost",
            "runtime.retrieval_invocation_count",
        ),
        implementation="runner_ready",
        next_denominator=(
            "Provider responses that expose exact monetary cost plus real CapabilityBroker calls "
            "whose executor reports exact external cost; never infer missing money from price "
            "tables."
        ),
    ),
    EvaluationMetricGroup(
        group_id="retrieval.execution",
        source="Requirements M6 semantic retrieval + M7 regression",
        owner="Retrieval + M7",
        purpose="explain interactive QA latency and physical-plan regressions",
        metric_names=(
            "retrieval.lexical_latency_ms",
            "retrieval.lexical_index_used",
        ),
        implementation="runner_ready",
    ),
    EvaluationMetricGroup(
        group_id="security.hard_gates",
        source="TD3 section 22 controlled runtime hard gates",
        owner="M7 security",
        purpose="controlled authority, secret and policy failures cannot be averaged away",
        metric_names=(
            "security.authority_violation_count",
            "security.secret_exposure_count",
            "security.policy_conformance",
        ),
        implementation="runner_ready",
    ),
    EvaluationMetricGroup(
        group_id="security.adversarial_suite",
        source="Requirements M7 adversarial set",
        owner="M7 security",
        purpose=(
            "breadth and pass-rate of the frozen prompt-injection / privilege / exfiltration "
            "adversarial denominator"
        ),
        metric_names=(
            "security.adversarial_class_coverage",
            "security.adversarial_case_pass_rate",
        ),
        implementation="runner_ready",
    ),
    EvaluationMetricGroup(
        group_id="engineering.recovery",
        source="Requirements M8 / TD3 section 23",
        owner="M8 + M7",
        purpose="controlled failure/recovery behavior",
        metric_names=(
            "engineering.fault_recovery_success",
            "engineering.failure_isolation",
            "engineering.retry_correctness",
            "engineering.bounded_termination",
        ),
        implementation="runner_ready",
    ),
)


def validate_evaluation_metric_contract() -> None:
    missing: list[str] = []
    grouped_metric_names: set[str] = set()
    for group in EVALUATION_METRIC_GROUPS:
        for metric_name in group.metric_names:
            grouped_metric_names.add(metric_name)
            try:
                metric_definition(metric_name)
            except KeyError:
                missing.append(f"{group.group_id}:{metric_name}")
    if missing:
        raise ValueError(
            "evaluation metric contract has unregistered metrics: " + ", ".join(missing)
        )
    unmapped_core_metrics = sorted(set(CORE_METRICS) - grouped_metric_names)
    if unmapped_core_metrics:
        raise ValueError(
            "evaluation metric contract leaves core metrics outside audit groups: "
            + ", ".join(unmapped_core_metrics)
        )
