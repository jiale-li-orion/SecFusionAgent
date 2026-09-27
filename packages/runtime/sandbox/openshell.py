from __future__ import annotations

import asyncio
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Protocol

from pydantic import BaseModel, Field, JsonValue, model_validator

from packages.runtime.sandbox.broker import (
    SandboxBackendExecResult,
    SandboxExecRequest,
    SandboxLeaseSpec,
    SandboxUnavailable,
)


class OpenShellCommandResult(BaseModel):
    argv: list[str]
    returncode: int
    stdout: bytes = b""
    stderr: bytes = b""
    timed_out: bool = False


class OpenShellCommandRunner(Protocol):
    async def run(
        self,
        argv: list[str],
        *,
        timeout_seconds: float,
    ) -> OpenShellCommandResult: ...


class AsyncioOpenShellCommandRunner:
    """Execute a trusted argv directly; shell parsing is intentionally unavailable."""

    def __init__(self, *, environment: Mapping[str, str] | None = None) -> None:
        self._environment = dict(environment or {})

    async def run(
        self,
        argv: list[str],
        *,
        timeout_seconds: float,
    ) -> OpenShellCommandResult:
        if not argv or not Path(argv[0]).is_absolute():
            raise ValueError("OpenShell runner requires an absolute executable path")
        if timeout_seconds <= 0:
            raise ValueError("OpenShell command timeout must be positive")
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._environment,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_seconds,
            )
        except TimeoutError:
            process.kill()
            stdout, stderr = await process.communicate()
            return OpenShellCommandResult(
                argv=argv,
                returncode=process.returncode if process.returncode is not None else -1,
                stdout=stdout,
                stderr=stderr,
                timed_out=True,
            )
        return OpenShellCommandResult(
            argv=argv,
            returncode=process.returncode or 0,
            stdout=stdout,
            stderr=stderr,
        )


class ResolvedSandboxProgram(BaseModel):
    argv: list[str] = Field(min_length=1)
    workdir: str = "/workspace"
    environment: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_program(self) -> ResolvedSandboxProgram:
        workdir = PurePosixPath(self.workdir)
        if not workdir.is_absolute() or ".." in workdir.parts:
            raise ValueError("sandbox program workdir must be a normalized absolute path")
        if any("\x00" in item for item in self.argv):
            raise ValueError("sandbox argv cannot contain NUL")
        for key, value in self.environment.items():
            if not key or "=" in key or "\x00" in key or "\x00" in value:
                raise ValueError("sandbox program environment is invalid")
        return self


class SandboxProgramResolver(Protocol):
    async def resolve(
        self,
        program_ref: str,
        arguments: dict[str, JsonValue],
    ) -> ResolvedSandboxProgram: ...


class SandboxArtifactBridge(Protocol):
    async def materialize(
        self,
        artifact_ref: str,
        *,
        destination_dir: Path,
    ) -> Path: ...

    async def ingest_bytes(
        self,
        body: bytes,
        *,
        media_type: str,
        logical_name: str,
    ) -> str: ...

    async def ingest_file(
        self,
        path: Path,
        *,
        logical_name: str,
    ) -> str: ...


class OpenShellPolicyMaterializer(Protocol):
    async def materialize(
        self,
        lease: SandboxLeaseSpec,
        *,
        destination_dir: Path,
    ) -> Path: ...


class StaticOpenShellPolicyMaterializer:
    """Copy an explicitly approved policy file; no permissive policy is synthesized."""

    def __init__(self, policy_paths: Mapping[str, Path]) -> None:
        self._policy_paths = {key: Path(value) for key, value in policy_paths.items()}

    async def materialize(
        self,
        lease: SandboxLeaseSpec,
        *,
        destination_dir: Path,
    ) -> Path:
        source = self._policy_paths.get(lease.profile.profile_id)
        if source is None:
            raise SandboxUnavailable(f"openshell_policy_unavailable:{lease.profile.profile_id}")
        if not source.is_file():
            raise SandboxUnavailable(f"openshell_policy_missing:{lease.profile.profile_id}")
        destination = destination_dir / "policy.yaml"
        await asyncio.to_thread(shutil.copyfile, source, destination)
        return destination


@dataclass(frozen=True, slots=True)
class OpenShellCliDialect:
    """Centralize CLI spelling so an installed-version probe can replace it later."""

    approval_mode: str = "manual"

    def create(
        self,
        executable: str,
        *,
        name: str,
        policy_path: Path,
        image_ref: str | None,
    ) -> list[str]:
        argv = [
            executable,
            "sandbox",
            "create",
            "--name",
            name,
            "--policy",
            str(policy_path),
            "--approval-mode",
            self.approval_mode,
            "--detach",
        ]
        if image_ref is not None:
            argv.extend(["--from", image_ref])
        return argv

    def exec(
        self,
        executable: str,
        *,
        name: str,
        program: ResolvedSandboxProgram,
    ) -> list[str]:
        argv = [
            executable,
            "sandbox",
            "exec",
            "--name",
            name,
            "--workdir",
            program.workdir,
        ]
        for key in sorted(program.environment):
            argv.extend(["--env", f"{key}={program.environment[key]}"])
        argv.append("--")
        argv.extend(program.argv)
        return argv

    def upload(
        self,
        executable: str,
        *,
        name: str,
        local_path: Path,
        remote_path: str,
    ) -> list[str]:
        return [
            executable,
            "sandbox",
            "upload",
            "--name",
            name,
            str(local_path),
            remote_path,
        ]

    def download(
        self,
        executable: str,
        *,
        name: str,
        remote_path: str,
        local_path: Path,
    ) -> list[str]:
        return [
            executable,
            "sandbox",
            "download",
            "--name",
            name,
            remote_path,
            str(local_path),
        ]

    def delete(self, executable: str, *, name: str) -> list[str]:
        return [executable, "sandbox", "delete", name]

    def get(self, executable: str, *, name: str) -> list[str]:
        return [executable, "sandbox", "get", "--name", name, "--json"]


class OpenShellBackend:
    backend_id = "openshell"

    def __init__(
        self,
        *,
        program_resolver: SandboxProgramResolver,
        artifact_bridge: SandboxArtifactBridge,
        policy_materializer: OpenShellPolicyMaterializer,
        executable: str | None = None,
        runner: OpenShellCommandRunner | None = None,
        dialect: OpenShellCliDialect | None = None,
        command_timeout_seconds: float = 30.0,
        delete_wait_seconds: float = 15.0,
        delete_poll_seconds: float = 0.25,
    ) -> None:
        resolved = executable or shutil.which("openshell")
        if resolved is None:
            raise SandboxUnavailable("openshell_cli_unavailable")
        executable_path = Path(resolved)
        if not executable_path.is_absolute():
            executable_path = executable_path.resolve()
        self._executable = str(executable_path)
        self._program_resolver = program_resolver
        self._artifact_bridge = artifact_bridge
        self._policy_materializer = policy_materializer
        self._runner = runner or AsyncioOpenShellCommandRunner()
        self._dialect = dialect or OpenShellCliDialect()
        self._command_timeout = command_timeout_seconds
        self._delete_wait = delete_wait_seconds
        self._delete_poll = delete_poll_seconds
        if min(self._command_timeout, self._delete_wait, self._delete_poll) <= 0:
            raise ValueError("OpenShell backend timeouts must be positive")

    @classmethod
    def available(cls) -> bool:
        return shutil.which("openshell") is not None

    async def create(self, lease: SandboxLeaseSpec) -> str:
        name = _sandbox_name(lease.execution_id)
        with TemporaryDirectory(prefix="secfusion-openshell-create-") as raw_dir:
            temp_dir = Path(raw_dir)
            policy_path = await self._policy_materializer.materialize(
                lease,
                destination_dir=temp_dir,
            )
            _require_local_file(policy_path, root=temp_dir, label="OpenShell policy")
            result = await self._runner.run(
                self._dialect.create(
                    self._executable,
                    name=name,
                    policy_path=policy_path,
                    image_ref=lease.profile.image_ref_or_digest,
                ),
                timeout_seconds=self._command_timeout,
            )
            _require_success(result, "openshell_create_failed")
            try:
                await self._upload_artifacts(
                    name,
                    lease.workspace_artifact_refs,
                    remote_root="/workspace/inputs",
                    temp_dir=temp_dir / "workspace",
                )
                await self._upload_artifacts(
                    name,
                    lease.readonly_artifact_refs,
                    remote_root="/workspace/readonly",
                    temp_dir=temp_dir / "readonly",
                )
            except Exception:
                await self._delete_best_effort(name)
                raise
        return name

    async def exec(
        self,
        backend_handle_ref: str,
        request: SandboxExecRequest,
        *,
        timeout_seconds: float,
    ) -> SandboxBackendExecResult:
        name = _require_handle(backend_handle_ref)
        program = await self._program_resolver.resolve(request.program_ref, request.arguments)
        with TemporaryDirectory(prefix="secfusion-openshell-exec-") as raw_dir:
            temp_dir = Path(raw_dir)
            await self._upload_artifacts(
                name,
                request.input_artifact_refs,
                remote_root=f"/workspace/operation-inputs/{_safe_component(request.operation_id)}",
                temp_dir=temp_dir / "inputs",
            )
            result = await self._runner.run(
                self._dialect.exec(self._executable, name=name, program=program),
                timeout_seconds=timeout_seconds,
            )
        stdout_ref = await self._artifact_bridge.ingest_bytes(
            result.stdout,
            media_type="text/plain; charset=utf-8",
            logical_name=f"{request.operation_id}.stdout",
        )
        stderr_ref = await self._artifact_bridge.ingest_bytes(
            result.stderr,
            media_type="text/plain; charset=utf-8",
            logical_name=f"{request.operation_id}.stderr",
        )
        if result.timed_out:
            return SandboxBackendExecResult(
                status="timed_out",
                stdout_artifact_ref=stdout_ref,
                stderr_artifact_ref=stderr_ref,
                failure_code="openshell_exec_timeout",
            )
        return SandboxBackendExecResult(
            status="succeeded" if result.returncode == 0 else "failed",
            exit_code=result.returncode,
            stdout_artifact_ref=stdout_ref,
            stderr_artifact_ref=stderr_ref,
            failure_code=(None if result.returncode == 0 else "openshell_exec_failed"),
        )

    async def export(
        self,
        backend_handle_ref: str,
        relative_paths: list[str],
    ) -> list[str]:
        name = _require_handle(backend_handle_ref)
        refs: list[str] = []
        with TemporaryDirectory(prefix="secfusion-openshell-export-") as raw_dir:
            temp_dir = Path(raw_dir)
            for index, relative in enumerate(relative_paths):
                safe_relative = _safe_relative_path(relative)
                local_path = temp_dir / f"export-{index}-{safe_relative.name}"
                result = await self._runner.run(
                    self._dialect.download(
                        self._executable,
                        name=name,
                        remote_path=f"/workspace/{safe_relative.as_posix()}",
                        local_path=local_path,
                    ),
                    timeout_seconds=self._command_timeout,
                )
                _require_success(result, "openshell_download_failed")
                if not local_path.is_file():
                    raise SandboxUnavailable("openshell_download_missing_output")
                refs.append(
                    await self._artifact_bridge.ingest_file(
                        local_path,
                        logical_name=safe_relative.name,
                    )
                )
        return refs

    async def destroy(self, backend_handle_ref: str) -> None:
        name = _require_handle(backend_handle_ref)
        result = await self._runner.run(
            self._dialect.delete(self._executable, name=name),
            timeout_seconds=self._command_timeout,
        )
        _require_success(result, "openshell_delete_failed")
        deadline = asyncio.get_running_loop().time() + self._delete_wait
        while asyncio.get_running_loop().time() < deadline:
            probe = await self._runner.run(
                self._dialect.get(self._executable, name=name),
                timeout_seconds=min(self._command_timeout, self._delete_poll * 4),
            )
            if probe.returncode != 0:
                return
            await asyncio.sleep(self._delete_poll)
        raise SandboxUnavailable("openshell_delete_not_confirmed")

    async def _upload_artifacts(
        self,
        name: str,
        refs: list[str],
        *,
        remote_root: str,
        temp_dir: Path,
    ) -> None:
        if not refs:
            return
        await asyncio.to_thread(temp_dir.mkdir, parents=True, exist_ok=True)
        for index, artifact_ref in enumerate(refs):
            if not artifact_ref.startswith("artifact:"):
                raise ValueError("OpenShell backend only accepts ArtifactRef inputs")
            local_path = await self._artifact_bridge.materialize(
                artifact_ref,
                destination_dir=temp_dir,
            )
            _require_local_file(local_path, root=temp_dir, label="sandbox artifact")
            remote = f"{remote_root}/{index:04d}-{_safe_component(local_path.name)}"
            result = await self._runner.run(
                self._dialect.upload(
                    self._executable,
                    name=name,
                    local_path=local_path,
                    remote_path=remote,
                ),
                timeout_seconds=self._command_timeout,
            )
            _require_success(result, "openshell_upload_failed")

    async def _delete_best_effort(self, name: str) -> None:
        try:
            await self._runner.run(
                self._dialect.delete(self._executable, name=name),
                timeout_seconds=self._command_timeout,
            )
        except Exception:
            return


def build_openshell_backend_aliases(backend: OpenShellBackend) -> dict[str, OpenShellBackend]:
    """Expose one enforcement adapter for profiles that additionally require Docker."""

    aliases = {"openshell": backend}
    if shutil.which("docker") is not None:
        aliases["openshell+docker"] = backend
    return aliases


def _sandbox_name(execution_id: str) -> str:
    digest = __import__("hashlib").sha256(execution_id.encode()).hexdigest()[:20]
    return f"secfusion-{digest}"


def _safe_component(value: str) -> str:
    normalized = "".join(
        character if character.isalnum() or character in "-_." else "-" for character in value
    )
    normalized = normalized.strip(".-_")
    if not normalized:
        raise ValueError("sandbox path component becomes empty after normalization")
    return normalized[:96]


def _safe_relative_path(value: str) -> PurePosixPath:
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        raise ValueError("sandbox export path must be normalized relative path")
    return candidate


def _require_handle(value: str) -> str:
    if not value.startswith("secfusion-"):
        raise ValueError("invalid OpenShell backend handle")
    return value


def _require_local_file(path: Path, *, root: Path, label: str) -> None:
    resolved_root = root.resolve()
    resolved = path.resolve()
    if not resolved.is_file() or not resolved.is_relative_to(resolved_root):
        raise SandboxUnavailable(
            f"{label} must be a regular file inside the controlled staging root"
        )


def _require_success(result: OpenShellCommandResult, failure_code: str) -> None:
    if result.timed_out:
        raise SandboxUnavailable(f"{failure_code}:timeout")
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace")[:512]
        raise SandboxUnavailable(f"{failure_code}:{detail}")
