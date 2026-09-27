from __future__ import annotations

from pydantic import JsonValue

from packages.runtime.capability.contracts import (
    CapabilityBinding,
    CapabilityContract,
    CapabilityDescriptor,
    EffectSemantics,
    ExecutionClass,
    ImplementationKind,
    ToolImplementation,
    native_schema_hash,
)
from packages.runtime.capability.registry import CapabilityRegistry
from packages.runtime.policy.contracts import Authorization, PolicyDecisionPoint, PolicyObligation
from packages.runtime.policy.engine import RuntimePolicyRule, StaticPolicyEngine
from packages.task_runtime.contracts.models import (
    DelegationCeiling,
    EffectCeiling,
    TaskContract,
    TaskKind,
)


def _objects():
    input_schema: dict[str, JsonValue] = {"type": "object", "required": ["repo", "tag"]}
    output_schema: dict[str, JsonValue] = {"type": "object"}
    schema_hash = native_schema_hash(input_schema, output_schema)
    implementation = ToolImplementation(
        tool_impl_id="github-api-release",
        implementation_revision=1,
        implementation_kind=ImplementationKind.PROVIDER_API,
        native_name="github.get_release",
        transport="https",
        native_input_schema=input_schema,
        native_output_schema=output_schema,
        server_identity="api.github.com",
        server_origin="https://api.github.com",
        auth_class="github-token",
        network_destinations=["api.github.com:443"],
        health_ref="health:github",
        native_schema_hash=schema_hash,
    )
    contract = CapabilityContract(
        capability_id="github.read_release",
        contract_revision=1,
        action="read",
        applicable_resource_types=["github.release"],
        canonical_input_schema=input_schema,
        canonical_output_schema=output_schema,
        observation_semantics="provider_observation",
        effect_semantics=EffectSemantics.OBSERVATION,
        authority_semantics=["primary_for(repository_release_state)"],
        preconditions=["public_or_authorized_repo"],
        idempotency="safe",
        reversibility="not_applicable",
        data_ingress_class="public",
        data_egress_class="none",
        failure_semantics=["provider_blocked", "rate_limited"],
        risk_class="low",
    )
    binding = CapabilityBinding(
        binding_id="github-release-api-v1",
        binding_revision=1,
        capability_id=contract.capability_id,
        contract_revision=1,
        tool_impl_id=implementation.tool_impl_id,
        implementation_revision=1,
        canonical_to_native_args={"repo": "repository", "tag": "tag"},
        resource_resolver="identity",
        effect_resolver="contract",
        authority_mapper="source-role:primary",
        execution_class=ExecutionClass.PROXIED_PROVIDER_READ,
        credential_profile="github:read",
        network_profile="github-api",
        sandbox_profile="none",
        health_requirement="healthy",
        cost_class="low",
        latency_class="interactive",
        fallback_rank=10,
        native_schema_hash=schema_hash,
    )
    return contract, implementation, binding


def _task() -> TaskContract:
    return TaskContract(
        task_contract_id="task-1",
        contract_revision=1,
        principal="user:alice",
        task_kind=TaskKind.VERIFY_VERSION_FIX,
        target_resources=["repo:vllm-project/vllm"],
        desired_state={"goal": "verify"},
        evidence_contract={"source_roles": ["primary"]},
        output_contract={},
        temporal_contract={"freshness": "current"},
        effect_ceiling=EffectCeiling.READ_ONLY,
        delegation_ceiling=DelegationCeiling(),
        completion_predicate={"type": "evidence_sufficient"},
        policy_revision="policy-v1",
    )


def _policy() -> StaticPolicyEngine:
    return StaticPolicyEngine(
        policy_revision="policy-v1",
        rules=[
            RuntimePolicyRule(
                policy_id="visible-public-read",
                policy_revision="policy-v1",
                decision_points=[PolicyDecisionPoint.CAPABILITY_VISIBILITY],
                principal_patterns=["user:*"],
                action_patterns=["read"],
                resource_patterns=["capability:github.*"],
                authorization=Authorization.PERMIT,
            ),
            RuntimePolicyRule(
                policy_id="audit-provider-read",
                policy_revision="policy-v1",
                decision_points=[PolicyDecisionPoint.CAPABILITY_VISIBILITY],
                principal_patterns=["user:*"],
                action_patterns=["read"],
                resource_patterns=["capability:github.*"],
                obligations=[PolicyObligation(kind="audit_available")],
            ),
        ],
    )


def test_visibility_filters_health_scope_policy_and_obligation_without_exposing_native_schema() -> (
    None
):
    contract, implementation, binding = _objects()
    registry = CapabilityRegistry(
        revision="registry-v1",
        contracts=[contract],
        descriptors={
            contract.capability_id: CapabilityDescriptor(
                purpose="Read repository release metadata",
                limitations=["provider snapshot"],
                obligation_hints=["audit"],
            )
        },
        implementations=[implementation],
        bindings=[binding],
    )
    visible = registry.visible_capabilities(
        task=_task(),
        task_run_id="run-1",
        policy_engine=_policy(),
        capability_scope={"github.read_release"},
        healthy_refs={"health:github"},
        available_execution_classes={ExecutionClass.PROXIED_PROVIDER_READ},
        satisfiable_obligation_kinds={"audit_available"},
    )
    assert [item.capability_id for item in visible.cards] == ["github.read_release"]
    assert visible.hidden_reasons == {}
    card_json = visible.cards[0].model_dump(mode="json")
    assert "native_input_schema" not in card_json
    assert "server_identity" not in card_json
    schema = registry.schema_view("github.read_release", 1)
    assert schema.canonical_input_schema == contract.canonical_input_schema

    hidden = registry.visible_capabilities(
        task=_task(),
        task_run_id="run-1",
        policy_engine=_policy(),
        capability_scope={"github.read_release"},
        healthy_refs=set(),
        available_execution_classes={ExecutionClass.PROXIED_PROVIDER_READ},
        satisfiable_obligation_kinds={"audit_available"},
    )
    assert hidden.cards == []
    assert "no_healthy_binding" in hidden.hidden_reasons["github.read_release@1"]


def test_registry_rejects_binding_after_native_schema_hash_drift() -> None:
    contract, implementation, binding = _objects()
    changed = implementation.model_copy(
        update={
            "native_output_schema": {"type": "array"},
            "native_schema_hash": native_schema_hash(
                implementation.native_input_schema,
                {"type": "array"},
            ),
        }
    )
    try:
        CapabilityRegistry(
            revision="registry-v2",
            contracts=[contract],
            descriptors={contract.capability_id: CapabilityDescriptor(purpose="read")},
            implementations=[changed],
            bindings=[binding],
        )
    except ValueError as exc:
        assert "native schema hash mismatch" in str(exc)
    else:
        raise AssertionError("stale binding must be rejected")
