from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from pydantic import BaseModel, Field, JsonValue, TypeAdapter, model_validator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.perception_execution import (
    ExternalPerceptionInvocation,
    ObservationPromotionBinding,
    SandboxPerceptionInvocation,
)
from packages.investigation.perception.contracts import (
    PerceptionRequest,
    PhysicalOperator,
    PhysicalPerceptionStep,
)
from packages.runtime.capability.broker import InvocationGrants
from packages.runtime.capability.contracts import (
    CapabilityRequest,
    EffectSemantics,
    ExecutionClass,
)
from packages.runtime.sandbox.broker import (
    SandboxCreateRequest,
    SandboxExecRequest,
    SandboxGrants,
)
from packages.runtime.sandbox.contracts import IsolationClass
from packages.task_runtime.storage.service import get_task_contract_for_run

_JSON_DICT = TypeAdapter(dict[str, JsonValue])


class PerceptionCapabilityRoute(BaseModel):
    route_id: str
    route_revision: int = Field(ge=1)
    capability_requirement: str
    capability_id: str
    contract_revision: int = Field(ge=1)
    action: str
    resource_type: str
    resource: str | None = None
    resource_input_key: str | None = None
    resource_prefix: str = ""
    argument_map: dict[str, str] = Field(default_factory=dict)
    static_arguments: dict[str, JsonValue] = Field(default_factory=dict)
    estimated_budget: dict[str, Decimal] = Field(default_factory=dict)
    healthy_refs: set[str] | None = None
    available_execution_classes: set[ExecutionClass] | None = None
    action_timeout_seconds: float = Field(default=30.0, gt=0)
    evidence_purpose: str | None = None

    @model_validator(mode="after")
    def validate_route(self) -> PerceptionCapabilityRoute:
        for value, label in (
            (self.route_id, "route_id"),
            (self.capability_requirement, "capability_requirement"),
            (self.capability_id, "capability_id"),
            (self.action, "action"),
            (self.resource_type, "resource_type"),
        ):
            if not value.strip():
                raise ValueError(f"PerceptionCapabilityRoute {label} cannot be empty")
        if (self.resource is None) == (self.resource_input_key is None):
            raise ValueError("route requires exactly one of resource or resource_input_key")
        return self


class ExternalObservationRoute(PerceptionCapabilityRoute):
    promotion_source_id: str | None = None
    promotion_target_kind: str = "object"
    promote_request_target: bool = False


class SandboxObservationRoute(PerceptionCapabilityRoute):
    program_ref: str
    minimum_isolation: IsolationClass
    requested_timeout_seconds: float = Field(default=30.0, gt=0)
    workspace_artifact_refs: list[str] = Field(default_factory=list)
    readonly_artifact_refs: list[str] = Field(default_factory=list)
    requested_writable_paths: list[str] = Field(default_factory=list)
    network_destinations: list[str] = Field(default_factory=list)
    credential_scope: list[str] = Field(default_factory=list)
    export_paths: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_program_ref(self) -> SandboxObservationRoute:
        if not self.program_ref.startswith(("program:", "artifact:")):
            raise ValueError("sandbox route requires program/artifact reference")
        return self


class StaticPerceptionExecutionResolver:
    """Exact semantic route binding for Perception physical operators.

    The resolver never discovers native tools and never performs fuzzy routing. It maps a
    planner-owned capability_requirement to one versioned semantic route. CapabilityBinding
    still owns canonical-to-native translation and CapabilityBroker still owns authorization.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        external_routes: list[ExternalObservationRoute] | None = None,
        sandbox_routes: list[SandboxObservationRoute] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._external = _route_map(external_routes or [], PhysicalOperator.EXTERNAL)
        self._sandbox = _route_map(sandbox_routes or [], PhysicalOperator.SANDBOX)

    async def resolve_external(
        self,
        *,
        task_run_id: str,
        request: PerceptionRequest,
        step: PhysicalPerceptionStep,
    ) -> ExternalPerceptionInvocation:
        route = self._require_route(self._external, step, PhysicalOperator.EXTERNAL)
        task = await self._task(task_run_id)
        arguments = _project_arguments(route, step)
        promotion = None
        if route.promotion_source_id is not None:
            if not route.promote_request_target:
                raise ValueError("promotion route must explicitly bind its target")
            target_id = request.target.object_id
            if target_id is None:
                raise ValueError("promotion route requires PerceptionRequest target.object_id")
            promotion = ObservationPromotionBinding(
                source_id=route.promotion_source_id,
                target_kind=route.promotion_target_kind,
                target_id=target_id,
                locator={
                    "kind": "perception_route",
                    "route_id": route.route_id,
                    "route_revision": route.route_revision,
                },
            )
        return ExternalPerceptionInvocation(
            request=_capability_request(
                task_run_id=task_run_id,
                task_contract_id=task.task_contract_id,
                principal=task.principal,
                case_id=request.case_id,
                request_id=_capability_request_id(request, step),
                route=route,
                resource=_resource(route, step),
                arguments=arguments,
                evidence_purpose=_evidence_purpose(route, request),
            ),
            estimated_budget=dict(route.estimated_budget),
            grants=InvocationGrants(),
            healthy_refs=set(route.healthy_refs) if route.healthy_refs is not None else None,
            available_execution_classes=(
                set(route.available_execution_classes)
                if route.available_execution_classes is not None
                else None
            ),
            action_timeout_seconds=route.action_timeout_seconds,
            promotion=promotion,
        )

    async def resolve_sandbox(
        self,
        *,
        task_run_id: str,
        request: PerceptionRequest,
        step: PhysicalPerceptionStep,
    ) -> SandboxPerceptionInvocation:
        route = self._require_route(self._sandbox, step, PhysicalOperator.SANDBOX)
        task = await self._task(task_run_id)
        arguments = _project_arguments(route, step)
        request_id = _capability_request_id(request, step)
        return SandboxPerceptionInvocation(
            request=_capability_request(
                task_run_id=task_run_id,
                task_contract_id=task.task_contract_id,
                principal=task.principal,
                case_id=request.case_id,
                request_id=request_id,
                route=route,
                resource=_resource(route, step),
                arguments=arguments,
                evidence_purpose=_evidence_purpose(route, request),
            ),
            estimated_budget=dict(route.estimated_budget),
            capability_grants=InvocationGrants(),
            healthy_refs=set(route.healthy_refs) if route.healthy_refs is not None else None,
            available_execution_classes=(
                set(route.available_execution_classes)
                if route.available_execution_classes is not None
                else None
            ),
            action_timeout_seconds=route.action_timeout_seconds,
            create_request=SandboxCreateRequest(
                request_id=f"sandbox-create:{request.request_id}:{step.step_id}",
                minimum_isolation=route.minimum_isolation,
                workspace_artifact_refs=list(route.workspace_artifact_refs),
                readonly_artifact_refs=list(route.readonly_artifact_refs),
                requested_writable_paths=list(route.requested_writable_paths),
                network_destinations=list(route.network_destinations),
                credential_scope=list(route.credential_scope),
            ),
            exec_request=SandboxExecRequest(
                operation_id=f"sandbox-exec:{request.request_id}:{step.step_id}",
                program_ref=route.program_ref,
                # CapabilityBinding translates canonical arguments. The bound executor
                # writes those native arguments immediately before SandboxBroker.exec.
                arguments={},
                input_artifact_refs=[],
                requested_timeout_seconds=route.requested_timeout_seconds,
            ),
            sandbox_grants=SandboxGrants(),
            export_paths=list(route.export_paths),
        )

    async def _task(self, task_run_id: str):
        async with self._session_factory() as session:
            return await get_task_contract_for_run(session, task_run_id)

    @staticmethod
    def _require_route[TRoute: PerceptionCapabilityRoute](
        routes: dict[str, TRoute],
        step: PhysicalPerceptionStep,
        operator: PhysicalOperator,
    ) -> TRoute:
        if step.operator is not operator:
            raise ValueError(
                "resolver operator mismatch: "
                f"expected={operator.value} actual={step.operator.value}"
            )
        route = routes.get(step.capability_requirement)
        if route is None:
            raise LookupError(
                "no perception capability route for "
                f"operator={operator.value} requirement={step.capability_requirement}"
            )
        return route


def _route_map[TRoute: PerceptionCapabilityRoute](
    routes: Sequence[TRoute],
    operator: PhysicalOperator,
) -> dict[str, TRoute]:
    result: dict[str, TRoute] = {}
    for route in routes:
        if route.capability_requirement in result:
            raise ValueError(
                f"duplicate {operator.value} capability route: {route.capability_requirement}"
            )
        result[route.capability_requirement] = route
    return result


def _project_arguments(
    route: PerceptionCapabilityRoute,
    step: PhysicalPerceptionStep,
) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = dict(route.static_arguments)
    for canonical_name, input_key in route.argument_map.items():
        if input_key not in step.input:
            raise ValueError(f"perception route {route.route_id} requires step input {input_key!r}")
        result[canonical_name] = _json_value(step.input[input_key], input_key)
    return result


def _resource(route: PerceptionCapabilityRoute, step: PhysicalPerceptionStep) -> str:
    if route.resource is not None:
        return route.resource
    assert route.resource_input_key is not None
    value = step.input.get(route.resource_input_key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"perception route {route.route_id} requires string resource input "
            f"{route.resource_input_key!r}"
        )
    return f"{route.resource_prefix}{value}"


def _capability_request(
    *,
    task_run_id: str,
    task_contract_id: str,
    principal: str,
    case_id: str | None,
    request_id: str,
    route: PerceptionCapabilityRoute,
    resource: str,
    arguments: dict[str, JsonValue],
    evidence_purpose: str | None,
) -> CapabilityRequest:
    return CapabilityRequest(
        request_id=request_id,
        task_contract_id=task_contract_id,
        task_run_id=task_run_id,
        case_id=case_id,
        principal=principal,
        capability_id=route.capability_id,
        contract_revision=route.contract_revision,
        action=route.action,
        resource=resource,
        resource_type=route.resource_type,
        canonical_arguments=arguments,
        intended_effect=EffectSemantics.OBSERVATION,
        evidence_purpose=evidence_purpose,
        execution_context={
            "perception_route_id": route.route_id,
            "perception_route_revision": route.route_revision,
        },
    )


def _capability_request_id(
    request: PerceptionRequest,
    step: PhysicalPerceptionStep,
) -> str:
    return f"capability:{request.request_id}:{step.step_id}"


def _evidence_purpose(
    route: PerceptionCapabilityRoute,
    request: PerceptionRequest,
) -> str | None:
    return request.need_id or route.evidence_purpose or request.desired_observation


def _json_value(value: object, label: str) -> JsonValue:
    try:
        return _JSON_DICT.validate_python({"value": value})["value"]
    except Exception as exc:
        raise ValueError(f"perception route input {label!r} is not JSON-compatible") from exc
