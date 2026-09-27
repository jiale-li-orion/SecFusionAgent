from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from packages.runtime.sandbox.broker import (
    SandboxExecRequest,
    SandboxLeaseSpec,
    SandboxUnavailable,
)
from packages.runtime.sandbox.contracts import IsolationClass, SandboxProfile
from packages.runtime.sandbox.openshell import (
    AsyncioOpenShellCommandRunner,
    OpenShellBackend,
    OpenShellCommandResult,
    ResolvedSandboxProgram,
    StaticOpenShellPolicyMaterializer,
    build_openshell_backend_aliases,
)


class _Runner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], float]] = []
        self.deleted: set[str] = set()

    async def run(self, argv: list[str], *, timeout_seconds: float) -> OpenShellCommandResult:
        self.calls.append((list(argv), timeout_seconds))
        action = argv[2] if len(argv) > 2 else ""
        if action == "exec":
            return OpenShellCommandResult(
                argv=argv,
                returncode=0,
                stdout=b"verified\n",
                stderr=b"",
            )
        if action == "download":
            local_path = Path(argv[-1])
            await asyncio.to_thread(local_path.write_bytes, b"exported")
            return OpenShellCommandResult(argv=argv, returncode=0)
        if action == "delete":
            self.deleted.add(argv[-1])
            return OpenShellCommandResult(argv=argv, returncode=0)
        if action == "get":
            name = argv[argv.index("--name") + 1]
            return OpenShellCommandResult(
                argv=argv,
                returncode=1 if name in self.deleted else 0,
            )
        return OpenShellCommandResult(argv=argv, returncode=0)


class _ProgramResolver:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def resolve(self, program_ref: str, arguments):
        self.calls.append((program_ref, dict(arguments)))
        return ResolvedSandboxProgram(
            argv=["python", "-m", "secfusion_verify", "--release", str(arguments["release"])],
            workdir="/workspace",
            environment={"SECFUSION_MODE": "verify"},
        )


class _ArtifactBridge:
    def __init__(self) -> None:
        self.materialized: list[str] = []
        self.ingested_bytes: list[tuple[str, bytes]] = []
        self.ingested_files: list[str] = []

    async def materialize(self, artifact_ref: str, *, destination_dir: Path) -> Path:
        await asyncio.to_thread(destination_dir.mkdir, parents=True, exist_ok=True)
        path = destination_dir / f"{artifact_ref.removeprefix('artifact:')}.bin"
        await asyncio.to_thread(path.write_bytes, b"input")
        self.materialized.append(artifact_ref)
        return path

    async def ingest_bytes(self, body: bytes, *, media_type: str, logical_name: str) -> str:
        del media_type
        self.ingested_bytes.append((logical_name, body))
        return f"artifact:captured:{logical_name}"

    async def ingest_file(self, path: Path, *, logical_name: str) -> str:
        assert await asyncio.to_thread(path.read_bytes) == b"exported"
        self.ingested_files.append(logical_name)
        return f"artifact:export:{logical_name}"


def _profile() -> SandboxProfile:
    return SandboxProfile(
        profile_id="process_restricted",
        revision="1",
        isolation_class=IsolationClass.PROCESS_RESTRICTED,
        backend="openshell",
        rootfs="read_only",
        network_mode="deny",
    )


def _lease(*, workspace_refs: list[str] | None = None) -> SandboxLeaseSpec:
    return SandboxLeaseSpec(
        execution_id="execution:verify-123",
        task_run_id="run-123",
        profile=_profile(),
        workspace_artifact_refs=workspace_refs or [],
    )


@pytest.mark.asyncio
async def test_openshell_backend_requires_approved_policy_and_builds_trusted_cli(
    tmp_path: Path,
) -> None:
    policy = tmp_path / "policy.yaml"
    policy.write_text("version: 1\n", encoding="utf-8")
    runner = _Runner()
    resolver = _ProgramResolver()
    artifacts = _ArtifactBridge()
    backend = OpenShellBackend(
        program_resolver=resolver,
        artifact_bridge=artifacts,
        policy_materializer=StaticOpenShellPolicyMaterializer({"process_restricted": policy}),
        executable="/usr/local/bin/openshell",
        runner=runner,
        command_timeout_seconds=5,
        delete_wait_seconds=1,
        delete_poll_seconds=0.01,
    )

    handle = await backend.create(_lease(workspace_refs=["artifact:repo-snapshot"]))
    assert handle.startswith("secfusion-")
    create_argv = runner.calls[0][0]
    assert create_argv[:3] == ["/usr/local/bin/openshell", "sandbox", "create"]
    assert "--policy" in create_argv
    assert "--approval-mode" in create_argv
    assert "manual" in create_argv
    assert "--detach" in create_argv
    assert artifacts.materialized == ["artifact:repo-snapshot"]
    upload_argv = next(argv for argv, _ in runner.calls if argv[2] == "upload")
    assert upload_argv[-1].startswith("/workspace/inputs/")

    sentinel = "v1.2.3;SHELL_META_MUST_STAY_LITERAL"
    result = await backend.exec(
        handle,
        SandboxExecRequest(
            operation_id="verify-release",
            program_ref="program:verify-release",
            arguments={"release": sentinel},
            requested_timeout_seconds=3,
        ),
        timeout_seconds=3,
    )
    assert result.status == "succeeded"
    assert result.stdout_artifact_ref == "artifact:captured:verify-release.stdout"
    exec_argv = next(argv for argv, _ in runner.calls if argv[2] == "exec")
    separator = exec_argv.index("--")
    assert exec_argv[separator + 1 :] == [
        "python",
        "-m",
        "secfusion_verify",
        "--release",
        sentinel,
    ]
    assert resolver.calls == [("program:verify-release", {"release": sentinel})]

    exports = await backend.export(handle, ["reports/result.json"])
    assert exports == ["artifact:export:result.json"]
    await backend.destroy(handle)
    assert any(argv[2] == "delete" for argv, _ in runner.calls)
    assert any(argv[2] == "get" for argv, _ in runner.calls)


@pytest.mark.asyncio
async def test_openshell_backend_fails_closed_without_policy() -> None:
    backend = OpenShellBackend(
        program_resolver=_ProgramResolver(),
        artifact_bridge=_ArtifactBridge(),
        policy_materializer=StaticOpenShellPolicyMaterializer({}),
        executable="/usr/local/bin/openshell",
        runner=_Runner(),
    )
    with pytest.raises(SandboxUnavailable, match="openshell_policy_unavailable"):
        await backend.create(_lease())


@pytest.mark.asyncio
async def test_asyncio_runner_never_accepts_shell_style_relative_executable() -> None:
    runner = AsyncioOpenShellCommandRunner()
    with pytest.raises(ValueError, match="absolute executable"):
        await runner.run(["openshell", "sandbox", "get"], timeout_seconds=1)


@pytest.mark.asyncio
async def test_openshell_exec_timeout_is_a_typed_backend_failure(tmp_path: Path) -> None:
    class _TimeoutRunner(_Runner):
        async def run(
            self,
            argv: list[str],
            *,
            timeout_seconds: float,
        ) -> OpenShellCommandResult:
            self.calls.append((list(argv), timeout_seconds))
            if len(argv) > 2 and argv[2] == "exec":
                return OpenShellCommandResult(
                    argv=argv,
                    returncode=-1,
                    stdout=b"partial",
                    stderr=b"deadline",
                    timed_out=True,
                )
            return OpenShellCommandResult(argv=argv, returncode=0)

    policy = tmp_path / "policy.yaml"
    policy.write_text("version: 1\n", encoding="utf-8")
    backend = OpenShellBackend(
        program_resolver=_ProgramResolver(),
        artifact_bridge=_ArtifactBridge(),
        policy_materializer=StaticOpenShellPolicyMaterializer({"process_restricted": policy}),
        executable="/usr/local/bin/openshell",
        runner=_TimeoutRunner(),
    )
    handle = await backend.create(_lease())
    result = await backend.exec(
        handle,
        SandboxExecRequest(
            operation_id="slow",
            program_ref="program:slow",
            arguments={"release": "v1"},
            requested_timeout_seconds=1,
        ),
        timeout_seconds=1,
    )
    assert result.status == "timed_out"
    assert result.failure_code == "openshell_exec_timeout"
    assert result.stdout_artifact_ref == "artifact:captured:slow.stdout"


def test_openshell_backend_reports_host_availability_and_docker_alias(monkeypatch) -> None:
    def fake_which(name: str) -> str | None:
        return {
            "openshell": "/usr/local/bin/openshell",
            "docker": "/usr/bin/docker",
        }.get(name)

    monkeypatch.setattr("packages.runtime.sandbox.openshell.shutil.which", fake_which)
    assert OpenShellBackend.available() is True
    backend = OpenShellBackend(
        program_resolver=_ProgramResolver(),
        artifact_bridge=_ArtifactBridge(),
        policy_materializer=StaticOpenShellPolicyMaterializer({}),
        executable="/usr/local/bin/openshell",
        runner=_Runner(),
    )
    aliases = build_openshell_backend_aliases(backend)
    assert set(aliases) == {"openshell", "openshell+docker"}
