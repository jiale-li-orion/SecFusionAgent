from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, Field, JsonValue

TStructured = TypeVar("TStructured", bound=BaseModel)


class StructuredModelRequest(BaseModel):
    system_instruction: str
    data: dict[str, JsonValue]
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class ProviderUsage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None


@dataclass(frozen=True)
class ProviderModelResult[TStructured: BaseModel]:
    output: TStructured
    actual_model: str
    provider_request_id: str | None = None
    usage: ProviderUsage | None = None
    response_metadata: dict[str, JsonValue] | None = None


class ModelProvider(Protocol):
    name: str
    version: str

    async def generate_structured(
        self,
        request: StructuredModelRequest,
        response_model: type[TStructured],
    ) -> TStructured: ...


@runtime_checkable
class MetadataModelProvider(ModelProvider, Protocol):
    async def generate_structured_result(
        self,
        request: StructuredModelRequest,
        response_model: type[TStructured],
    ) -> ProviderModelResult[TStructured]: ...
