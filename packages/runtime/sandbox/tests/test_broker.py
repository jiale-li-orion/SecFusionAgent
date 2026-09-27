from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.runtime.execution import ExecutionRunService
from packages.runtime.policy.contracts import Authorization, PolicyDecisionPoint, PolicyObligation
from packages.runtime.policy.engine import RuntimePolicyRule, StaticPolicyEngine
from packages.runtime.sandbox import (
    IsolationClass,
    SandboxBackendExecResult,
    SandboxBroker,
    SandboxCreateRequest,
    SandboxExecRequest,
    SandboxGrants,
    SandboxLeaseSpec,
    SandboxUnavailable,
    detect_available_backend_components,
    select_sandbox_profile,
)
from packages.runtime.storage.models import (
    SandboxExecutionModel,
    SandboxInstanceModel,
)
from packages.shared.db import Base
from packages.task_runtime.contracts.execution import ExecutionEnvelope
from packages.task_runtime.contracts.models import (
    ContextManifest,
    DelegationCeiling,
    EffectCeiling,
    ExecutionProfile,
    TaskContract,
    TaskKind,
)
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.service import create_task_run

NOW = datetime(2026, 9, 27, 9, 30, tzinfo=UTC)


class FakeContainerBackend:
    backend_id = "openshell+docker"

    def __init__(self) -> None:
        self.create_calls = 0
        self.exec_calls = 0
        self.export_calls = 0
        self.destroy_calls = 0
        self.last_lease: SandboxLeaseSpec | None = None
        self.last_timeout: float | None = None

    async def create(self, lease: SandboxLeaseSpec) -> str:
        self.create_calls += 1
        self.last_lease = lease
        return "sandbox-handle:fake-1"

    async def exec(self, backend_handle_ref, request, *, timeout_seconds):
        self.exec_calls += 1
        self.last_timeout = timeout_seconds
        return SandboxBackendExecResult(
            status="succeeded",
            exit_code=0,
            stdout_artifact_ref="artifact:sandbox-stdout-1",
            stderr_artifact_ref="artifact:sandbox-stderr-1",
        )

    async def export(self, backend_handle_ref, relative_paths):
        self.export_calls += 1
        return [f"artifact:export:{path.replace('/', '-')}" for path in relative_paths]

    async def destroy(self, backend_handle_ref):
        self.destroy_calls += 1


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _task(run_id: str) -> TaskContract:
    return TaskContract(
        task_contract_id=f"verify:{run_id}",
        contract_revision=1,
        principal="user:alice",
        task_kind=TaskKind.VERIFY_VERSION_FIX,
        target_resources=["repo:vllm-project/vllm"],
        desired_state={"goal": "verify ancestry"},
        evidence_contract={"source_roles": ["primary"]},
        output_contract={"format": "decision"},
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
                policy_id="allow-container-sandbox",
                policy_revision="policy-v1",
                decision_points=[PolicyDecisionPoint.SANDBOX_SELECTION],
                principal_patterns=["user:*"],
                action_patterns=["sandbox.create"],
                resource_patterns=["sandbox-profile:container_standard"],
                authorization=Authorization.PERMIT,
            ),
            RuntimePolicyRule(
                policy_id="audit-sandbox",
                policy_revision="policy-v1",
                decision_points=[PolicyDecisionPoint.SANDBOX_SELECTION],
                principal_patterns=["user:*"],
                action_patterns=["sandbox.create"],
                resource_patterns=["sandbox-profile:container_standard"],
                obligations=[PolicyObligation(kind="require_audit_log")],
            ),
        ],
    )


async def _seed_execution(
    session,
    run_id: str,
    *,
    sandbox_profile_revision: str = "container_standard@1",
) -> tuple[TaskContract, ExecutionEnvelope]:
    task = _task(run_id)
    manifest = ContextManifest(
        context_id=f"context:{run_id}",
        context_revision=1,
        task_contract_ref=f"{task.task_contract_id}@1",
        role_ref="InvestigationRole@1",
        knowledge_revision=0,
        object_refs=["repo:vllm-project/vllm"],
        policy_context_ref="policy-context:policy-v1",
        capability_envelope_ref="capability:git-ancestry",
        budget_ref=f"budget:{run_id}",
    )
    await create_task_run(
        session,
        contract=task,
        manifest=manifest,
        role=canonical_roles()["InvestigationRole"],
        execution_envelope_ref=f"execution:{run_id}",
        stream_name="secfusion:task-events:test",
        run_id=run_id,
        now=NOW,
    )
    envelope = ExecutionEnvelope(
        execution_id=f"execution:{run_id}",
        task_contract_id=task.task_contract_id,
        task_run_id=run_id,
        role_revision="InvestigationRole@1",
        context_manifest_revision=1,
        execution_profile=ExecutionProfile.VERIFY,
        capability_scope=["git.ancestry_check"],
        deadline_at=NOW + timedelta(seconds=5),
        budget_ref=f"budget:{run_id}",
        policy_revision="policy-v1",
        identity_scope=["github:read"],
        network_policy="proxied",
        side_effect_policy="read-only",
        sandbox_profile_revision=sandbox_profile_revision,
    )
    execution = ExecutionRunService(now=lambda: NOW)
    await execution.create(session, envelope)
    await execution.start(session, envelope.execution_id)
    return task, envelope


def _request() -> SandboxCreateRequest:
    return SandboxCreateRequest(
        request_id="sandbox-create-1",
        minimum_isolation=IsolationClass.CONTAINER_STANDARD,
        workspace_artifact_refs=["artifact:repo-snapshot"],
        readonly_artifact_refs=["artifact:verification-script"],
        requested_writable_paths=["/workspace", "/tmp"],
        network_destinations=["api.github.com:443"],
        credential_scope=["github:read"],
    )


def test_backend_detection_does_not_treat_docker_as_openshell_or_kvm_as_firecracker() -> None:
    def docker_only(name: str) -> str | None:
        return "/usr/bin/docker" if name == "docker" else None

    components = detect_available_backend_components(which=docker_only, kvm_available=True)
    assert components == {"docker"}
    container = select_sandbox_profile(
        IsolationClass.CONTAINER_STANDARD,
        available_backends=components,
    )
    assert container.available is False
    assert container.reason == "sandbox_unavailable"

    def firecracker_binary(name: str) -> str | None:
        return "/usr/bin/firecracker" if name == "firecracker" else None

    without_kvm = detect_available_backend_components(
        which=firecracker_binary,
        kvm_available=False,
    )
    assert "firecracker" not in without_kvm
    with_kvm = detect_available_backend_components(
        which=firecracker_binary,
        kvm_available=True,
    )
    assert with_kvm == {"firecracker"}


def test_request_contract_rejects_host_paths_and_raw_commands() -> None:
    with pytest.raises(ValueError, match="ArtifactRef"):
        SandboxCreateRequest(
            request_id="bad-mount",
            minimum_isolation=IsolationClass.CONTAINER_STANDARD,
            workspace_artifact_refs=["/home/orion/repo"],
        )
    with pytest.raises(ValueError, match="program/artifact reference"):
        SandboxExecRequest(
            operation_id="bad-command",
            program_ref="bash -lc 'cat /etc/passwd'",
            requested_timeout_seconds=5,
        )


@pytest.mark.asyncio
async def test_sandbox_broker_is_policy_gated_bounded_audited_and_replay_safe() -> None:
    engine, factory = await _database()
    backend = FakeContainerBackend()
    broker = SandboxBroker(
        _policy(),
        {backend.backend_id: backend},
        available_backend_components={"openshell", "docker"},
        now=lambda: NOW,
    )
    run_id = str(uuid4())
    try:
        async with factory() as session, session.begin():
            task, envelope = await _seed_execution(session, run_id)
            instance = await broker.create(
                session,
                task=task,
                envelope=envelope,
                request=_request(),
                grants=SandboxGrants(
                    fulfilled_obligation_kinds={"require_audit_log"},
                    network_grant_ref="network-grant:github",
                    credential_grant_ref="credential-grant:github-read",
                ),
            )
            assert backend.create_calls == 1
            assert backend.last_lease is not None
            assert backend.last_lease.workspace_artifact_refs == ["artifact:repo-snapshot"]
            assert backend.last_lease.credential_scope == ["github:read"]
            assert backend.last_lease.credential_grant_ref == "credential-grant:github-read"
            assert "token" not in backend.last_lease.model_dump_json().lower()

            replay_instance = await broker.create(
                session,
                task=task,
                envelope=envelope,
                request=_request(),
                grants=SandboxGrants(
                    fulfilled_obligation_kinds={"require_audit_log"},
                    network_grant_ref="network-grant:github",
                    credential_grant_ref="credential-grant:github-read",
                ),
            )
            assert replay_instance.instance_id == instance.instance_id
            assert backend.create_calls == 1

            exec_request = SandboxExecRequest(
                operation_id="ancestry-1",
                program_ref="artifact:verification-script",
                arguments={"ancestor": "abc123", "descendant": "v0.21.0"},
                input_artifact_refs=["artifact:repo-snapshot"],
                requested_timeout_seconds=30,
            )
            result = await broker.exec(
                session,
                envelope=envelope,
                instance_id=instance.instance_id,
                request=exec_request,
            )
            assert result.status == "succeeded"
            assert result.timeout_seconds == 5.0
            assert backend.last_timeout == 5.0
            assert result.stdout_artifact_ref == "artifact:sandbox-stdout-1"
            assert backend.exec_calls == 1

            replay = await broker.exec(
                session,
                envelope=envelope,
                instance_id=instance.instance_id,
                request=exec_request,
            )
            assert replay.replay is True
            assert backend.exec_calls == 1

            exports = await broker.export(
                session,
                instance_id=instance.instance_id,
                relative_paths=["results/ancestry.json"],
            )
            assert exports == ["artifact:export:results-ancestry.json"]
            with pytest.raises(ValueError, match="normalized relative path"):
                await broker.export(
                    session,
                    instance_id=instance.instance_id,
                    relative_paths=["../host-secret"],
                )

            await broker.destroy(session, instance.instance_id)
            await broker.destroy(session, instance.instance_id)
            assert backend.destroy_calls == 1
            assert await session.scalar(select(func.count()).select_from(SandboxInstanceModel)) == 1
            assert (
                await session.scalar(select(func.count()).select_from(SandboxExecutionModel)) == 1
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_missing_network_or_credential_grant_blocks_before_backend_create() -> None:
    engine, factory = await _database()
    backend = FakeContainerBackend()
    broker = SandboxBroker(
        _policy(),
        {backend.backend_id: backend},
        available_backend_components={"openshell", "docker"},
        now=lambda: NOW,
    )
    run_id = str(uuid4())
    try:
        async with factory() as session, session.begin():
            task, envelope = await _seed_execution(session, run_id)
            with pytest.raises(ValueError, match="NetworkGrant"):
                await broker.create(
                    session,
                    task=task,
                    envelope=envelope,
                    request=_request(),
                    grants=SandboxGrants(
                        fulfilled_obligation_kinds={"require_audit_log"},
                        credential_grant_ref="credential-grant:github-read",
                    ),
                )
            assert backend.create_calls == 0

            with pytest.raises(ValueError, match="CredentialGrant"):
                await broker.create(
                    session,
                    task=task,
                    envelope=envelope,
                    request=_request(),
                    grants=SandboxGrants(
                        fulfilled_obligation_kinds={"require_audit_log"},
                        network_grant_ref="network-grant:github",
                    ),
                )
            assert backend.create_calls == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_docker_only_and_missing_firecracker_fail_closed_without_backend_fallback() -> None:
    engine, factory = await _database()
    backend = FakeContainerBackend()
    run_id = str(uuid4())
    try:
        async with factory() as session, session.begin():
            task, envelope = await _seed_execution(session, run_id)
            docker_only = SandboxBroker(
                _policy(),
                {backend.backend_id: backend},
                available_backend_components={"docker"},
                now=lambda: NOW,
            )
            with pytest.raises(SandboxUnavailable, match="sandbox_unavailable"):
                await docker_only.create(
                    session,
                    task=task,
                    envelope=envelope,
                    request=_request(),
                    grants=SandboxGrants(
                        fulfilled_obligation_kinds={"require_audit_log"},
                        network_grant_ref="network-grant:github",
                        credential_grant_ref="credential-grant:github-read",
                    ),
                )
            assert backend.create_calls == 0

            microvm_run_id = str(uuid4())
            microvm_task, microvm_envelope = await _seed_execution(
                session,
                microvm_run_id,
                sandbox_profile_revision="microvm_untrusted@1",
            )
            microvm_request = SandboxCreateRequest(
                request_id="microvm-1",
                minimum_isolation=IsolationClass.MICROVM_UNTRUSTED,
                workspace_artifact_refs=["artifact:repo-snapshot"],
            )
            missing_firecracker = SandboxBroker(
                _policy(),
                {backend.backend_id: backend},
                available_backend_components={"openshell", "docker"},
                now=lambda: NOW,
            )
            with pytest.raises(SandboxUnavailable, match="sandbox_unavailable"):
                await missing_firecracker.create(
                    session,
                    task=microvm_task,
                    envelope=microvm_envelope,
                    request=microvm_request,
                    grants=SandboxGrants(fulfilled_obligation_kinds={"require_audit_log"}),
                )
            assert backend.create_calls == 0
    finally:
        await engine.dispose()
