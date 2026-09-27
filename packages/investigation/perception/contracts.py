from __future__ import annotations

from enum import StrEnum
from typing import Literal, Protocol

from pydantic import BaseModel, Field, JsonValue

from packages.intelligence.retrieval.contracts import RetrievedCandidate


class PerceptionOperation(StrEnum):
    INSPECT = "inspect"
    EXPAND = "expand"
    TRACE = "trace"
    ZOOM = "zoom"
    SEARCH = "search"
    CORROBORATE = "corroborate"
    CONTRAST = "contrast"
    REFRESH = "refresh"
    OBSERVE_EXTERNAL = "observe_external"
    WATCH = "watch"


class IdentifierTarget(BaseModel):
    namespace: str
    value: str


class EvidenceTarget(BaseModel):
    target_kind: str
    target_id: str


class PerceptionTarget(BaseModel):
    identifier: IdentifierTarget | None = None
    object_id: str | None = None
    query_text: str | None = None
    query_vector: list[float] | None = None
    projection_types: list[str] = Field(default_factory=list)
    relation_types: list[str] = Field(default_factory=list)
    evidence_targets: list[EvidenceTarget] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    verification_intent: str | None = None


class EvidenceRequirement(BaseModel):
    required_source_roles: list[str] = Field(default_factory=list)
    min_independent_sources: int = 0
    max_candidates: int = 20


class PerceptionRequest(BaseModel):
    request_id: str
    case_id: str | None = None
    need_id: str | None = None
    operation: PerceptionOperation
    target: PerceptionTarget
    desired_observation: str | None = None
    evidence_requirement: EvidenceRequirement = Field(default_factory=EvidenceRequirement)
    time_scope: dict[str, JsonValue] = Field(default_factory=dict)
    current_context_refs: list[str] = Field(default_factory=list)
    budget_ref: str | None = None


class PhysicalOperator(StrEnum):
    EXACT = "exact"
    STRUCTURED = "structured"
    LEXICAL = "lexical"
    DENSE = "dense"
    GRAPH = "graph"
    EVIDENCE = "evidence"
    EXTERNAL = "external"
    SANDBOX = "sandbox"


class PhysicalPerceptionStep(BaseModel):
    step_id: str
    operator: PhysicalOperator
    input: dict[str, object] = Field(default_factory=dict)
    dependency: str | None = None
    expected_output_type: str
    capability_requirement: str = "local_read"
    estimated_cost: Literal["low", "medium", "high"] = "low"


class PhysicalPerceptionPlan(BaseModel):
    request_id: str
    steps: list[PhysicalPerceptionStep] = Field(default_factory=list)
    stop_condition: str = "local_plan_exhausted"
    fallback_order: list[str] = Field(default_factory=list)
    planner_revision: str = "perception-planner-v1"


class PerceptionStepResult(BaseModel):
    candidates: list[RetrievedCandidate] = Field(default_factory=list)
    observed_propositions: list[ObservedProposition] = Field(default_factory=list)
    observation_handles: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    cost: dict[str, JsonValue] = Field(default_factory=dict)


class PhysicalObservationPort(Protocol):
    async def execute(
        self,
        *,
        task_run_id: str,
        request: PerceptionRequest,
        step: PhysicalPerceptionStep,
    ) -> PerceptionStepResult: ...


class CandidateAssemblyResult(BaseModel):
    candidates: list[RetrievedCandidate] = Field(default_factory=list)
    independent_source_keys: list[str] = Field(default_factory=list)
    source_roles: list[str] = Field(default_factory=list)
    requirements_satisfied: bool
    unresolved: list[str] = Field(default_factory=list)


class ObservedProposition(BaseModel):
    statement: str
    support_refs: list[str] = Field(default_factory=list)
    refute_refs: list[str] = Field(default_factory=list)
    source_groups: list[str] = Field(default_factory=list)
    freshness: dict[str, JsonValue] = Field(default_factory=dict)


class PhysicalObservationResult(BaseModel):
    observation_handle: str | None = None
    target_refs: list[str] = Field(default_factory=list)
    observed_propositions: list[ObservedProposition] = Field(default_factory=list)
    relations: list[dict[str, JsonValue]] = Field(default_factory=list)
    timeline_slice: list[dict[str, JsonValue]] = Field(default_factory=list)
    candidates: list[RetrievedCandidate] = Field(default_factory=list)
    evidence_handles: list[str] = Field(default_factory=list)
    independent_source_keys: list[str] = Field(default_factory=list)
    source_roles: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    cost: dict[str, JsonValue] = Field(default_factory=dict)


class Percept(BaseModel):
    percept_id: str
    request_id: str
    target_refs: list[str] = Field(default_factory=list)
    observed_propositions: list[ObservedProposition] = Field(default_factory=list)
    relations: list[dict[str, JsonValue]] = Field(default_factory=list)
    timeline_slice: list[dict[str, JsonValue]] = Field(default_factory=list)
    candidate_evidence: list[RetrievedCandidate] = Field(default_factory=list)
    evidence_handles: list[str] = Field(default_factory=list)
    observation_handles: list[str] = Field(default_factory=list)
    independent_source_keys: list[str] = Field(default_factory=list)
    source_roles: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    operator_counts: dict[str, int] = Field(default_factory=dict)
    cost: dict[str, object] = Field(default_factory=dict)
    assembler_revision: str = "candidate-assembler-v1"
