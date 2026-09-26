from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel, Field, JsonValue

TStructured = TypeVar("TStructured", bound=BaseModel)


class StructuredModelRequest(BaseModel):
    system_instruction: str
    data: dict[str, JsonValue]
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class ModelProvider(Protocol):
    name: str
    version: str

    async def generate_structured(
        self,
        request: StructuredModelRequest,
        response_model: type[TStructured],
    ) -> TStructured: ...
