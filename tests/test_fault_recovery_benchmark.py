from packages.evaluation.fault_recovery_status import render_fault_recovery_markdown
from scripts.run_fault_recovery_benchmark import FAULT_CASES


def test_fault_recovery_suite_has_stable_unique_cases() -> None:
    case_ids = [item.case_id for item in FAULT_CASES]
    assert case_ids == [
        "engineering-stale-acquisition-requeue",
        "engineering-outbox-fail-once-retry",
        "engineering-legacy-artifact-replay-recovery",
    ]
    assert len(case_ids) == len(set(case_ids))


def test_fault_recovery_markdown_projects_machine_result() -> None:
    rendered = render_fault_recovery_markdown(
        {
            "benchmark_run_id": "run-1",
            "deployment_revision_id": "deployment:abc",
            "suite_ref": "engineering-fault-recovery@1",
            "success_rate": 1.0,
            "cases": [
                {
                    "case_id": "engineering-stale-acquisition-requeue",
                    "mechanism": "stale -> requeue",
                    "success": True,
                    "diagnostics": {"outbox_count": 1},
                }
            ],
        }
    )
    assert "Fault-recovery success: 100.0%" in rendered
    assert "engineering-stale-acquisition-requeue" in rendered
    assert "`outbox_count=1`" in rendered
