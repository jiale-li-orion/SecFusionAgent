from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.enrichment.runtime.tasks import build_vulnerability_enrichment_contract
from packages.intelligence.knowledge.vocabulary import EnrichmentDimension
from packages.investigation.runtime.contracts import (
    DelegationResult,
    EnrichmentDelegationRequest,
)
from packages.runtime.budget import BudgetGovernor, BudgetLimits
from packages.runtime.execution.service import ExecutionRunService
from packages.task_runtime.context.contracts import ChildContextSpec
from packages.task_runtime.context.handoff import create_child_task_run
from packages.task_runtime.context.service import derive_child_context
from packages.task_runtime.contracts.execution import (
    ExecutionEnvelope,
    validate_child_execution_envelope,
)
from packages.task_runtime.contracts.models import TaskRunStatus
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.service import (
    get_task_context,
    get_task_contract_for_run,
    get_task_run,
    transition_task_run,
)


class DelegatedEnrichmentPolicy(BaseModel):
    budget_quantities: dict[str, Decimal] = Field(default_factory=dict)
    capability_scope: list[str] = Field(default_factory=list)
    identity_scope: list[str] = Field(default_factory=list)


class EnrichmentDelegationAdapter:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        policy: DelegatedEnrichmentPolicy,
        budget_governor: BudgetGovernor | None = None,
        execution_service: ExecutionRunService | None = None,
        stream_name: str = "secfusion:task-events",
    ) -> None:
        self._session_factory = session_factory
        self._policy = policy
        self._budget = budget_governor or BudgetGovernor()
        self._execution = execution_service or ExecutionRunService()
        self._stream_name = stream_name

    async def delegate_enrichment(
        self,
        *,
        parent_run_id: str,
        request: EnrichmentDelegationRequest,
    ) -> DelegationResult:
        dimensions = _dimensions(request.required_dimensions)
        child_run_id = _stable_id(f"delegated-enrichment:{parent_run_id}:{request.delegation_id}")
        child_execution_id = f"execution:{child_run_id}"
        child_budget_id = f"budget:{child_run_id}"
        child_context_id = f"context:{child_run_id}"

        async with self._session_factory() as session, session.begin():
            parent_run = await get_task_run(session, parent_run_id)
            parent_contract = await get_task_contract_for_run(session, parent_run_id)
            parent_manifest = await get_task_context(session, parent_run_id)
            parent_envelope = await self._execution.get(
                session,
                parent_run.execution_envelope_ref,
            )
            if request.target_object_id not in set(parent_manifest.object_refs):
                raise ValueError(
                    "delegated enrichment target must be present in parent ContextManifest"
                )
            if not set(self._policy.capability_scope) <= set(parent_envelope.capability_scope):
                raise ValueError("delegated capability scope exceeds parent execution scope")
            if not set(self._policy.identity_scope) <= set(parent_envelope.identity_scope):
                raise ValueError("delegated identity scope exceeds parent execution scope")

            child_contract = build_vulnerability_enrichment_contract(
                task_contract_id=(
                    f"delegated-enrichment:{parent_contract.task_contract_id}:"
                    f"{request.delegation_id}"
                ),
                principal=parent_contract.principal,
                target_object_id=request.target_object_id,
                cve_id=request.cve_id,
                required_dimensions=dimensions,
                policy_revision=parent_contract.policy_revision,
                on_behalf_of=parent_contract.on_behalf_of,
            )
            child_role = canonical_roles()["EnrichmentRole"]
            child_context_spec = ChildContextSpec(
                context_id=child_context_id,
                policy_context_ref=parent_manifest.policy_context_ref,
                capability_envelope_ref=f"capability:delegated-enrichment:{child_run_id}",
                budget_ref=child_budget_id,
                include_case=False,
                include_investigation_state=False,
                object_refs=[request.target_object_id],
            )
            expected_context = derive_child_context(
                parent_manifest,
                child_contract=child_contract,
                child_role=child_role,
                spec=child_context_spec,
            )
            try:
                child_run = await get_task_run(session, child_run_id)
            except LookupError:
                child_run = await create_child_task_run(
                    session,
                    parent_run_id=parent_run_id,
                    child_contract=child_contract,
                    child_role=child_role,
                    context_spec=child_context_spec,
                    execution_envelope_ref=child_execution_id,
                    stream_name=self._stream_name,
                    run_id=child_run_id,
                    producer="InvestigationRole",
                )
            else:
                if (
                    child_run.parent_run_id != parent_run_id
                    or child_run.role_id != child_role.role_id
                    or child_run.execution_envelope_ref != child_execution_id
                ):
                    raise ValueError("delegated child run identity conflicts with replay")
                stored_contract = await get_task_contract_for_run(session, child_run_id)
                if stored_contract != child_contract:
                    raise ValueError("delegated child contract changed on replay")
                stored_context = await get_task_context(session, child_run_id)
                # A child keeps its original world snapshot while the parent and child
                # contexts can advance independently after the first delegation.
                stable_fields = (
                    "context_id", "parent_context_id", "task_contract_ref", "role_ref",
                    "case_ref", "investigation_state_ref", "object_refs",
                    "policy_context_ref", "capability_envelope_ref", "budget_ref",
                )
                if any(
                    getattr(stored_context, field) != getattr(expected_context, field)
                    for field in stable_fields
                ):
                    raise ValueError("delegated child context changed on replay")
            await self._budget.create_account(
                session,
                account_id=child_budget_id,
                task_run_id=child_run.run_id,
                parent_account_id=parent_envelope.budget_ref,
                limits=BudgetLimits(quantities=dict(self._policy.budget_quantities)),
            )
            child_envelope = ExecutionEnvelope(
                execution_id=child_execution_id,
                parent_execution_id=parent_envelope.execution_id,
                task_contract_id=child_contract.task_contract_id,
                task_run_id=child_run.run_id,
                case_id=None,
                role_revision=f"{child_role.role_id}@{child_role.version}",
                context_manifest_revision=1,
                execution_profile=child_role.default_execution_profile,
                capability_scope=sorted(set(self._policy.capability_scope)),
                deadline_at=parent_envelope.deadline_at,
                budget_ref=child_budget_id,
                policy_revision=parent_envelope.policy_revision,
                identity_scope=sorted(set(self._policy.identity_scope)),
                network_policy=parent_envelope.network_policy,
                side_effect_policy=parent_envelope.side_effect_policy,
                sandbox_profile_revision=parent_envelope.sandbox_profile_revision,
                trace_context={
                    **parent_envelope.trace_context,
                    "delegation_id": request.delegation_id,
                    "parent_run_id": parent_run_id,
                },
            )
            errors = validate_child_execution_envelope(parent_envelope, child_envelope)
            if errors:
                raise ValueError(
                    "delegated execution envelope violates parent ceiling: "
                    + ",".join(sorted(errors))
                )
            await self._execution.create(session, child_envelope)
            if child_run.status is TaskRunStatus.SUBMITTED:
                child_run = await transition_task_run(
                    session,
                    run_id=child_run_id,
                    target=TaskRunStatus.QUEUED,
                    payload_ref=f"queue:delegated-enrichment:{request.delegation_id}",
                    idempotency_key=f"queue:delegated-enrichment:{child_run_id}",
                    stream_name=self._stream_name,
                    producer="InvestigationRole",
                )

        return DelegationResult(
            child_run_id=child_run_id,
            child_context_ref=f"{child_context_id}@1",
            child_execution_ref=child_execution_id,
            child_status=child_run.status,
        )


def _dimensions(values: Iterable[str]) -> list[EnrichmentDimension]:
    result: list[EnrichmentDimension] = []
    for value in values:
        try:
            result.append(EnrichmentDimension(value))
        except ValueError as exc:
            raise ValueError(f"unknown enrichment dimension: {value}") from exc
    return sorted(set(result), key=lambda item: item.value)


def _stable_id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"secfusion:{value}"))
