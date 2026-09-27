from __future__ import annotations

import pytest

from packages.runtime.sandbox.programs import (
    SandboxArgumentBinding,
    SandboxArgumentEncoding,
    SandboxProgramDefinition,
    StaticSandboxProgramResolver,
)


def _resolver() -> StaticSandboxProgramResolver:
    return StaticSandboxProgramResolver(
        [
            SandboxProgramDefinition(
                program_ref="program:verify-release",
                argv_prefix=["python", "-m", "secfusion_verify"],
                argument_bindings=[
                    SandboxArgumentBinding(argument="release", flag="--release"),
                    SandboxArgumentBinding(
                        argument="context",
                        flag="--context-json",
                        required=False,
                        encoding=SandboxArgumentEncoding.JSON,
                    ),
                ],
                environment={"SECFUSION_MODE": "verify"},
            )
        ]
    )


@pytest.mark.asyncio
async def test_static_program_resolver_compiles_registered_typed_arguments() -> None:
    result = await _resolver().resolve(
        "program:verify-release",
        {
            "release": "v1.2.3;SHELL_META_LITERAL",
            "context": {"commit": "abc123", "expected": True},
        },
    )
    assert result.argv == [
        "python",
        "-m",
        "secfusion_verify",
        "--release",
        "v1.2.3;SHELL_META_LITERAL",
        "--context-json",
        '{"commit":"abc123","expected":true}',
    ]
    assert result.environment == {"SECFUSION_MODE": "verify"}


@pytest.mark.asyncio
async def test_static_program_resolver_rejects_unknown_program_or_argument() -> None:
    with pytest.raises(LookupError, match="not registered"):
        await _resolver().resolve("program:unknown", {})
    with pytest.raises(ValueError, match="argument not allowed"):
        await _resolver().resolve(
            "program:verify-release",
            {"release": "v1", "command": "unexpected"},
        )
    with pytest.raises(ValueError, match="argument required: release"):
        await _resolver().resolve("program:verify-release", {})
