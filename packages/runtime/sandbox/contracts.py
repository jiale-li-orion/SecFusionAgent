from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class IsolationClass(StrEnum):
    NONE = "none"
    PROCESS_RESTRICTED = "process_restricted"
    CONTAINER_STANDARD = "container_standard"
    MICROVM_UNTRUSTED = "microvm_untrusted"
    FULLVM_BROWSER = "fullvm_browser"


_ISOLATION_RANK: dict[IsolationClass, int] = {
    IsolationClass.NONE: 0,
    IsolationClass.PROCESS_RESTRICTED: 1,
    IsolationClass.CONTAINER_STANDARD: 2,
    IsolationClass.MICROVM_UNTRUSTED: 3,
    IsolationClass.FULLVM_BROWSER: 4,
}


class SandboxProfile(BaseModel):
    profile_id: str
    revision: str
    isolation_class: IsolationClass
    backend: str
    image_ref_or_digest: str | None = None
    run_as_uid_gid: str | None = None
    cpu_limit: float | None = Field(default=None, gt=0)
    memory_limit: int | None = Field(default=None, gt=0)
    pids_limit: int | None = Field(default=None, gt=0)
    wall_timeout_seconds: int | None = Field(default=None, gt=0)
    rootfs: str = "read_only"
    writable_paths: list[str] = Field(default_factory=list)
    readonly_mounts: list[str] = Field(default_factory=list)
    seccomp_profile: str | None = None
    landlock_profile: str | None = None
    linux_capabilities: list[str] = Field(default_factory=list)
    no_new_privs: bool = True
    network_mode: str = "deny"
    allowed_destinations: list[str] = Field(default_factory=list)
    credential_injection: str = "none"
    artifact_export_policy: str = "explicit"
    teardown_policy: str = "destroy"
    require_hardware_virtualization: bool = False
    fallback: str = "deny"

    @model_validator(mode="after")
    def enforce_v1_security_shape(self) -> SandboxProfile:
        if not self.profile_id.strip() or not self.revision.strip() or not self.backend.strip():
            raise ValueError("SandboxProfile identity/backend cannot be empty")
        if self.rootfs not in {"read_only", "overlay"}:
            raise ValueError("SandboxProfile rootfs must be read_only or overlay")
        if self.network_mode not in {"deny", "allowlist", "proxied"}:
            raise ValueError("SandboxProfile network_mode is invalid")
        if self.credential_injection not in {"none", "gateway"}:
            raise ValueError("SandboxProfile credential_injection is invalid")
        if self.linux_capabilities:
            raise ValueError("v1 Agent sandbox profiles must drop Linux capabilities")
        if not self.no_new_privs:
            raise ValueError("v1 Agent sandbox profiles require no_new_privs")
        if self.image_ref_or_digest and "@sha256:" not in self.image_ref_or_digest:
            raise ValueError("sandbox image must be pinned by digest")
        if self.isolation_class is IsolationClass.MICROVM_UNTRUSTED:
            if self.backend != "firecracker":
                raise ValueError("microvm_untrusted requires Firecracker")
            if not self.require_hardware_virtualization:
                raise ValueError("microvm_untrusted requires hardware virtualization")
            if self.fallback != "deny":
                raise ValueError("microvm_untrusted fallback must be deny")
        return self


class SandboxSelection(BaseModel):
    profile: SandboxProfile | None = None
    available: bool
    reason: str | None = None


def default_sandbox_profiles() -> dict[IsolationClass, SandboxProfile]:
    profiles = [
        SandboxProfile(
            profile_id="process_restricted",
            revision="1",
            isolation_class=IsolationClass.PROCESS_RESTRICTED,
            backend="openshell",
            rootfs="read_only",
            network_mode="deny",
        ),
        SandboxProfile(
            profile_id="container_standard",
            revision="1",
            isolation_class=IsolationClass.CONTAINER_STANDARD,
            backend="openshell+docker",
            rootfs="read_only",
            writable_paths=["/workspace", "/tmp"],
            network_mode="proxied",
            credential_injection="gateway",
        ),
        SandboxProfile(
            profile_id="microvm_untrusted",
            revision="1",
            isolation_class=IsolationClass.MICROVM_UNTRUSTED,
            backend="firecracker",
            rootfs="read_only",
            network_mode="deny",
            require_hardware_virtualization=True,
            fallback="deny",
        ),
    ]
    return {profile.isolation_class: profile for profile in profiles}


def select_sandbox_profile(
    minimum_isolation: IsolationClass,
    *,
    available_backends: set[str],
    profiles: dict[IsolationClass, SandboxProfile] | None = None,
) -> SandboxSelection:
    if minimum_isolation is IsolationClass.NONE:
        return SandboxSelection(available=True, profile=None)
    configured = profiles or default_sandbox_profiles()
    profile = configured.get(minimum_isolation)
    if profile is None:
        return SandboxSelection(available=False, reason="sandbox_profile_unavailable")
    backend_candidates = set(profile.backend.split("+"))
    if not backend_candidates <= available_backends:
        return SandboxSelection(available=False, reason="sandbox_unavailable")
    return SandboxSelection(available=True, profile=profile)


def isolation_satisfies(actual: IsolationClass, required: IsolationClass) -> bool:
    return _ISOLATION_RANK[actual] >= _ISOLATION_RANK[required]
