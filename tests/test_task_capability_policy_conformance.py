from __future__ import annotations

from datetime import UTC, datetime

import pytest

from packages.runtime.capability.contracts import (
    CapabilityContract,
    CapabilityRequest,
    EffectSemantics,
    capability_visible_for_task,
    validate_capability_request,
)
from packages.runtime.policy.contracts import (
    Authorization,
    PolicyDecision,
    PolicyObligation,
    combine_deny_overrides,
    obligations_satisfied,
)
from packages.task_runtime.contracts.conformance import validate_child_contract
from packages.task_runtime.contracts.models import (
    TASK_RUN_TRANSITIONS,
    DelegationCeiling,
    EffectCeiling,
    TaskContract,
    TaskKind,
    TaskRunStatus,
    can_transition_task_run,
)
from packages.task_runtime.contracts.roles import canonical_roles


def _task(
    *,
    task_id: str = "task-parent",
    kind: TaskKind = TaskKind.VERIFY_VERSION_FIX,
    effect: EffectCeiling = EffectCeiling.READ_ONLY,
    delegation: DelegationCeiling | None = None,
    principal: str = "user:alice",
) -> TaskContract:
    return TaskContract(
        task_contract_id=task_id,
        contract_revision=1,
        principal=principal,
        task_kind=kind,
        target_resources=["repo:vllm-project/vllm"],
        desired_state={"predicate": "fix_boundary_resolved"},
        evidence_contract={"source_roles": ["primary"]},
        output_contract={"format": "decision"},
        temporal_contract={"freshness": "current"},
        effect_ceiling=effect,
        delegation_ceiling=delegation or DelegationCeiling(),
        completion_predicate={"any": ["evidence_sufficient", "conflict", "blocked"]},
        policy_revision="policy-v1",
    )


def _capability(
    *,
    capability_id: str = "github.read_release",
    action: str = "read",
    effect: EffectSemantics = EffectSemantics.OBSERVATION,
    resource_types: list[str] | None = None,
) -> CapabilityContract:
    return CapabilityContract(
        capability_id=capability_id,
        contract_revision=1,
        action=action,
        applicable_resource_types=resource_types or ["github.release"],
        observation_semantics="provider_observation",
        effect_semantics=effect,
        authority_semantics=["primary_for(repository_release_state)"],
        idempotency="safe",
        reversibility="not_applicable",
        data_ingress_class="public",
        data_egress_class="none",
        failure_semantics=["provider_blocked", "rate_limited", "not_found"],
        risk_class="low",
    )


def _request(
    task: TaskContract,
    capability: CapabilityContract,
    **updates: object,
) -> CapabilityRequest:
    values: dict[str, object] = {
        "request_id": "req-1",
        "task_contract_id": task.task_contract_id,
        "task_run_id": "run-1",
        "principal": task.principal,
        "capability_id": capability.capability_id,
        "contract_revision": capability.contract_revision,
        "action": capability.action,
        "resource": "repo:vllm-project/vllm:release:v0.21.0",
        "resource_type": "github.release",
        "canonical_arguments": {"repo": "vllm-project/vllm", "tag": "v0.21.0"},
        "intended_effect": capability.effect_semantics,
        "evidence_purpose": "verify_fix_boundary",
        "execution_context": {"world_revision": 42},
    }
    values.update(updates)
    return CapabilityRequest.model_validate(values)


@pytest.mark.parametrize(
    ("current", "target", "expected"),
    [
        (TaskRunStatus.SUBMITTED, TaskRunStatus.QUEUED, True),
        (TaskRunStatus.SUBMITTED, TaskRunStatus.CANCELLED, True),
        (TaskRunStatus.QUEUED, TaskRunStatus.RUNNING, True),
        (TaskRunStatus.QUEUED, TaskRunStatus.TIMED_OUT, True),
        (TaskRunStatus.RUNNING, TaskRunStatus.WAITING_INPUT, True),
        (TaskRunStatus.RUNNING, TaskRunStatus.WAITING_DEPENDENCY, True),
        (TaskRunStatus.RUNNING, TaskRunStatus.COMPLETED, True),
        (TaskRunStatus.RUNNING, TaskRunStatus.FAILED, True),
        (TaskRunStatus.WAITING_INPUT, TaskRunStatus.QUEUED, True),
        (TaskRunStatus.WAITING_DEPENDENCY, TaskRunStatus.QUEUED, True),
        (TaskRunStatus.COMPLETED, TaskRunStatus.RUNNING, False),
        (TaskRunStatus.FAILED, TaskRunStatus.RUNNING, False),
        (TaskRunStatus.CANCELLED, TaskRunStatus.QUEUED, False),
        (TaskRunStatus.TIMED_OUT, TaskRunStatus.RUNNING, False),
        (TaskRunStatus.BLOCKED, TaskRunStatus.RUNNING, False),
        (TaskRunStatus.SUBMITTED, TaskRunStatus.COMPLETED, False),
    ],
)
def test_task_run_transition_conformance(
    current: TaskRunStatus,
    target: TaskRunStatus,
    expected: bool,
) -> None:
    assert can_transition_task_run(current, target) is expected


def test_task_run_transition_table_covers_closed_status_set() -> None:
    assert set(TASK_RUN_TRANSITIONS) == set(TaskRunStatus)


@pytest.mark.parametrize(
    ("ceiling", "effect", "visible"),
    [
        (EffectCeiling.READ_ONLY, EffectSemantics.OBSERVATION, True),
        (EffectCeiling.READ_ONLY, EffectSemantics.INTERNAL_STATE, False),
        (EffectCeiling.READ_ONLY, EffectSemantics.EXTERNAL_SIDE_EFFECT, False),
        (EffectCeiling.INTERNAL_STATE, EffectSemantics.OBSERVATION, True),
        (EffectCeiling.INTERNAL_STATE, EffectSemantics.INTERNAL_STATE, True),
        (EffectCeiling.INTERNAL_STATE, EffectSemantics.EXTERNAL_SIDE_EFFECT, False),
        (EffectCeiling.EXTERNAL_SIDE_EFFECT, EffectSemantics.OBSERVATION, True),
        (EffectCeiling.EXTERNAL_SIDE_EFFECT, EffectSemantics.INTERNAL_STATE, True),
        (EffectCeiling.EXTERNAL_SIDE_EFFECT, EffectSemantics.EXTERNAL_SIDE_EFFECT, True),
    ],
)
def test_capability_visibility_respects_effect_ceiling(
    ceiling: EffectCeiling,
    effect: EffectSemantics,
    visible: bool,
) -> None:
    assert capability_visible_for_task(_task(effect=ceiling), _capability(effect=effect)) is visible


@pytest.mark.parametrize(
    ("updates", "expected_error"),
    [
        ({}, None),
        ({"task_contract_id": "other"}, "task_contract_mismatch"),
        ({"principal": "user:bob"}, "principal_mismatch"),
        ({"capability_id": "other"}, "capability_id_mismatch"),
        ({"contract_revision": 2}, "capability_revision_mismatch"),
        ({"action": "write"}, "action_mismatch"),
        ({"resource_type": "github.issue"}, "resource_type_not_applicable"),
        ({"intended_effect": EffectSemantics.INTERNAL_STATE}, "intended_effect_mismatch"),
    ],
)
def test_argument_bound_capability_request_conformance(
    updates: dict[str, object],
    expected_error: str | None,
) -> None:
    task = _task()
    capability = _capability()
    errors = validate_capability_request(task, capability, _request(task, capability, **updates))
    if expected_error is None:
        assert errors == []
    else:
        assert expected_error in errors


def test_argument_bound_request_can_be_visible_but_invalid_at_invocation() -> None:
    task = _task()
    capability = _capability()
    assert capability_visible_for_task(task, capability) is True
    request = _request(task, capability, resource_type="github.issue")
    assert "resource_type_not_applicable" in validate_capability_request(task, capability, request)


@pytest.mark.parametrize(
    ("child_kind", "child_effect", "child_delegates", "expected", "reason"),
    [
        (TaskKind.ENRICHMENT, EffectCeiling.READ_ONLY, False, True, None),
        (
            TaskKind.ENRICHMENT,
            EffectCeiling.INTERNAL_STATE,
            False,
            False,
            "exceeds_parent_effect_ceiling",
        ),
        (
            TaskKind.INVESTIGATE_INCIDENT,
            EffectCeiling.READ_ONLY,
            False,
            False,
            "child_task_kind_not_allowed",
        ),
        (
            TaskKind.ENRICHMENT,
            EffectCeiling.READ_ONLY,
            True,
            False,
            "exceeds_parent_delegation_ceiling",
        ),
    ],
)
def test_parent_child_delegation_conformance(
    child_kind: TaskKind,
    child_effect: EffectCeiling,
    child_delegates: bool,
    expected: bool,
    reason: str | None,
) -> None:
    parent = _task(
        delegation=DelegationCeiling(
            allowed=True,
            max_depth=1,
            allowed_task_kinds=[TaskKind.ENRICHMENT],
            child_effect_ceiling=EffectCeiling.READ_ONLY,
        )
    )
    child_delegation = (
        DelegationCeiling(
            allowed=True,
            max_depth=1,
            allowed_task_kinds=[TaskKind.ENRICHMENT],
            child_effect_ceiling=EffectCeiling.READ_ONLY,
        )
        if child_delegates
        else DelegationCeiling()
    )
    child = _task(
        task_id="task-child",
        kind=child_kind,
        effect=child_effect,
        delegation=child_delegation,
    )
    result = validate_child_contract(parent, child)
    assert result.allowed is expected
    assert result.reason == reason


def test_delegation_denied_when_parent_disallows_children() -> None:
    result = validate_child_contract(_task(), _task(task_id="child", kind=TaskKind.ENRICHMENT))
    assert result.allowed is False
    assert result.reason == "delegation_not_allowed"


@pytest.mark.parametrize(
    ("role_id", "task_kind", "expected"),
    [
        ("EnrichmentRole", TaskKind.ENRICHMENT, True),
        ("EnrichmentRole", TaskKind.VERIFY_VERSION_FIX, False),
        ("EnrichmentRole", TaskKind.INVESTIGATE_INCIDENT, False),
        ("InvestigationRole", TaskKind.VERIFY_VERSION_FIX, True),
        ("InvestigationRole", TaskKind.RESOLVE_CONFLICT, True),
        ("InvestigationRole", TaskKind.INVESTIGATE_RELATION, True),
        ("InvestigationRole", TaskKind.INVESTIGATE_INCIDENT, True),
        ("InvestigationRole", TaskKind.WATCH_INCIDENT, True),
        ("InvestigationRole", TaskKind.ENRICHMENT, False),
        ("InvestigationRole", TaskKind.LOOKUP, False),
    ],
)
def test_role_acceptance_conformance(role_id: str, task_kind: TaskKind, expected: bool) -> None:
    assert canonical_roles()[role_id].accepts(task_kind) is expected


def _decision(
    authorization: Authorization,
    policy_id: str,
    *,
    obligations: list[PolicyObligation] | None = None,
) -> PolicyDecision:
    return PolicyDecision(
        authorization=authorization,
        obligations=obligations or [],
        matched_policy_ids=[policy_id],
        determining_policy_ids=[policy_id],
        policy_revision="policy-v1",
    )


def test_policy_deny_overrides_permit() -> None:
    combined = combine_deny_overrides(
        [
            _decision(Authorization.PERMIT, "allow-read"),
            _decision(Authorization.DENY, "deny-private-repo"),
        ],
        policy_revision="policy-v1",
    )
    assert combined.authorization is Authorization.DENY
    assert combined.determining_policy_ids == ["deny-private-repo"]


def test_policy_implicit_deny_without_permit() -> None:
    combined = combine_deny_overrides([], policy_revision="policy-v1")
    assert combined.authorization is Authorization.DENY
    assert combined.advice == ["implicit_deny"]


def test_policy_indeterminate_remains_fail_closed_signal() -> None:
    combined = combine_deny_overrides(
        [_decision(Authorization.INDETERMINATE, "provider-policy-error")],
        policy_revision="policy-v1",
    )
    assert combined.authorization is Authorization.INDETERMINATE
    assert obligations_satisfied(combined, fulfilled_obligation_kinds=set()) is False


def test_policy_permit_collects_obligations() -> None:
    combined = combine_deny_overrides(
        [
            _decision(
                Authorization.PERMIT,
                "sandbox-policy",
                obligations=[PolicyObligation(kind="sandbox_min", parameters={"class": "process"})],
            ),
            _decision(
                Authorization.PERMIT,
                "audit-policy",
                obligations=[PolicyObligation(kind="require_audit_log")],
            ),
        ],
        policy_revision="policy-v1",
    )
    assert combined.authorization is Authorization.PERMIT
    assert {item.kind for item in combined.obligations} == {"sandbox_min", "require_audit_log"}
    assert (
        obligations_satisfied(
            combined,
            fulfilled_obligation_kinds={"sandbox_min", "require_audit_log"},
        )
        is True
    )
    assert obligations_satisfied(combined, fulfilled_obligation_kinds={"sandbox_min"}) is False


def test_policy_decision_expiry_is_data_not_authorization_side_channel() -> None:
    decision = PolicyDecision(
        authorization=Authorization.PERMIT,
        policy_revision="policy-v1",
        expires_at=datetime(2026, 9, 27, 2, 0, tzinfo=UTC),
    )
    assert decision.authorization is Authorization.PERMIT
    assert decision.expires_at is not None


def test_child_execution_envelope_cannot_extend_parent_grant() -> None:
    from packages.task_runtime.contracts.execution import (
        ExecutionEnvelope,
        validate_child_execution_envelope,
    )
    from packages.task_runtime.contracts.models import ExecutionProfile

    parent = ExecutionEnvelope(
        execution_id="exec-parent",
        task_contract_id="task-parent",
        task_run_id="run-parent",
        role_revision="InvestigationRole@1",
        context_manifest_revision=1,
        execution_profile=ExecutionProfile.INVESTIGATE,
        capability_scope=["github.read", "osv.query"],
        deadline_at=datetime(2026, 9, 27, 3, 0, tzinfo=UTC),
        budget_ref="budget:parent",
        policy_revision="policy-v1",
        identity_scope=["github:public", "osv:public"],
        network_policy="network:parent",
        side_effect_policy="read-only",
        sandbox_profile_revision="container_standard@1",
    )
    child = parent.model_copy(
        update={
            "execution_id": "exec-child",
            "parent_execution_id": "exec-parent",
            "task_contract_id": "task-child",
            "task_run_id": "run-child",
            "capability_scope": ["github.read", "shell.exec"],
            "identity_scope": ["github:public"],
            "deadline_at": datetime(2026, 9, 27, 4, 0, tzinfo=UTC),
        }
    )
    assert validate_child_execution_envelope(parent, child) == [
        "child_deadline_exceeds_parent",
        "child_capability_scope_exceeds_parent",
    ]


def test_action_timeout_is_bounded_by_absolute_execution_deadline() -> None:
    from packages.task_runtime.contracts.execution import ExecutionEnvelope, bounded_timeout_seconds
    from packages.task_runtime.contracts.models import ExecutionProfile

    envelope = ExecutionEnvelope(
        execution_id="exec-1",
        task_contract_id="task-1",
        task_run_id="run-1",
        role_revision="InvestigationRole@1",
        context_manifest_revision=1,
        execution_profile=ExecutionProfile.VERIFY,
        deadline_at=datetime(2026, 9, 27, 2, 0, 10, tzinfo=UTC),
        budget_ref="budget:1",
        policy_revision="policy-v1",
        network_policy="deny",
        side_effect_policy="read-only",
        sandbox_profile_revision="process_restricted@1",
    )
    assert (
        bounded_timeout_seconds(
            envelope,
            now=datetime(2026, 9, 27, 2, 0, 0, tzinfo=UTC),
            action_timeout_seconds=60,
        )
        == 10
    )


def test_microvm_sandbox_fails_closed_when_firecracker_is_unavailable() -> None:
    from packages.runtime.sandbox.contracts import IsolationClass, select_sandbox_profile

    selection = select_sandbox_profile(
        IsolationClass.MICROVM_UNTRUSTED,
        available_backends={"openshell", "docker"},
    )
    assert selection.available is False
    assert selection.profile is None
    assert selection.reason == "sandbox_unavailable"


def test_container_sandbox_requires_supervisor_and_oci_backend() -> None:
    from packages.runtime.sandbox.contracts import IsolationClass, select_sandbox_profile

    denied = select_sandbox_profile(
        IsolationClass.CONTAINER_STANDARD,
        available_backends={"docker"},
    )
    assert denied.available is False
    permitted = select_sandbox_profile(
        IsolationClass.CONTAINER_STANDARD,
        available_backends={"openshell", "docker"},
    )
    assert permitted.available is True
    assert permitted.profile is not None
    assert permitted.profile.backend == "openshell+docker"
