from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, Field

from packages.intelligence.knowledge.vocabulary import EnrichmentDimension
from packages.investigation.perception.contracts import Percept, PerceptionRequest
from packages.investigation.state.contracts import EvidenceNeed, InvestigationState, StatePatch
from packages.task_runtime.contracts.models import TaskContract, TaskRunStatus


class InvestigationActionKind(StrEnum):
    PERCEIVE = "perceive"
    DELEGATE = "delegate"
    PATCH = "patch"
    WAIT = "wait"
    STOP = "stop"


class PerceptionAction(BaseModel):
    kind: Literal[InvestigationActionKind.PERCEIVE] = InvestigationActionKind.PERCEIVE
    request: PerceptionRequest


class EnrichmentDelegationRequest(BaseModel):
    delegation_id: str
    target_object_id: str
    cve_id: str
    required_dimensions: list[EnrichmentDimension] = Field(
        min_length=1,
        description=(
            "Canonical enrichment-v1 dimensions only. First fixed version and fix commit "
            "questions use fix_remediation; affected version questions use version_applicability."
        ),
    )
    reason: str


class DelegationAction(BaseModel):
    kind: Literal[InvestigationActionKind.DELEGATE] = InvestigationActionKind.DELEGATE
    request: EnrichmentDelegationRequest


class DelegationResult(BaseModel):
    child_run_id: str
    child_context_ref: str
    child_execution_ref: str
    child_status: TaskRunStatus | None = None


class InvestigationDelegationPort(Protocol):
    async def delegate_enrichment(
        self,
        *,
        parent_run_id: str,
        request: EnrichmentDelegationRequest,
    ) -> DelegationResult: ...


class InvestigationExecutionBoundary(Protocol):
    async def blocking_reason(self, task_run_id: str) -> str | None: ...


class StatePatchAction(BaseModel):
    kind: Literal[InvestigationActionKind.PATCH] = InvestigationActionKind.PATCH
    patch: StatePatch


class WaitAction(BaseModel):
    kind: Literal[InvestigationActionKind.WAIT] = InvestigationActionKind.WAIT
    reason: str = "waiting_for_world_update"


class StopAction(BaseModel):
    kind: Literal[InvestigationActionKind.STOP] = InvestigationActionKind.STOP
    reason: str


InvestigationAction = Annotated[
    PerceptionAction | DelegationAction | StatePatchAction | WaitAction | StopAction,
    Field(discriminator="kind"),
]


class InvestigationPlannerDecision(BaseModel):
    action: InvestigationAction
    decision_note: str | None = None


class InvestigationFrame(BaseModel):
    task_run_id: str
    task_contract: TaskContract
    state: InvestigationState
    selected_need: EvidenceNeed | None = None
    iteration: int
    last_percept: Percept | None = None
    recent_percepts: list[Percept] = Field(default_factory=list)


class InvestigationPlanner(Protocol):
    async def next_action(self, frame: InvestigationFrame) -> InvestigationAction: ...
