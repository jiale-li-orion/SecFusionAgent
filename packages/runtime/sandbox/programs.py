from __future__ import annotations

import json
from enum import StrEnum

from pydantic import BaseModel, Field, JsonValue, model_validator

from packages.runtime.sandbox.openshell import ResolvedSandboxProgram


class SandboxArgumentEncoding(StrEnum):
    SCALAR = "scalar"
    JSON = "json"


class SandboxArgumentBinding(BaseModel):
    argument: str
    flag: str | None = None
    required: bool = True
    encoding: SandboxArgumentEncoding = SandboxArgumentEncoding.SCALAR

    @model_validator(mode="after")
    def validate_binding(self) -> SandboxArgumentBinding:
        if not self.argument.strip():
            raise ValueError("sandbox argument binding requires argument name")
        if self.flag is not None:
            if not self.flag.startswith("-") or any(character.isspace() for character in self.flag):
                raise ValueError("sandbox argument flag must be a single CLI flag token")
        return self


class SandboxProgramDefinition(BaseModel):
    program_ref: str
    argv_prefix: list[str] = Field(min_length=1)
    argument_bindings: list[SandboxArgumentBinding] = Field(default_factory=list)
    workdir: str = "/workspace"
    environment: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_program(self) -> SandboxProgramDefinition:
        if not self.program_ref.startswith("program:"):
            raise ValueError("SandboxProgramDefinition requires program: reference")
        names = [item.argument for item in self.argument_bindings]
        if len(names) != len(set(names)):
            raise ValueError("sandbox argument bindings must be unique")
        ResolvedSandboxProgram(
            argv=list(self.argv_prefix),
            workdir=self.workdir,
            environment=self.environment,
        )
        return self


class StaticSandboxProgramResolver:
    def __init__(self, definitions: list[SandboxProgramDefinition]) -> None:
        self._definitions: dict[str, SandboxProgramDefinition] = {}
        for definition in definitions:
            if definition.program_ref in self._definitions:
                raise ValueError(f"duplicate sandbox program_ref: {definition.program_ref}")
            self._definitions[definition.program_ref] = definition

    async def resolve(
        self,
        program_ref: str,
        arguments: dict[str, JsonValue],
    ) -> ResolvedSandboxProgram:
        definition = self._definitions.get(program_ref)
        if definition is None:
            raise LookupError(f"sandbox program not registered: {program_ref}")
        bindings = {item.argument: item for item in definition.argument_bindings}
        unknown = sorted(set(arguments) - set(bindings))
        if unknown:
            raise ValueError(f"sandbox program argument not allowed: {unknown[0]}")
        missing = sorted(
            item.argument
            for item in definition.argument_bindings
            if item.required and item.argument not in arguments
        )
        if missing:
            raise ValueError(f"sandbox program argument required: {missing[0]}")

        argv = list(definition.argv_prefix)
        for binding in definition.argument_bindings:
            if binding.argument not in arguments:
                continue
            if binding.flag is not None:
                argv.append(binding.flag)
            argv.append(_encode_argument(arguments[binding.argument], binding.encoding))
        return ResolvedSandboxProgram(
            argv=argv,
            workdir=definition.workdir,
            environment=dict(definition.environment),
        )


def _encode_argument(value: JsonValue, encoding: SandboxArgumentEncoding) -> str:
    if encoding is SandboxArgumentEncoding.JSON:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float)):
        return str(value)
    raise ValueError("scalar sandbox argument must be string/number/bool/null")
