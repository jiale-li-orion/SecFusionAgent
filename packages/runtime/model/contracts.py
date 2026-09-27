from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, JsonValue


class ModelAttemptStatus(StrEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN_AFTER_DISPATCH = "unknown_after_dispatch"


class ModelUsageSource(StrEnum):
    PROVIDER_EXACT = "provider_exact"
    TOKENIZER_ESTIMATE = "tokenizer_estimate"
    RESERVATION_UPPER_BOUND = "reservation_upper_bound"
    UNAVAILABLE = "unavailable"


class ModelUsage(BaseModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    provider_cost: str | None = None
    measurement_source: ModelUsageSource = ModelUsageSource.UNAVAILABLE


class ModelRequestRecord(BaseModel):
    model_request_id: str
    purpose: str
    request_owner_ref: str
    execution_id: str | None = None
    task_run_id: str | None = None
    case_id: str | None = None
    processing_run_id: str | None = None
    prompt_assembly_id: str | None = None
    prompt_revision: str
    request_schema_digest: str
    request_digest: str
    request_artifact_ref: str | None = None
    requested_model: str
    provider_policy_ref: str | None = None
    budget_ref: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    created_at: datetime


class ModelAttemptRecord(BaseModel):
    model_attempt_id: str
    model_request_id: str
    ordinal: int = Field(ge=1)
    provider: str
    adapter_revision: str
    actual_model: str
    provider_request_id: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    status: ModelAttemptStatus
    failure_class: str | None = None
    failure_detail: str | None = None
    response_schema_digest: str
    response_artifact_ref: str | None = None
    usage: ModelUsage
    cost: dict[str, JsonValue] = Field(default_factory=dict)
    cache_usage: dict[str, JsonValue] = Field(default_factory=dict)
    response_metadata: dict[str, JsonValue] = Field(default_factory=dict)
    latency_ms: int | None = Field(default=None, ge=0)


class PromptFragmentRecord(BaseModel):
    fragment_id: str
    kind: str
    source_ref: str
    source_revision: str
    disclosure_level: str | None = None
    selection_reason: str | None = None
    trust_class: str
    cache_class: str
    content_hash: str


class PromptAssemblyRecord(BaseModel):
    assembly_id: str
    assembly_hash: str
    execution_id: str
    task_run_id: str
    task_contract_id: str
    context_manifest_ref: str
    context_manifest_revision: int = Field(ge=1)
    role_revision: str
    platform_invariant_revision: str
    execution_profile_revision: str
    policy_context_revision: str
    state_projection_revision: str | None = None
    percept_refs: list[str] = Field(default_factory=list)
    materialized_skill_refs: list[str] = Field(default_factory=list)
    materialized_capability_view_refs: list[str] = Field(default_factory=list)
    materialized_fragment_refs: list[str] = Field(default_factory=list)
    ordered_fragment_ids: list[str] = Field(default_factory=list)
    materialized_ref_set_digest: str
    cache_handle_hints: list[str] = Field(default_factory=list)
    fragment_manifest: list[PromptFragmentRecord] = Field(default_factory=list)
    request_artifact_ref: str | None = None
    created_at: datetime
