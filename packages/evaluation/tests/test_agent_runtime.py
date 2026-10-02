from packages.evaluation.agent_runtime import (
    AgentCapabilityCall,
    AgentRuntimeGold,
    AgentRuntimeObservation,
    score_agent_runtime,
)


def test_agent_runtime_scorer_separates_quality_failure_chain() -> None:
    score = score_agent_runtime(
        gold=AgentRuntimeGold(
            expected_task_success=True,
            required_capability_ids=["retrieve"],
            allowed_capability_ids=["retrieve", "lookup"],
            expected_argument_digests={"retrieve": ["args-ok"]},
            required_event_types=["evidence_found", "completed"],
            forbidden_event_types=["authority_violation"],
            acceptable_stop_reasons=["evidence_sufficient"],
            expected_continuation=False,
        ),
        observation=AgentRuntimeObservation(
            task_success=True,
            capability_calls=[
                AgentCapabilityCall(capability_id="retrieve", arguments_digest="args-ok")
            ],
            event_types=["evidence_found", "completed"],
            stop_reason="evidence_sufficient",
            wall_latency_seconds=2.0,
            planning_iteration_count=2,
            no_progress_iteration_count=0,
            recoverable_failure_count=1,
            recovered_failure_count=1,
            policy_request_count=1,
            unnecessary_denied_request_count=0,
            critical_evidence_need_count=1,
            critical_evidence_need_recalled_count=1,
            opened_gap_count=1,
            false_gap_count=0,
            acquisition_count=2,
            useful_acquisition_count=1,
            redundant_acquisition_count=1,
            source_role_requirement_count=1,
            source_role_satisfied_count=1,
            freshness_requirement_count=1,
            freshness_satisfied_count=1,
            integrated_assertion_count=2,
            wrong_entity_attachment_count=0,
            version_scoped_assertion_count=1,
            wrong_version_attachment_count=0,
            evidence_ref_assertion_count=2,
            invalid_evidence_ref_count=0,
            conflict_group_count=1,
            collapsed_conflict_count=0,
            delegation_count=1,
            useful_child_task_count=1,
            budget_adherent_child_task_count=1,
            stale_child_result_count=0,
            budget_deadline_boundary_count=1,
            correct_budget_deadline_stop_count=1,
        ),
    )
    assert score.task_success == 1.0
    assert score.capability_selection_correctness == 1.0
    assert score.argument_correctness == 1.0
    assert score.trajectory_conformance == 1.0
    assert score.recovery_success_rate == 1.0
    assert score.redundant_acquisition_rate == 0.5
    assert score.conflict_collapse_rate == 0.0
    assert score.wrong_version_attachment_rate == 0.0
    assert score.stop_correctness == 1.0
    assert score.unnecessary_continuation_rate == 0.0
