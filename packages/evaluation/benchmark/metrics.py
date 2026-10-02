from __future__ import annotations

import json
from enum import StrEnum
from hashlib import sha256

from pydantic import BaseModel

from packages.evaluation.benchmark.contracts import MetricDirection


class MetricAggregation(StrEnum):
    MEAN = "mean"
    SUM = "sum"
    MIN = "min"
    MAX = "max"
    P50 = "p50"
    P95 = "p95"
    LAST = "last"
    DERIVED = "derived"


class MissingValuePolicy(StrEnum):
    EXCLUDE = "exclude"
    FAIL = "fail"
    NOT_EVALUATED = "not_evaluated"


class MetricDefinition(BaseModel):
    name: str
    revision: str
    denominator: str
    aggregation: MetricAggregation
    missing_value_policy: MissingValuePolicy
    direction: MetricDirection
    unit: str | None = None

    @property
    def ref(self) -> str:
        return f"{self.name}@{self.revision}"

    @property
    def digest(self) -> str:
        return sha256(
            json.dumps(
                self.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()


CORE_METRICS: dict[str, MetricDefinition] = {
    item.name: item
    for item in (
        MetricDefinition(
            name="m1.source_category_count",
            revision="1",
            denominator="fixed eight-category product source taxonomy",
            aggregation=MetricAggregation.LAST,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="categories",
        ),
        MetricDefinition(
            name="m1.source_delivery_coverage",
            revision="1",
            denominator="frozen expected source delivery keys",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="engineering.failure_isolation",
            revision="1",
            denominator="controlled fault cases with an explicit unrelated-state sentinel",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="engineering.retry_correctness",
            revision="1",
            denominator="controlled fault cases whose expected behavior includes retry semantics",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="engineering.bounded_termination",
            revision="1",
            denominator="controlled fault cases with an expected bounded terminal outcome",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m3.dimension_macro_precision",
            revision="1",
            denominator="enrichment dimensions present in the frozen scored denominator",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m3.dimension_macro_recall",
            revision="1",
            denominator="enrichment dimensions present in the frozen scored denominator",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m6.session_retrieval_overlap_rate",
            revision="1",
            denominator="follow-up RETRIEVE turns with non-empty document-chunk refs",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.INFORMATIONAL,
            unit="ratio",
        ),
        MetricDefinition(
            name="m6.session_retrieval_invocation_coverage",
            revision="1",
            denominator="follow-up RETRIEVE turns in a QASessionCase",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m6.session_retrieval_reuse_rate",
            revision="1",
            denominator="follow-up RETRIEVE turns with one durable retrieval invocation",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.INFORMATIONAL,
            unit="ratio",
        ),
        MetricDefinition(
            name="m6.citation_completeness",
            revision="1",
            denominator="factual conclusions requiring citation coverage",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m1.monitoring.evaluable_coverage",
            revision="1",
            denominator="all monitoring latency samples in the frozen window",
            aggregation=MetricAggregation.LAST,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m1.monitoring.p50_seconds",
            revision="1",
            denominator="latency-evaluable samples only",
            aggregation=MetricAggregation.LAST,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="seconds",
        ),
        MetricDefinition(
            name="m6.investigation_time_to_first_status_seconds",
            revision="1",
            denominator="long-investigation cases with a durable post-acceptance status event",
            aggregation=MetricAggregation.P95,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="seconds",
        ),
        MetricDefinition(
            name="m6.unknown_correctness",
            revision="1",
            denominator="QA cases with adjudicated unknown/abstention behavior",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.EXCLUDE,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m6.conflict_handling",
            revision="1",
            denominator="QA cases with adjudicated source conflicts",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.EXCLUDE,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m6.completion_correctness",
            revision="1",
            denominator="frozen QA cases with expected DIRECT/ANSWER/CONTINUE behavior",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m1.monitoring.p95_seconds",
            revision="1",
            denominator="latency-evaluable samples only",
            aggregation=MetricAggregation.LAST,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="seconds",
        ),
        MetricDefinition(
            name="m1.monitoring.max_seconds",
            revision="1",
            denominator="latency-evaluable samples only",
            aggregation=MetricAggregation.LAST,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="seconds",
        ),
        MetricDefinition(
            name="m1.monitoring.within_6h_rate",
            revision="1",
            denominator="latency-evaluable samples only",
            aggregation=MetricAggregation.LAST,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m3.micro_precision",
            revision="1",
            denominator="evidence-aware closed-set predicted facts",
            aggregation=MetricAggregation.DERIVED,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m3.micro_recall",
            revision="1",
            denominator="evidence-aware closed-set gold facts",
            aggregation=MetricAggregation.DERIVED,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m3.true_positive",
            revision="1",
            denominator="evidence-aware closed-set facts",
            aggregation=MetricAggregation.SUM,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.INFORMATIONAL,
            unit="facts",
        ),
        MetricDefinition(
            name="m3.false_positive",
            revision="1",
            denominator="evidence-aware closed-set facts",
            aggregation=MetricAggregation.SUM,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="facts",
        ),
        MetricDefinition(
            name="m3.false_negative",
            revision="1",
            denominator="evidence-aware closed-set facts",
            aggregation=MetricAggregation.SUM,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="facts",
        ),
        MetricDefinition(
            name="m6.answer_accuracy",
            revision="1",
            denominator="frozen QA cases with adjudicated answer gold",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m6.groundedness",
            revision="1",
            denominator="factual conclusions requiring evidence",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m6.citation_correctness",
            revision="1",
            denominator="answer citations checked against supporting evidence",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m6.multi_hop_correctness",
            revision="1",
            denominator="QA cases requiring adjudicated intermediate relation paths",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m6.interactive_latency_seconds",
            revision="1",
            denominator="interactive QA cases only; long investigations excluded",
            aggregation=MetricAggregation.P95,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="seconds",
        ),
        MetricDefinition(
            name="m6.investigation_final_decision_completion",
            revision="1",
            denominator="frozen long-investigation cases measured for final M6 decision outcome",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m6.investigation_time_to_final_decision_seconds",
            revision="1",
            denominator="long-investigation cases that reached a durable M4 DecisionCommit",
            aggregation=MetricAggregation.P95,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="seconds",
        ),
        MetricDefinition(
            name="m6.investigation_role_episode_count",
            revision="1",
            denominator="frozen long-investigation cases",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.INFORMATIONAL,
            unit="episodes",
        ),
        MetricDefinition(
            name="m6.investigation_open_need_count_at_measurement",
            revision="1",
            denominator="frozen long-investigation cases at completion measurement time",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.INFORMATIONAL,
            unit="needs",
        ),
        MetricDefinition(
            name="m6.session_context_chain_correctness",
            revision="1",
            denominator="live Product QA session cases with at least two turns",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m6.session_target_carry_correctness",
            revision="1",
            denominator="follow-up turns with frozen expected canonical target keys",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.task_success",
            revision="1",
            denominator="frozen Agent benchmark case runs",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        # Requirements M2 diagnostics. These definitions make the frozen metric
        # contract executable even where the first real denominator is still pending.
        MetricDefinition(
            name="m2.parser_field_accuracy",
            revision="1",
            denominator="frozen parser field assertions with value and locator gold",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m2.replay_suppression_accuracy",
            revision="1",
            denominator="frozen replay cases with expected duplicate suppression behavior",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m2.entity_resolution_precision",
            revision="1",
            denominator="predicted same-entity bindings in a frozen identity-pair set",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m2.entity_resolution_recall",
            revision="1",
            denominator="gold same-entity bindings in a frozen identity-pair set",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m2.evidence_correctness",
            revision="1",
            denominator=(
                "accepted claim/relation assertions checked against frozen EvidenceRef support"
            ),
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m2.conflict_preservation",
            revision="1",
            denominator=(
                "frozen source-conflict cases whose competing assertions must remain represented"
            ),
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        # TD3 Agent diagnostics. Quality metrics require an explicit frozen gold
        # denominator; operational counters can be emitted directly from durable traces.
        MetricDefinition(
            name="agent.critical_evidence_need_recall",
            revision="1",
            denominator="adjudicated critical EvidenceNeeds in frozen Agent cases",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.false_gap_rate",
            revision="1",
            denominator="EvidenceNeeds opened by the Agent in adjudicated frozen cases",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.useful_acquisition_precision",
            revision="1",
            denominator="Agent acquisition actions in adjudicated frozen cases",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.redundant_acquisition_rate",
            revision="1",
            denominator="Agent acquisition actions in frozen cases",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.source_role_satisfaction",
            revision="1",
            denominator="frozen EvidenceNeeds with required source-role constraints",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.freshness_satisfaction",
            revision="1",
            denominator="frozen EvidenceNeeds with explicit freshness constraints",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.wrong_entity_attachment_rate",
            revision="1",
            denominator="Agent-integrated facts/relations with adjudicated target identity",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.wrong_version_attachment_rate",
            revision="2",
            denominator=(
                "Agent-integrated version-scoped assertions whose reasoning support is checked "
                "against prospectively frozen typed relation/claim support for the adjudicated "
                "version boundary"
            ),
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.invalid_evidence_ref_rate",
            revision="1",
            denominator="Agent-integrated assertions carrying EvidenceRefs",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.conflict_collapse_rate",
            revision="1",
            denominator="adjudicated conflicting assertion groups encountered by Agent cases",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.capability_selection_correctness",
            revision="1",
            denominator="tool-selection decisions with adjudicated acceptable capability set",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.argument_correctness",
            revision="1",
            denominator="capability invocations with adjudicated argument expectations",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.unnecessary_denied_request_rate",
            revision="1",
            denominator="Agent capability requests evaluated by policy in frozen cases",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.fallback_success_rate",
            revision="1",
            denominator="Agent tool/provider actions that entered an adjudicated fallback path",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.delegation_precision",
            revision="1",
            denominator="Agent child-task delegations with adjudicated usefulness",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.child_task_usefulness",
            revision="1",
            denominator="completed delegated child tasks in frozen Agent cases",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.parent_child_budget_adherence",
            revision="1",
            denominator="delegated child tasks with inherited budget envelopes",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.stale_child_result_rate",
            revision="1",
            denominator="child-task results returned to a parent execution",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.stop_correctness",
            revision="1",
            denominator="Agent stop/continue decisions with adjudicated expected behavior",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.no_progress_iteration_rate",
            revision="1",
            denominator="Agent planning iterations in frozen cases",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.budget_deadline_stop_correctness",
            revision="1",
            denominator="Agent cases reaching a frozen budget/deadline boundary",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.unnecessary_continuation_rate",
            revision="1",
            denominator="Agent/M6 continuation decisions with adjudicated answerability gold",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.trajectory_conformance",
            revision="1",
            denominator="frozen Agent cases with required/forbidden trajectory expectations",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.timeout_rate",
            revision="1",
            denominator="Agent TaskRun/Execution episodes in frozen cases",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.recovery_success_rate",
            revision="1",
            denominator=(
                "Agent episodes that encountered a recoverable runtime/provider/tool failure"
            ),
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.wall_latency_seconds",
            revision="1",
            denominator="frozen Agent cases with a durable start and terminal time",
            aggregation=MetricAggregation.P95,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="seconds",
        ),
        MetricDefinition(
            name="agent.capability_invocation_count",
            revision="1",
            denominator="frozen Agent case runs",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.INFORMATIONAL,
            unit="calls",
        ),
        MetricDefinition(
            name="runtime.capability_external_cost",
            revision="1",
            denominator="benchmark case runs whose capability results expose exact external cost",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="provider_currency",
        ),
        # Cross-cutting execution economics required by TD3 M6/M5 cost reporting.
        MetricDefinition(
            name="runtime.model_attempt_count",
            revision="1",
            denominator="benchmark case runs with recorded model execution",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.INFORMATIONAL,
            unit="attempts",
        ),
        MetricDefinition(
            name="runtime.model_input_tokens",
            revision="1",
            denominator="benchmark case runs with provider/tokenizer model usage",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.INFORMATIONAL,
            unit="tokens",
        ),
        MetricDefinition(
            name="runtime.model_output_tokens",
            revision="1",
            denominator="benchmark case runs with provider/tokenizer model usage",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.INFORMATIONAL,
            unit="tokens",
        ),
        MetricDefinition(
            name="runtime.model_reasoning_tokens",
            revision="1",
            denominator="benchmark case runs with provider-reported reasoning-token usage",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.INFORMATIONAL,
            unit="tokens",
        ),
        MetricDefinition(
            name="runtime.model_cached_input_tokens",
            revision="1",
            denominator="benchmark case runs with provider-reported cached-input usage",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.INFORMATIONAL,
            unit="tokens",
        ),
        MetricDefinition(
            name="runtime.model_provider_cost",
            revision="1",
            denominator="benchmark case runs with provider-reported monetary cost",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="provider_currency",
        ),
        MetricDefinition(
            name="runtime.capability_call_count",
            revision="1",
            denominator="benchmark case runs with durable capability invocations",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.INFORMATIONAL,
            unit="calls",
        ),
        MetricDefinition(
            name="runtime.retrieval_invocation_count",
            revision="1",
            denominator="benchmark case runs with durable retrieval invocation provenance",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.INFORMATIONAL,
            unit="calls",
        ),
        # Retrieval execution diagnostics explain QA latency but are not direct
        # competition target checks.
        MetricDefinition(
            name="retrieval.lexical_latency_ms",
            revision="1",
            denominator="fixed lexical retrieval benchmark queries",
            aggregation=MetricAggregation.P95,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="milliseconds",
        ),
        MetricDefinition(
            name="retrieval.lexical_index_used",
            revision="1",
            denominator="fixed lexical retrieval benchmark queries with EXPLAIN plan inspection",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        # Security hard gates from TD3 section 22. Real adversarial denominators
        # remain separate suites; absence of a run stays NOT_EVALUATED.
        MetricDefinition(
            name="security.authority_violation_count",
            revision="1",
            denominator="frozen security benchmark case runs",
            aggregation=MetricAggregation.SUM,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.TARGET_ZERO,
            unit="violations",
        ),
        MetricDefinition(
            name="security.secret_exposure_count",
            revision="1",
            denominator="frozen security benchmark case runs",
            aggregation=MetricAggregation.SUM,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.TARGET_ZERO,
            unit="exposures",
        ),
        MetricDefinition(
            name="security.policy_conformance",
            revision="1",
            denominator="frozen security cases with required/forbidden policy outcomes",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="security.adversarial_class_coverage",
            revision="1",
            denominator="required adversarial classes in the frozen M7 security profile",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="security.adversarial_case_pass_rate",
            revision="1",
            denominator="executed cases in the frozen M7 adversarial security suite",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="engineering.fault_recovery_success",
            revision="1",
            denominator="frozen fault-injection cases",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
    )
}


def metric_definition(name: str) -> MetricDefinition:
    exact = CORE_METRICS.get(name)
    if exact is not None:
        return exact
    if name.startswith("m3.dimension."):
        suffix = name.rsplit(".", 1)[-1]
        if suffix in {"precision", "recall"}:
            return MetricDefinition(
                name=name,
                revision="1",
                denominator="closed-set facts in the named enrichment dimension",
                aggregation=MetricAggregation.MEAN,
                missing_value_policy=MissingValuePolicy.EXCLUDE,
                direction=MetricDirection.HIGHER_IS_BETTER,
                unit="ratio",
            )
        if suffix in {"true_positive", "false_positive", "false_negative"}:
            return MetricDefinition(
                name=name,
                revision="1",
                denominator="closed-set facts in the named enrichment dimension",
                aggregation=MetricAggregation.SUM,
                missing_value_policy=MissingValuePolicy.EXCLUDE,
                direction=(
                    MetricDirection.INFORMATIONAL
                    if suffix == "true_positive"
                    else MetricDirection.LOWER_IS_BETTER
                ),
                unit="facts",
            )
    raise KeyError(f"metric definition is not registered: {name}")
