from __future__ import annotations

import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, Field, JsonValue, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.runtime.execution.service import ExecutionRunService
from packages.runtime.policy.contracts import (
    Authorization,
    PolicyDecision,
    PolicyDecisionPoint,
    PolicyRequest,
)
from packages.runtime.policy.engine import StaticPolicyEngine
from packages.runtime.sandbox.contracts import (
    IsolationClass,
    SandboxProfile,
    default_sandbox_profiles,
    select_sandbox_profile,
)
from packages.runtime.storage.models import SandboxExecutionModel, SandboxInstanceModel
from packages.task_runtime.contracts.execution import ExecutionEnvelope, bounded_timeout_seconds
from packages.task_runtime.contracts.models import TaskContract


class SandboxUnavailable(RuntimeError):
    pass


class SandboxStatus(str):
    ACTIVE = "active"
    DESTROYED = "destroyed"
    FAILED = "failed"


class SandboxCreateRequest(BaseModel):
    request_id: str
    minimum_isolation: IsolationClass
    workspace_artifact_refs: list[str] = Field(default_factory=list)
    readonly_artifact_refs: list[str] = Field(default_factory=list)
    requested_writable_paths: list[str] = Field(default_factory=list)
    network_destinations: list[str] = Field(default_factory=list)
    credential_scope: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_refs(self) -> SandboxCreateRequest:
        for ref in [*self.workspace_artifact_refs, *self.readonly_artifact_refs]:
            if not ref.startswith("artifact:"):
                raise ValueError("sandbox mounts must use ArtifactRef, not host paths")
        for path in self.requested_writable_paths:
            _validate_absolute_sandbox_path(path)
        return self


class SandboxGrants(BaseModel):
    fulfilled_obligation_kinds: set[str] = Field(default_factory=set)
    network_grant_ref: str | None = None
    credential_grant_ref: str | None = None


class SandboxLeaseSpec(BaseModel):
    execution_id: str
    task_run_id: str
    profile: SandboxProfile
    workspace_artifact_refs: list[str] = Field(default_factory=list)
    readonly_artifact_refs: list[str] = Field(default_factory=list)
    writable_paths: list[str] = Field(default_factory=list)
    network_destinations: list[str] = Field(default_factory=list)
    network_grant_ref: str | None = None
    credential_scope: list[str] = Field(default_factory=list)
    credential_grant_ref: str | None = None


class SandboxInstance(BaseModel):
    instance_id: str
    execution_id: str
    task_run_id: str
    profile_id: str
    profile_revision: str
    backend: str
    backend_handle_ref: str
    status: str
    created_at: datetime


class SandboxExecRequest(BaseModel):
    operation_id: str
    program_ref: str
    arguments: dict[str, JsonValue] = Field(default_factory=dict)
    input_artifact_refs: list[str] = Field(default_factory=list)
    requested_timeout_seconds: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_program(self) -> SandboxExecRequest:
        if not self.program_ref.startswith(("program:", "artifact:")):
            raise ValueError("sandbox execution requires program/artifact reference")
        if any(not ref.startswith("artifact:") for ref in self.input_artifact_refs):
            raise ValueError("sandbox execution inputs must use ArtifactRef")
        return self


class SandboxBackendExecResult(BaseModel):
    status: str
    exit_code: int | None = None
    stdout_artifact_ref: str | None = None
    stderr_artifact_ref: str | None = None
    failure_code: str | None = None


class SandboxExecResult(BaseModel):
    sandbox_execution_id: str
    operation_id: str
    status: str
    exit_code: int | None = None
    stdout_artifact_ref: str | None = None
    stderr_artifact_ref: str | None = None
    timeout_seconds: float
    started_at: datetime
    finished_at: datetime
    failure_code: str | None = None
    replay: bool = False


class SandboxBackend(Protocol):
    backend_id: str

    async def create(self, lease: SandboxLeaseSpec) -> str: ...

    async def exec(
        self,
        backend_handle_ref: str,
        request: SandboxExecRequest,
        *,
        timeout_seconds: float,
    ) -> SandboxBackendExecResult: ...

    async def export(self, backend_handle_ref: str, relative_paths: list[str]) -> list[str]: ...

    async def destroy(self, backend_handle_ref: str) -> None: ...


class SandboxBroker:
    def __init__(
        self,
        policy_engine: StaticPolicyEngine,
        backends: dict[str, SandboxBackend],
        *,
        profiles: dict[IsolationClass, SandboxProfile] | None = None,
        available_backend_components: set[str] | None = None,
        execution_service: ExecutionRunService | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._policy = policy_engine
        self._backends = dict(backends)
        self._profiles = profiles or default_sandbox_profiles()
        self._available = (
            set(available_backend_components)
            if available_backend_components is not None
            else detect_available_backend_components()
        )
        self._execution_service = execution_service or ExecutionRunService()
        self._now = now or (lambda: datetime.now(UTC))

    async def create(
        self,
        session: AsyncSession,
        *,
        task: TaskContract,
        envelope: ExecutionEnvelope,
        request: SandboxCreateRequest,
        grants: SandboxGrants,
    ) -> SandboxInstance:
        existing = await session.scalar(
            select(SandboxInstanceModel).where(
                SandboxInstanceModel.execution_id == envelope.execution_id,
                SandboxInstanceModel.request_id == request.request_id,
            )
        )
        if existing is not None:
            if existing.status != SandboxStatus.ACTIVE or existing.backend_handle_ref is None:
                raise SandboxUnavailable(existing.failure_code or "sandbox_instance_unavailable")
            return _instance_view(existing)

        persisted_envelope = await self._execution_service.get(session, envelope.execution_id)
        if persisted_envelope != envelope:
            raise SandboxUnavailable("sandbox_execution_envelope_mismatch")

        selection = select_sandbox_profile(
            request.minimum_isolation,
            available_backends=self._available,
            profiles=self._profiles,
        )
        if not selection.available or selection.profile is None:
            raise SandboxUnavailable(selection.reason or "sandbox_unavailable")
        profile = selection.profile
        selected_profile_ref = f"{profile.profile_id}@{profile.revision}"
        if envelope.sandbox_profile_revision != selected_profile_ref:
            raise SandboxUnavailable("sandbox_profile_revision_mismatch")
        if profile.backend not in self._backends:
            raise SandboxUnavailable("sandbox_backend_adapter_unavailable")
        if not set(request.credential_scope) <= set(envelope.identity_scope):
            raise SandboxUnavailable("sandbox_credential_scope_exceeds_execution_identity")
        _validate_request_against_profile(request, profile, grants)

        policy_request = PolicyRequest(
            decision_point=PolicyDecisionPoint.SANDBOX_SELECTION,
            principal=task.principal,
            action="sandbox.create",
            resource=f"sandbox-profile:{profile.profile_id}",
            context={
                "task_contract_id": task.task_contract_id,
                "task_run_id": envelope.task_run_id,
                "execution_id": envelope.execution_id,
                "sandbox_profile": selected_profile_ref,
            },
        )
        decision = self._policy.evaluate(policy_request)
        _enforce_policy_decision(decision, grants.fulfilled_obligation_kinds)
        decision_ref = self._policy.decision_ref(policy_request, decision)

        lease = SandboxLeaseSpec(
            execution_id=envelope.execution_id,
            task_run_id=envelope.task_run_id,
            profile=profile,
            workspace_artifact_refs=request.workspace_artifact_refs,
            readonly_artifact_refs=request.readonly_artifact_refs,
            writable_paths=request.requested_writable_paths,
            network_destinations=request.network_destinations,
            network_grant_ref=grants.network_grant_ref,
            credential_scope=request.credential_scope,
            credential_grant_ref=grants.credential_grant_ref,
        )
        backend = self._backends[profile.backend]
        backend_handle_ref = await backend.create(lease)
        now = self._now()
        model = SandboxInstanceModel(
            instance_id=_stable_id(
                f"sandbox-instance:{envelope.execution_id}:{request.request_id}"
            ),
            execution_id=envelope.execution_id,
            task_run_id=envelope.task_run_id,
            request_id=request.request_id,
            profile_id=profile.profile_id,
            profile_revision=profile.revision,
            backend=profile.backend,
            backend_handle_ref=backend_handle_ref,
            request_json=request.model_dump(mode="json"),
            lease_json=lease.model_dump(mode="json"),
            policy_decision_ref=decision_ref,
            policy_decision_json=decision.model_dump(mode="json"),
            status=SandboxStatus.ACTIVE,
            created_at=now,
        )
        session.add(model)
        await session.flush()
        return _instance_view(model)

    async def exec(
        self,
        session: AsyncSession,
        *,
        envelope: ExecutionEnvelope,
        instance_id: str,
        request: SandboxExecRequest,
    ) -> SandboxExecResult:
        instance = await session.get(SandboxInstanceModel, instance_id)
        if instance is None:
            raise LookupError(f"sandbox instance not found: {instance_id}")
        if instance.execution_id != envelope.execution_id:
            raise ValueError("sandbox instance escapes ExecutionEnvelope")
        if instance.status != SandboxStatus.ACTIVE or instance.backend_handle_ref is None:
            raise SandboxUnavailable("sandbox_instance_not_active")
        existing = await session.scalar(
            select(SandboxExecutionModel).where(
                SandboxExecutionModel.instance_id == instance_id,
                SandboxExecutionModel.operation_id == request.operation_id,
            )
        )
        if existing is not None:
            if existing.result_json is None or existing.finished_at is None:
                raise RuntimeError("sandbox operation is already running")
            replay = SandboxExecResult.model_validate(existing.result_json)
            return replay.model_copy(update={"replay": True})

        lease = SandboxLeaseSpec.model_validate(instance.lease_json)
        profile = lease.profile
        timeout = bounded_timeout_seconds(
            envelope,
            now=self._now(),
            action_timeout_seconds=request.requested_timeout_seconds,
        )
        if profile.wall_timeout_seconds is not None:
            timeout = min(timeout, float(profile.wall_timeout_seconds))
        started_at = self._now()
        audit = SandboxExecutionModel(
            sandbox_execution_id=_stable_id(f"sandbox-exec:{instance_id}:{request.operation_id}"),
            instance_id=instance_id,
            operation_id=request.operation_id,
            request_json=request.model_dump(mode="json"),
            status="running",
            timeout_seconds=timeout,
            started_at=started_at,
        )
        session.add(audit)
        await session.flush()

        if timeout <= 0:
            result = SandboxExecResult(
                sandbox_execution_id=audit.sandbox_execution_id,
                operation_id=request.operation_id,
                status="timed_out",
                timeout_seconds=0,
                started_at=started_at,
                finished_at=self._now(),
                failure_code="execution_deadline_reached",
            )
            _finish_exec_audit(audit, result)
            await session.flush()
            return result

        backend = self._backends.get(instance.backend)
        if backend is None:
            raise SandboxUnavailable("sandbox_backend_adapter_unavailable")
        native = await backend.exec(
            instance.backend_handle_ref,
            request,
            timeout_seconds=timeout,
        )
        result = SandboxExecResult(
            sandbox_execution_id=audit.sandbox_execution_id,
            operation_id=request.operation_id,
            status=native.status,
            exit_code=native.exit_code,
            stdout_artifact_ref=native.stdout_artifact_ref,
            stderr_artifact_ref=native.stderr_artifact_ref,
            timeout_seconds=timeout,
            started_at=started_at,
            finished_at=self._now(),
            failure_code=native.failure_code,
        )
        _validate_backend_artifact_refs(result)
        _finish_exec_audit(audit, result)
        await session.flush()
        return result

    async def export(
        self,
        session: AsyncSession,
        *,
        instance_id: str,
        relative_paths: list[str],
    ) -> list[str]:
        instance = await session.get(SandboxInstanceModel, instance_id)
        if instance is None:
            raise LookupError(f"sandbox instance not found: {instance_id}")
        if instance.status != SandboxStatus.ACTIVE or instance.backend_handle_ref is None:
            raise SandboxUnavailable("sandbox_instance_not_active")
        lease = SandboxLeaseSpec.model_validate(instance.lease_json)
        if lease.profile.artifact_export_policy != "explicit":
            raise SandboxUnavailable("sandbox_artifact_export_disabled")
        for path in relative_paths:
            _validate_relative_export_path(path)
        backend = self._backends.get(instance.backend)
        if backend is None:
            raise SandboxUnavailable("sandbox_backend_adapter_unavailable")
        refs = await backend.export(instance.backend_handle_ref, relative_paths)
        if any(not ref.startswith("artifact:") for ref in refs):
            raise RuntimeError("sandbox backend returned non-ArtifactRef export")
        return refs

    async def destroy(self, session: AsyncSession, instance_id: str) -> None:
        instance = await session.scalar(
            select(SandboxInstanceModel)
            .where(SandboxInstanceModel.instance_id == instance_id)
            .with_for_update()
        )
        if instance is None:
            raise LookupError(f"sandbox instance not found: {instance_id}")
        if instance.status == SandboxStatus.DESTROYED:
            return
        if instance.backend_handle_ref is not None:
            backend = self._backends.get(instance.backend)
            if backend is None:
                raise SandboxUnavailable("sandbox_backend_adapter_unavailable")
            await backend.destroy(instance.backend_handle_ref)
        instance.status = SandboxStatus.DESTROYED
        instance.destroyed_at = self._now()
        await session.flush()


def detect_available_backend_components(
    *,
    which: Callable[[str], str | None] = shutil.which,
    kvm_available: bool | None = None,
) -> set[str]:
    available: set[str] = set()
    for name in ("openshell", "docker", "podman"):
        if which(name) is not None:
            available.add(name)
    has_kvm = Path("/dev/kvm").exists() if kvm_available is None else kvm_available
    if which("firecracker") is not None and has_kvm:
        available.add("firecracker")
    return available


def _validate_request_against_profile(
    request: SandboxCreateRequest,
    profile: SandboxProfile,
    grants: SandboxGrants,
) -> None:
    if not set(request.requested_writable_paths) <= set(profile.writable_paths):
        raise ValueError("sandbox writable path exceeds profile")
    if profile.network_mode == "deny" and request.network_destinations:
        raise ValueError("sandbox profile denies network")
    if profile.network_mode == "allowlist" and not set(request.network_destinations) <= set(
        profile.allowed_destinations
    ):
        raise ValueError("sandbox destination exceeds profile allowlist")
    if profile.network_mode == "proxied" and request.network_destinations:
        if grants.network_grant_ref is None:
            raise ValueError("proxied sandbox network requires NetworkGrant")
    if request.credential_scope:
        if profile.credential_injection != "gateway":
            raise ValueError("sandbox profile does not allow credential injection")
        if grants.credential_grant_ref is None:
            raise ValueError("sandbox credential scope requires CredentialGrant")


def _enforce_policy_decision(
    decision: PolicyDecision,
    fulfilled_obligation_kinds: set[str],
) -> None:
    if decision.authorization is not Authorization.PERMIT:
        raise SandboxUnavailable(f"sandbox_policy_{decision.authorization.value}")
    required = {item.kind for item in [*decision.constraints, *decision.obligations]}
    missing = sorted(required - fulfilled_obligation_kinds)
    if missing:
        raise SandboxUnavailable(f"sandbox_policy_obligation_unsatisfied:{','.join(missing)}")


def _finish_exec_audit(model: SandboxExecutionModel, result: SandboxExecResult) -> None:
    model.result_json = result.model_dump(mode="json")
    model.status = result.status
    model.finished_at = result.finished_at
    model.failure_code = result.failure_code


def _instance_view(model: SandboxInstanceModel) -> SandboxInstance:
    if model.backend_handle_ref is None:
        raise SandboxUnavailable(model.failure_code or "sandbox_instance_unavailable")
    return SandboxInstance(
        instance_id=model.instance_id,
        execution_id=model.execution_id,
        task_run_id=model.task_run_id,
        profile_id=model.profile_id,
        profile_revision=model.profile_revision,
        backend=model.backend,
        backend_handle_ref=model.backend_handle_ref,
        status=model.status,
        created_at=model.created_at,
    )


def _validate_backend_artifact_refs(result: SandboxExecResult) -> None:
    refs = [result.stdout_artifact_ref, result.stderr_artifact_ref]
    if any(ref is not None and not ref.startswith("artifact:") for ref in refs):
        raise RuntimeError("sandbox backend output must be ArtifactRef")


def _validate_absolute_sandbox_path(path: str) -> None:
    candidate = PurePosixPath(path)
    if not candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("sandbox writable path must be normalized absolute sandbox path")


def _validate_relative_export_path(path: str) -> None:
    candidate = PurePosixPath(path)
    if candidate.is_absolute() or ".." in candidate.parts or not path.strip():
        raise ValueError("sandbox export path must be normalized relative path")


def _stable_id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"secfusion:{value}"))
