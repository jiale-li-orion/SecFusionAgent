from __future__ import annotations

import json
from hashlib import sha256
from typing import Protocol

from pydantic import BaseModel, Field, JsonValue, model_validator

from packages.task_runtime.contracts.models import TaskContract, TaskIntent, TaskKind


class TaskAdmissionDenied(PermissionError):
    pass


class TaskAdmissionAuthorization(BaseModel):
    allowed: bool
    authorization: str
    policy_decision_ref: str | None = None
    denial_reason: str | None = None
    fulfilled_obligations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_authorization(self) -> TaskAdmissionAuthorization:
        if self.allowed and self.denial_reason is not None:
            raise ValueError("permitted task admission cannot carry denial_reason")
        if not self.allowed and not self.denial_reason:
            raise ValueError("denied task admission requires denial_reason")
        return self


class TaskContractCompiler(Protocol):
    task_kind: TaskKind
    compiler_revision: str

    def compile(
        self,
        intent: TaskIntent,
        *,
        task_contract_id: str,
        contract_revision: int,
        principal: str,
        on_behalf_of: str | None,
        policy_revision: str,
        binding_context: dict[str, JsonValue],
    ) -> TaskContract: ...


class TaskAdmissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        intent_ref: str,
        intent: TaskIntent,
        candidate_contract: TaskContract,
    ) -> TaskAdmissionAuthorization: ...


class TaskAdmissionRequest(BaseModel):
    intent: TaskIntent
    principal: str
    policy_revision: str
    on_behalf_of: str | None = None
    task_contract_id: str | None = None
    contract_revision: int = Field(default=1, ge=1)
    binding_context: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_request(self) -> TaskAdmissionRequest:
        if not self.principal.strip() or not self.policy_revision.strip():
            raise ValueError("task admission principal/policy_revision cannot be empty")
        return self


class TaskAdmissionResult(BaseModel):
    intent_ref: str
    contract: TaskContract
    compiler_revision: str
    policy_decision_ref: str | None = None
    policy_authorization: str
    replay_key: str


class TaskContractService:
    """Compile ambiguous TaskIntent into an executable, policy-admitted contract."""

    def __init__(
        self,
        compilers: list[TaskContractCompiler],
        *,
        authorizer: TaskAdmissionAuthorizer,
    ) -> None:
        self._authorizer = authorizer
        self._compilers: dict[TaskKind, TaskContractCompiler] = {}
        for compiler in compilers:
            if compiler.task_kind in self._compilers:
                raise ValueError(f"duplicate TaskContract compiler for {compiler.task_kind.value}")
            self._compilers[compiler.task_kind] = compiler

    async def admit(self, request: TaskAdmissionRequest) -> TaskAdmissionResult:
        kind = request.intent.candidate_task_kind
        if kind is None:
            raise ValueError(
                "TaskIntent is ambiguous: candidate_task_kind is required for admission"
            )
        compiler = self._compilers.get(kind)
        if compiler is None:
            raise ValueError(f"no TaskContract compiler registered for {kind.value}")

        intent_ref = _intent_ref(request.intent)
        contract_id = request.task_contract_id or _contract_id(
            request,
            intent_ref=intent_ref,
            compiler_revision=compiler.compiler_revision,
        )
        contract = compiler.compile(
            request.intent,
            task_contract_id=contract_id,
            contract_revision=request.contract_revision,
            principal=request.principal,
            on_behalf_of=request.on_behalf_of,
            policy_revision=request.policy_revision,
            binding_context=dict(request.binding_context),
        )
        _validate_compiled_contract(request, kind, contract, contract_id)

        authorization = await self._authorizer.authorize(
            intent_ref=intent_ref,
            intent=request.intent,
            candidate_contract=contract,
        )
        if not authorization.allowed:
            raise TaskAdmissionDenied(authorization.denial_reason or "task_admission_denied")

        replay_key = _digest(
            {
                "intent_ref": intent_ref,
                "contract": contract.model_dump(mode="json"),
                "compiler_revision": compiler.compiler_revision,
                "policy_decision_ref": authorization.policy_decision_ref,
            }
        )
        return TaskAdmissionResult(
            intent_ref=intent_ref,
            contract=contract,
            compiler_revision=compiler.compiler_revision,
            policy_decision_ref=authorization.policy_decision_ref,
            policy_authorization=authorization.authorization,
            replay_key=f"task-admission:{replay_key[:32]}",
        )


def _validate_compiled_contract(
    request: TaskAdmissionRequest,
    kind: TaskKind,
    contract: TaskContract,
    contract_id: str,
) -> None:
    if contract.task_contract_id != contract_id:
        raise ValueError("TaskContract compiler changed admission contract identity")
    if contract.contract_revision != request.contract_revision:
        raise ValueError("TaskContract compiler changed requested contract revision")
    if contract.principal != request.principal or contract.on_behalf_of != request.on_behalf_of:
        raise ValueError("TaskContract compiler changed admission principal")
    if contract.policy_revision != request.policy_revision:
        raise ValueError("TaskContract compiler changed admission policy revision")
    if contract.task_kind is not kind:
        raise ValueError("TaskContract compiler changed admitted task kind")


def _intent_ref(intent: TaskIntent) -> str:
    return f"task-intent:{_digest(intent.model_dump(mode='json'))[:32]}"


def _contract_id(
    request: TaskAdmissionRequest,
    *,
    intent_ref: str,
    compiler_revision: str,
) -> str:
    digest = _digest(
        {
            "intent_ref": intent_ref,
            "principal": request.principal,
            "on_behalf_of": request.on_behalf_of,
            "policy_revision": request.policy_revision,
            "contract_revision": request.contract_revision,
            "compiler_revision": compiler_revision,
        }
    )
    return f"task-contract:{digest[:32]}"


def _digest(payload: object) -> str:
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
