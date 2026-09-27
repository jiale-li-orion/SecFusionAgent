from __future__ import annotations

from pydantic import BaseModel, Field

from packages.runtime.capability.contracts import (
    CapabilityBinding,
    CapabilityCard,
    CapabilityContract,
    CapabilityDescriptor,
    CapabilitySchemaView,
    ExecutionClass,
    ToolImplementation,
    capability_visible_for_task,
)
from packages.runtime.policy.contracts import (
    Authorization,
    PolicyDecisionPoint,
    PolicyRequest,
    obligations_satisfied,
)
from packages.runtime.policy.engine import StaticPolicyEngine
from packages.task_runtime.contracts.models import TaskContract


class VisibleCapabilitySet(BaseModel):
    registry_revision: str
    cards: list[CapabilityCard] = Field(default_factory=list)
    hidden_reasons: dict[str, list[str]] = Field(default_factory=dict)


class CapabilityRegistry:
    def __init__(
        self,
        *,
        revision: str,
        contracts: list[CapabilityContract],
        descriptors: dict[str, CapabilityDescriptor],
        implementations: list[ToolImplementation],
        bindings: list[CapabilityBinding],
    ) -> None:
        if not revision.strip():
            raise ValueError("capability registry revision cannot be empty")
        self.revision = revision
        self._contracts = {(item.capability_id, item.contract_revision): item for item in contracts}
        self._descriptors = dict(descriptors)
        self._implementations = {
            (item.tool_impl_id, item.implementation_revision): item for item in implementations
        }
        self._bindings = tuple(bindings)
        self._validate_registry()

    def contract(self, capability_id: str, contract_revision: int) -> CapabilityContract:
        try:
            return self._contracts[(capability_id, contract_revision)]
        except KeyError as exc:
            raise LookupError(
                f"capability contract not found: {capability_id}@{contract_revision}"
            ) from exc

    def implementation(self, tool_impl_id: str, implementation_revision: int) -> ToolImplementation:
        try:
            return self._implementations[(tool_impl_id, implementation_revision)]
        except KeyError as exc:
            raise LookupError(
                f"tool implementation not found: {tool_impl_id}@{implementation_revision}"
            ) from exc

    def schema_view(
        self,
        capability_id: str,
        contract_revision: int,
    ) -> CapabilitySchemaView:
        contract = self.contract(capability_id, contract_revision)
        descriptor = self._descriptors[capability_id]
        return CapabilitySchemaView(
            capability_id=contract.capability_id,
            contract_revision=contract.contract_revision,
            canonical_input_schema=contract.canonical_input_schema,
            canonical_output_schema=contract.canonical_output_schema,
            relevant_preconditions=contract.preconditions,
            failure_semantics=contract.failure_semantics,
            obligation_hints=descriptor.obligation_hints,
        )

    def visible_capabilities(
        self,
        *,
        task: TaskContract,
        task_run_id: str,
        policy_engine: StaticPolicyEngine,
        capability_scope: set[str] | None = None,
        healthy_refs: set[str] | None = None,
        available_execution_classes: set[ExecutionClass] | None = None,
        satisfiable_obligation_kinds: set[str] | None = None,
    ) -> VisibleCapabilitySet:
        scope = capability_scope
        health = healthy_refs
        execution_classes = available_execution_classes
        satisfiable = satisfiable_obligation_kinds or set()
        cards: list[CapabilityCard] = []
        hidden: dict[str, list[str]] = {}
        for contract in sorted(
            self._contracts.values(), key=lambda item: (item.capability_id, item.contract_revision)
        ):
            reasons: list[str] = []
            if scope is not None and contract.capability_id not in scope:
                reasons.append("outside_execution_capability_scope")
            if not capability_visible_for_task(task, contract):
                reasons.append("exceeds_task_effect_ceiling")
            eligible_bindings = self._eligible_bindings(
                contract,
                healthy_refs=health,
                available_execution_classes=execution_classes,
            )
            if not eligible_bindings:
                reasons.append("no_healthy_binding")
            decision = policy_engine.evaluate(
                PolicyRequest(
                    decision_point=PolicyDecisionPoint.CAPABILITY_VISIBILITY,
                    principal=task.principal,
                    action=contract.action,
                    resource=f"capability:{contract.capability_id}",
                    context={
                        "task_contract_id": task.task_contract_id,
                        "task_run_id": task_run_id,
                        "capability_id": contract.capability_id,
                    },
                )
            )
            if decision.authorization is not Authorization.PERMIT:
                reasons.append("visibility_policy_denied")
            elif not obligations_satisfied(
                decision,
                fulfilled_obligation_kinds=satisfiable,
            ):
                reasons.append("visibility_obligation_unsatisfied")
            if reasons:
                hidden[f"{contract.capability_id}@{contract.contract_revision}"] = sorted(
                    set(reasons)
                )
                continue
            descriptor = self._descriptors[contract.capability_id]
            chosen = eligible_bindings[0]
            cards.append(
                CapabilityCard(
                    capability_id=contract.capability_id,
                    contract_revision=contract.contract_revision,
                    action=contract.action,
                    purpose=descriptor.purpose,
                    applicable_resource_types=contract.applicable_resource_types,
                    observation_semantics=contract.observation_semantics,
                    effect_semantics=contract.effect_semantics,
                    authority_semantics=contract.authority_semantics,
                    limitations=descriptor.limitations,
                    risk_class=contract.risk_class,
                    cost_class=chosen.cost_class,
                    latency_class=chosen.latency_class,
                )
            )
        return VisibleCapabilitySet(
            registry_revision=self.revision,
            cards=cards,
            hidden_reasons=hidden,
        )

    def resolve_binding(
        self,
        contract: CapabilityContract,
        *,
        healthy_refs: set[str] | None = None,
        available_execution_classes: set[ExecutionClass] | None = None,
    ) -> tuple[CapabilityBinding, ToolImplementation]:
        bindings = self._eligible_bindings(
            contract,
            healthy_refs=healthy_refs,
            available_execution_classes=available_execution_classes,
        )
        if not bindings:
            raise LookupError(f"no healthy capability binding: {contract.capability_id}")
        binding = bindings[0]
        implementation = self.implementation(
            binding.tool_impl_id,
            binding.implementation_revision,
        )
        if binding.native_schema_hash != implementation.native_schema_hash:
            raise RuntimeError("capability binding is stale after native schema change")
        return binding, implementation

    def _eligible_bindings(
        self,
        contract: CapabilityContract,
        *,
        healthy_refs: set[str] | None,
        available_execution_classes: set[ExecutionClass] | None,
    ) -> list[CapabilityBinding]:
        result: list[CapabilityBinding] = []
        for binding in self._bindings:
            if (
                binding.capability_id != contract.capability_id
                or binding.contract_revision != contract.contract_revision
            ):
                continue
            implementation = self.implementation(
                binding.tool_impl_id,
                binding.implementation_revision,
            )
            if binding.native_schema_hash != implementation.native_schema_hash:
                continue
            if healthy_refs is not None and implementation.health_ref not in healthy_refs:
                continue
            if (
                available_execution_classes is not None
                and binding.execution_class not in available_execution_classes
            ):
                continue
            result.append(binding)
        return sorted(result, key=lambda item: (item.fallback_rank, item.binding_id))

    def _validate_registry(self) -> None:
        for capability_id in {key[0] for key in self._contracts}:
            if capability_id not in self._descriptors:
                raise ValueError(f"capability descriptor missing: {capability_id}")
        for binding in self._bindings:
            contract = self.contract(binding.capability_id, binding.contract_revision)
            implementation = self.implementation(
                binding.tool_impl_id,
                binding.implementation_revision,
            )
            if binding.native_schema_hash != implementation.native_schema_hash:
                raise ValueError(
                    f"stale CapabilityBinding {binding.binding_id}: native schema hash mismatch"
                )
            if contract.capability_id != binding.capability_id:
                raise ValueError("binding capability mismatch")
