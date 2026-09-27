from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from hashlib import sha256

from pydantic import BaseModel, Field, JsonValue, model_validator

from packages.task_runtime.contracts.models import (
    EffectCeiling,
    TaskContract,
    effect_within_ceiling,
)


class EffectSemantics(StrEnum):
    OBSERVATION = "observation"
    INTERNAL_STATE = "internal_state"
    EXTERNAL_SIDE_EFFECT = "external_side_effect"


_EFFECT_TO_CEILING: dict[EffectSemantics, EffectCeiling] = {
    EffectSemantics.OBSERVATION: EffectCeiling.READ_ONLY,
    EffectSemantics.INTERNAL_STATE: EffectCeiling.INTERNAL_STATE,
    EffectSemantics.EXTERNAL_SIDE_EFFECT: EffectCeiling.EXTERNAL_SIDE_EFFECT,
}


class ImplementationKind(StrEnum):
    LOCAL_FUNCTION = "local_function"
    RETRIEVAL_OPERATOR = "retrieval_operator"
    PROVIDER_API = "provider_api"
    MCP_TOOL = "mcp_tool"
    OPENAPI_OPERATION = "openapi_operation"
    CLI = "cli"
    BROWSER = "browser"
    COMPUTER_USE = "computer_use"
    SANDBOX_PROGRAM = "sandbox_program"
    CHILD_TASK = "child_task"


class ExecutionClass(StrEnum):
    TRUSTED_LOCAL_READ = "trusted_local_read"
    PROXIED_PROVIDER_READ = "proxied_provider_read"
    RESTRICTED_PROCESS = "restricted_process"
    OCI_CONTAINER = "oci_container"
    MICROVM = "microvm"
    FULLVM_BROWSER = "fullvm_browser"


class ToolImplementation(BaseModel):
    tool_impl_id: str
    implementation_revision: int = Field(ge=1)
    implementation_kind: ImplementationKind
    native_name: str
    transport: str
    native_input_schema: dict[str, JsonValue] = Field(default_factory=dict)
    native_output_schema: dict[str, JsonValue] = Field(default_factory=dict)
    server_identity: str | None = None
    server_origin: str | None = None
    auth_class: str = "none"
    network_destinations: list[str] = Field(default_factory=list)
    execution_backend: str | None = None
    health_ref: str
    native_schema_hash: str
    implementation_metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_implementation(self) -> ToolImplementation:
        for value, label in (
            (self.tool_impl_id, "tool_impl_id"),
            (self.native_name, "native_name"),
            (self.transport, "transport"),
            (self.health_ref, "health_ref"),
            (self.native_schema_hash, "native_schema_hash"),
        ):
            if not value.strip():
                raise ValueError(f"ToolImplementation {label} cannot be empty")
        expected = native_schema_hash(self.native_input_schema, self.native_output_schema)
        if self.native_schema_hash != expected:
            raise ValueError("ToolImplementation native_schema_hash does not match native schemas")
        return self


class CapabilityContract(BaseModel):
    capability_id: str
    contract_revision: int = Field(ge=1)
    action: str
    applicable_resource_types: list[str]
    canonical_input_schema: dict[str, JsonValue] = Field(default_factory=dict)
    canonical_output_schema: dict[str, JsonValue] = Field(default_factory=dict)
    observation_semantics: str
    effect_semantics: EffectSemantics
    authority_semantics: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    idempotency: str
    reversibility: str
    compensation: str | None = None
    data_ingress_class: str
    data_egress_class: str
    failure_semantics: list[str] = Field(default_factory=list)
    risk_class: str

    @model_validator(mode="after")
    def validate_contract_identity(self) -> CapabilityContract:
        if not self.capability_id.strip() or not self.action.strip():
            raise ValueError("CapabilityContract requires non-empty capability_id and action")
        if not self.applicable_resource_types:
            raise ValueError("CapabilityContract requires applicable_resource_types")
        return self

    @property
    def required_effect_ceiling(self) -> EffectCeiling:
        return _EFFECT_TO_CEILING[self.effect_semantics]


class CapabilityBinding(BaseModel):
    binding_id: str
    binding_revision: int = Field(ge=1)
    capability_id: str
    contract_revision: int = Field(ge=1)
    tool_impl_id: str
    implementation_revision: int = Field(ge=1)
    canonical_to_native_args: dict[str, str] = Field(default_factory=dict)
    native_to_canonical_result: dict[str, str] = Field(default_factory=dict)
    resource_resolver: str
    effect_resolver: str
    authority_mapper: str
    execution_class: ExecutionClass
    credential_profile: str
    network_profile: str
    sandbox_profile: str
    health_requirement: str
    cost_class: str
    latency_class: str
    fallback_rank: int = Field(default=100, ge=0)
    native_schema_hash: str

    @model_validator(mode="after")
    def validate_binding_identity(self) -> CapabilityBinding:
        for value, label in (
            (self.binding_id, "binding_id"),
            (self.capability_id, "capability_id"),
            (self.tool_impl_id, "tool_impl_id"),
            (self.resource_resolver, "resource_resolver"),
            (self.effect_resolver, "effect_resolver"),
            (self.authority_mapper, "authority_mapper"),
            (self.health_requirement, "health_requirement"),
            (self.native_schema_hash, "native_schema_hash"),
        ):
            if not value.strip():
                raise ValueError(f"CapabilityBinding {label} cannot be empty")
        return self


class CapabilityCard(BaseModel):
    capability_id: str
    contract_revision: int
    action: str
    purpose: str
    applicable_resource_types: list[str]
    observation_semantics: str
    effect_semantics: EffectSemantics
    authority_semantics: list[str]
    limitations: list[str] = Field(default_factory=list)
    risk_class: str
    cost_class: str
    latency_class: str


class CapabilitySchemaView(BaseModel):
    capability_id: str
    contract_revision: int
    canonical_input_schema: dict[str, JsonValue]
    canonical_output_schema: dict[str, JsonValue]
    relevant_preconditions: list[str] = Field(default_factory=list)
    failure_semantics: list[str] = Field(default_factory=list)
    obligation_hints: list[str] = Field(default_factory=list)


class CapabilityRequest(BaseModel):
    request_id: str
    task_contract_id: str
    task_run_id: str
    case_id: str | None = None
    principal: str
    capability_id: str
    contract_revision: int = Field(ge=1)
    action: str
    resource: str
    resource_type: str
    canonical_arguments: dict[str, JsonValue] = Field(default_factory=dict)
    intended_effect: EffectSemantics
    evidence_purpose: str | None = None
    execution_context: dict[str, JsonValue] = Field(default_factory=dict)


class InvocationPlan(BaseModel):
    invocation_plan_id: str
    capability_request_ref: str
    binding_id: str
    binding_revision: int
    resolved_resource: str
    resolved_effect: EffectSemantics
    canonical_arguments_digest: str
    native_arguments_ref: str
    execution_class: ExecutionClass
    credential_requirement: str
    network_requirement: str
    sandbox_requirement: str
    deadline_at: datetime
    budget_reservation_ref: str

    @model_validator(mode="after")
    def validate_deadline(self) -> InvocationPlan:
        if self.deadline_at.tzinfo is None:
            raise ValueError("InvocationPlan deadline_at must be timezone-aware")
        return self


class CapabilityInvocation(BaseModel):
    invocation_id: str
    invocation_plan_id: str
    policy_decision_ref: str
    credential_grant_ref: str | None = None
    network_grant_ref: str | None = None
    sandbox_instance_ref: str | None = None
    started_at: datetime


class CapabilityResultStatus(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    BLOCKED = "blocked"
    TIMED_OUT = "timed_out"


class CapabilityResult(BaseModel):
    invocation_id: str
    status: CapabilityResultStatus
    canonical_output_ref: str | None = None
    raw_artifact_ref: str | None = None
    effect_receipt_ref: str | None = None
    observation_class: str
    provenance: dict[str, JsonValue] = Field(default_factory=dict)
    latency: dict[str, JsonValue] = Field(default_factory=dict)
    cost: dict[str, JsonValue] = Field(default_factory=dict)
    failure_code: str | None = None
    failure_detail: str | None = None


class CapabilityDescriptor(BaseModel):
    purpose: str
    limitations: list[str] = Field(default_factory=list)
    obligation_hints: list[str] = Field(default_factory=list)


def capability_visible_for_task(task: TaskContract, capability: CapabilityContract) -> bool:
    return effect_within_ceiling(capability.required_effect_ceiling, task.effect_ceiling)


def validate_capability_request(
    task: TaskContract,
    capability: CapabilityContract,
    request: CapabilityRequest,
) -> list[str]:
    errors: list[str] = []
    if request.task_contract_id != task.task_contract_id:
        errors.append("task_contract_mismatch")
    if request.principal != task.principal:
        errors.append("principal_mismatch")
    if request.capability_id != capability.capability_id:
        errors.append("capability_id_mismatch")
    if request.contract_revision != capability.contract_revision:
        errors.append("capability_revision_mismatch")
    if request.action != capability.action:
        errors.append("action_mismatch")
    if request.resource_type not in capability.applicable_resource_types:
        errors.append("resource_type_not_applicable")
    if request.intended_effect != capability.effect_semantics:
        errors.append("intended_effect_mismatch")
    if not capability_visible_for_task(task, capability):
        errors.append("exceeds_task_effect_ceiling")
    return errors


def native_schema_hash(
    input_schema: dict[str, JsonValue], output_schema: dict[str, JsonValue]
) -> str:
    return _json_hash({"input": input_schema, "output": output_schema})


def canonical_arguments_digest(arguments: dict[str, JsonValue]) -> str:
    return _json_hash(arguments)


def _json_hash(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
