from __future__ import annotations

from datetime import UTC, datetime

import pytest

from packages.evaluation.m7_replay import (
    M7ReplayService,
    MetricDirection,
    ReplayCase,
    ReplayMetricRule,
    ReplayObservation,
    ReplayVariant,
)
from packages.investigation.replay import (
    ReplayCheckpoint,
    ReplayExpectation,
    ReplayIntervention,
    ReplayInterventionKind,
    ReplayLoopTopology,
    ReplayProtocolResult,
    ReplayRuntimeBinding,
)

NOW = datetime(2026, 9, 27, 22, 0, tzinfo=UTC)


def _checkpoint() -> ReplayCheckpoint:
    return ReplayCheckpoint(
        checkpoint_id="replay-checkpoint:evaluation",
        case_id="case-1",
        snapshot_id="snapshot-1",
        case_revision=4,
        knowledge_revision=17,
        task_run_id="run-1",
        task_contract_ref="contract-1@1",
        context_manifest_ref="context-1@3",
        task_event_seq=6,
        trajectory_id="trajectory-1",
        trajectory_ordinal=9,
        role_ref="InvestigationRole@1",
        runtime=ReplayRuntimeBinding(
            task_run_id="run-1",
            execution_envelope_ref="execution:run-1",
            execution_profile="VERIFY",
            policy_revision="policy-v1",
            capability_scope=["evidence.read", "graph.read"],
            identity_scope=["public"],
            network_policy="proxied",
            side_effect_policy="internal-state",
            sandbox_profile_revision="process_restricted@1",
            budget_ref="budget:run-1",
            budget_limits={"agent_turns": "8", "tool_calls": "4"},
            budget_reserved={"agent_turns": "1"},
        ),
        capability_registry_revision="cap-v4",
        model_revision="model-v3",
        prompt_assembly_revision="prompt-v5",
        skill_refs=["skill:investigation.verify_fix_boundary@1"],
        source_availability_snapshot={"github": "available"},
        loop_topology=ReplayLoopTopology.MULTI_LOOP_DELEGATED,
        context_handoff_mode="reference",
        created_at=NOW,
    )


class _Executor:
    def __init__(self, payloads: dict[str, dict[str, object]]) -> None:
        self._payloads = payloads

    async def execute(self, replay_case: ReplayCase, variant: ReplayVariant) -> ReplayObservation:
        payload = self._payloads[variant.variant_id]
        metrics = payload.get("metrics", {})
        protocol_failures = payload.get("protocol_failures", [])
        assert isinstance(metrics, dict)
        assert isinstance(protocol_failures, list)
        return ReplayObservation(
            replay_case_id=replay_case.replay_case_id,
            freeze_hash=str(payload.get("freeze_hash", replay_case.freeze_hash)),
            variant_id=variant.variant_id,
            protocol=ReplayProtocolResult(
                passed=bool(payload.get("protocol_passed", True)),
                failures=[str(item) for item in protocol_failures],
            ),
            expected_domain_outcome_met=bool(payload.get("domain_passed", True)),
            metrics={key: float(value) for key, value in metrics.items()},
        )


@pytest.mark.asyncio
async def test_m7_compare_detects_regression_under_same_frozen_checkpoint() -> None:
    replay_case = ReplayCase(
        replay_case_id="replay-case:fix-boundary",
        source_ref="trajectory:counterexample-1",
        checkpoint=_checkpoint(),
        expectation=ReplayExpectation(expected_task_status="completed"),
        metric_rules=[
            ReplayMetricRule(
                metric="unsupported_claims",
                direction=MetricDirection.LOWER_IS_BETTER,
            ),
            ReplayMetricRule(
                metric="evidence_use_score",
                direction=MetricDirection.HIGHER_IS_BETTER,
                tolerance=0.01,
            ),
        ],
    )
    candidate = ReplayVariant(
        variant_id="summary-handoff",
        intervention=ReplayIntervention(
            kind=ReplayInterventionKind.CONTEXT_HANDOFF,
            replacement="summary",
            rationale="reference-vs-summary ablation",
        ),
    )
    report = await M7ReplayService().compare(
        cases=[replay_case],
        executor=_Executor(
            {
                "baseline": {"metrics": {"unsupported_claims": 0, "evidence_use_score": 0.9}},
                "summary-handoff": {
                    "metrics": {"unsupported_claims": 1, "evidence_use_score": 0.85}
                },
            }
        ),
        candidate_variant=candidate,
    )

    assert report.passed is False
    assert report.comparisons[0].freeze_hash == replay_case.freeze_hash
    assert report.comparisons[0].regression_reasons == [
        "metric_regression:unsupported_claims:0.0->1.0",
        "metric_regression:evidence_use_score:0.9->0.85",
    ]


@pytest.mark.asyncio
async def test_m7_compare_rejects_executor_freeze_drift() -> None:
    replay_case = ReplayCase(
        replay_case_id="replay-case:freeze",
        source_ref="trajectory:freeze",
        checkpoint=_checkpoint(),
    )
    candidate = ReplayVariant(
        variant_id="policy-v2",
        intervention=ReplayIntervention(
            kind=ReplayInterventionKind.POLICY,
            replacement="policy-v2",
            rationale="policy intervention",
        ),
    )
    with pytest.raises(ValueError, match="changed frozen"):
        await M7ReplayService().compare(
            cases=[replay_case],
            executor=_Executor(
                {
                    "baseline": {"freeze_hash": "not-the-checkpoint"},
                    "policy-v2": {},
                }
            ),
            candidate_variant=candidate,
        )


@pytest.mark.asyncio
async def test_m7_candidate_must_contain_an_explicit_single_intervention() -> None:
    replay_case = ReplayCase(
        replay_case_id="replay-case:baseline-only",
        source_ref="trajectory:baseline-only",
        checkpoint=_checkpoint(),
    )
    with pytest.raises(ValueError, match="requires exactly one intervention"):
        await M7ReplayService().compare(
            cases=[replay_case],
            executor=_Executor({"baseline": {}}),
            candidate_variant=ReplayVariant(variant_id="candidate-without-intervention"),
        )
