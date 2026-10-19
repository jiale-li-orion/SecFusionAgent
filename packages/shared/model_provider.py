from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, JsonValue

TStructured = TypeVar("TStructured", bound=BaseModel)


class ModelProviderError(RuntimeError):
    """Base error for a physical model-provider request."""

    retryable = False

    def __init__(
        self,
        message: str,
        *,
        response_metadata: ProviderResponseMetadata | None = None,
        raw_response_content: str | None = None,
    ) -> None:
        super().__init__(message)
        self.response_metadata = response_metadata
        # Opt-in visible output only; never include this in exception args or metadata.
        self.raw_response_content = raw_response_content


class ModelProviderTransientError(ModelProviderError):
    """A request may be retried without changing the logical model request."""

    retryable = True

    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: float | None = None,
        response_metadata: ProviderResponseMetadata | None = None,
        raw_response_content: str | None = None,
    ) -> None:
        super().__init__(
            message, response_metadata=response_metadata, raw_response_content=raw_response_content,
        )
        self.retry_after_seconds = retry_after_seconds


class ModelProviderRateLimited(ModelProviderTransientError):
    pass


class ModelProviderMalformedOutputError(ModelProviderTransientError):
    """The provider returned an incomplete or syntactically invalid JSON response."""


class ModelProviderAuthError(ModelProviderError):
    pass


class ModelProviderResponseError(ModelProviderError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_metadata: ProviderResponseMetadata | None = None,
        raw_response_content: str | None = None,
    ) -> None:
        super().__init__(
            message, response_metadata=response_metadata, raw_response_content=raw_response_content,
        )
        self.status_code = status_code


class StructuredModelRequest(BaseModel):
    system_instruction: str
    data: dict[str, JsonValue]
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class ProviderUsage(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None


class ProviderResponseMetadata(BaseModel):
    """Immutable, provider-neutral facts retained even when structured output is invalid."""

    model_config = ConfigDict(frozen=True)

    actual_model: str
    provider_request_id: str | None = None
    usage: ProviderUsage | None = None
    finish_reason: str | None = None


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
