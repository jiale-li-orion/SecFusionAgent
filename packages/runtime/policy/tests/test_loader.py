from pathlib import Path

from packages.runtime.policy.contracts import Authorization, PolicyDecisionPoint, PolicyRequest
from packages.runtime.policy.loader import load_runtime_policy


def test_production_policy_catalog_permits_watch_resume_and_denies_other_points() -> None:
    policy = load_runtime_policy(Path("config/runtime-policy.json"))
    permitted = policy.evaluate(
        PolicyRequest(
            decision_point=PolicyDecisionPoint.WATCH_RESUME,
            principal="user:any",
            action="resume_watch",
            resource="case:abc",
            context={
                "task_contract_id": "watch-contract",
                "task_run_id": "watch-run",
            },
        )
    )
    denied = policy.evaluate(
        PolicyRequest(
            decision_point=PolicyDecisionPoint.CAPABILITY_INVOCATION,
            principal="user:any",
            action="read",
            resource="repo:example/project",
            context={
                "task_contract_id": "watch-contract",
                "task_run_id": "watch-run",
            },
        )
    )
    assert permitted.authorization is Authorization.PERMIT
    assert permitted.determining_policy_ids == ["watch-resume-existing-case"]
    assert denied.authorization is Authorization.DENY


def test_production_policy_catalog_permits_task_admission_without_task_run() -> None:
    policy = load_runtime_policy(Path("config/runtime-policy.json"))
    permitted = policy.evaluate(
        PolicyRequest(
            decision_point=PolicyDecisionPoint.TASK_ADMISSION,
            principal="user:test",
            action="admit_verify_version_fix",
            resource="task-kind:verify_version_fix",
            context={
                "intent_ref": "task-intent:test",
                "task_contract_id": "task-contract:test",
            },
        )
    )
    assert permitted.authorization is Authorization.PERMIT
    assert permitted.determining_policy_ids == ["task-admission-canonical-user-system"]
