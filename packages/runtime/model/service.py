from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from time import monotonic
from typing import Any, cast
from uuid import uuid4

from pydantic import BaseModel, JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.runtime.artifacts import RuntimeArtifactService
from packages.runtime.model.contracts import (
    ModelAttemptRecord,
    ModelAttemptStatus,
    ModelRequestRecord,
    ModelUsage,
    ModelUsageSource,
)
from packages.runtime.model.storage import ModelAttemptModel, ModelRequestModel
from packages.shared.model_provider import (
    MetadataModelProvider,
    ModelProvider,
    ProviderModelResult,
    StructuredModelRequest,
    TStructured,
)


@dataclass(frozen=True)
class ModelRetryPolicy:
    max_attempts: int = 1
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 4.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("model retry max_attempts must be >= 1")
        if self.base_delay_seconds < 0:
            raise ValueError("model retry base delay must be >= 0")
        if self.max_delay_seconds < 0:
            raise ValueError("model retry max delay must be >= 0")

    def delay_after(self, ordinal: int, exc: Exception) -> float:
        exponential = self.base_delay_seconds * (2 ** max(0, ordinal - 1))
        requested = getattr(exc, "retry_after_seconds", None)
        if not isinstance(requested, (int, float)) or isinstance(requested, bool):
            requested = 0.0
        return min(self.max_delay_seconds, max(exponential, float(requested)))


class RecordedModelProvider:
    """Record logical model requests and physical attempts around an existing provider.

    Request/attempt rows are committed before dispatch. The provider call therefore never runs
    inside the recorder's database transaction. A second transaction records the terminal attempt.
    Payload artifacts are opt-in because prompt bodies may contain sensitive material.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        provider: ModelProvider,
        *,
        artifact_service: RuntimeArtifactService | None = None,
        retry_policy: ModelRetryPolicy | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._provider = provider
        self._artifact_service = artifact_service
        self._retry_policy = retry_policy or ModelRetryPolicy()
        self.name = provider.name
        self.version = provider.version

    async def generate_structured(
        self,
        request: StructuredModelRequest,
        response_model: type[TStructured],
    ) -> TStructured:
        coordinate = _request_coordinate(request)
        model_request_id = str(uuid4())
        request_digest = _digest(request.model_dump(mode="json"))
        request_schema_digest = _digest(StructuredModelRequest.model_json_schema())
        response_schema_digest = _digest(response_model.model_json_schema())
        requested_at = datetime.now(UTC)
        request_artifact_ref: str | None = None

        async with self._session_factory() as session, session.begin():
            if (
                self._artifact_service is not None
                and coordinate.execution_id is not None
                and coordinate.persist_payload_artifacts
            ):
                artifact = await self._artifact_service.write(
                    session,
                    execution_id=coordinate.execution_id,
                    producer_kind="model_request",
                    producer_ref=model_request_id,
                    logical_name=f"model-request-{model_request_id}.json",
                    media_type="application/json",
                    body=_canonical_bytes(_redacted_request(request)),
                    trust_class="execution_sensitive",
                )
                request_artifact_ref = artifact.artifact_ref
            session.add(
                ModelRequestModel(
                    model_request_id=model_request_id,
                    purpose=coordinate.purpose,
                    request_owner_ref=coordinate.request_owner_ref,
                    execution_id=coordinate.execution_id,
                    task_run_id=coordinate.task_run_id,
                    case_id=coordinate.case_id,
                    processing_run_id=coordinate.processing_run_id,
                    prompt_assembly_id=coordinate.prompt_assembly_id,
                    prompt_revision=coordinate.prompt_revision,
                    request_schema_digest=request_schema_digest,
                    request_digest=request_digest,
                    request_artifact_ref=request_artifact_ref,
                    requested_model=self._provider.name,
                    provider_policy_ref=coordinate.provider_policy_ref,
                    budget_ref=coordinate.budget_ref,
                    metadata_json=coordinate.public_metadata,
                    created_at=requested_at,
                )
            )

        logical_started_clock = monotonic()
        logical_deadline_clock = (
            logical_started_clock + coordinate.model_wall_seconds
            if coordinate.model_wall_seconds is not None
            else None
        )
        for ordinal in range(1, self._retry_policy.max_attempts + 1):
            model_attempt_id = str(uuid4())
            started_at = datetime.now(UTC)
            async with self._session_factory() as session, session.begin():
                session.add(
                    ModelAttemptModel(
                        model_attempt_id=model_attempt_id,
                        model_request_id=model_request_id,
                        ordinal=ordinal,
                        provider=self._provider.name,
                        adapter_revision=self._provider.version,
                        actual_model=self._provider.name,
                        provider_request_id=None,
                        started_at=started_at,
                        finished_at=None,
                        status=ModelAttemptStatus.STARTED.value,
                        failure_class=None,
                        failure_detail=None,
                        response_schema_digest=response_schema_digest,
                        response_artifact_ref=None,
                        usage_json=ModelUsage().model_dump(mode="json"),
                        cost_json={},
                        cache_usage_json={},
                        response_metadata_json={},
                        latency_ms=None,
                    )
                )

            started_clock = monotonic()
            try:
                remaining_seconds = (
                    logical_deadline_clock - monotonic()
                    if logical_deadline_clock is not None
                    else None
                )
                if remaining_seconds is not None:
                    if remaining_seconds <= 0:
                        raise TimeoutError("model logical request deadline exhausted")
                    async with asyncio.timeout(remaining_seconds):
                        provider_result = await _generate_with_metadata(
                            self._provider,
                            request,
                            response_model,
                        )
                else:
                    provider_result = await _generate_with_metadata(
                        self._provider,
                        request,
                        response_model,
                    )
            except Exception as exc:
                finished_at = datetime.now(UTC)
                latency_ms = max(0, round((monotonic() - started_clock) * 1000))
                retryable = bool(getattr(exc, "retryable", False))
                has_retry = retryable and ordinal < self._retry_policy.max_attempts
                retry_delay = self._retry_policy.delay_after(ordinal, exc) if has_retry else None
                if has_retry and logical_deadline_clock is not None:
                    assert retry_delay is not None
                    has_retry = monotonic() + retry_delay < logical_deadline_clock
                    if not has_retry:
                        retry_delay = None
                async with self._session_factory() as session, session.begin():
                    attempt = await _require_attempt(session, model_attempt_id)
                    attempt.status = ModelAttemptStatus.FAILED.value
                    attempt.failure_class = _failure_class(exc)
                    attempt.failure_detail = _failure_detail(exc)
                    attempt.finished_at = finished_at
                    attempt.response_metadata_json = {
                        "retryable": retryable,
                        "retry_scheduled": has_retry,
                        "retry_delay_seconds": retry_delay,
                    }
                    attempt.latency_ms = latency_ms
                if not has_retry:
                    raise
                assert retry_delay is not None
                if retry_delay > 0:
                    await asyncio.sleep(retry_delay)
                continue

            finished_at = datetime.now(UTC)
            latency_ms = max(0, round((monotonic() - started_clock) * 1000))
            usage = _usage(provider_result)
            response_artifact_ref: str | None = None
            async with self._session_factory() as session, session.begin():
                if (
                    self._artifact_service is not None
                    and coordinate.execution_id is not None
                    and coordinate.persist_payload_artifacts
                ):
                    artifact = await self._artifact_service.write(
                        session,
                        execution_id=coordinate.execution_id,
                        producer_kind="model_response",
                        producer_ref=model_attempt_id,
                        logical_name=f"model-response-{model_attempt_id}.json",
                        media_type="application/json",
                        body=_canonical_bytes(provider_result.output.model_dump(mode="json")),
                        trust_class="execution_sensitive",
                    )
                    response_artifact_ref = artifact.artifact_ref
                attempt = await _require_attempt(session, model_attempt_id)
                attempt.actual_model = provider_result.actual_model
                attempt.provider_request_id = provider_result.provider_request_id
                attempt.finished_at = finished_at
                attempt.status = ModelAttemptStatus.SUCCEEDED.value
                attempt.response_artifact_ref = response_artifact_ref
                attempt.usage_json = usage.model_dump(mode="json")
                attempt.cache_usage_json = cast(dict[str, object], _cache_usage(usage))
                attempt.response_metadata_json = cast(
                    dict[str, object], dict(provider_result.response_metadata or {})
                )
                attempt.latency_ms = latency_ms
            return provider_result.output

        raise RuntimeError("model retry loop exhausted without terminal result")


class _RequestCoordinate(BaseModel):
    purpose: str
    request_owner_ref: str
    prompt_revision: str
    execution_id: str | None = None
    task_run_id: str | None = None
    case_id: str | None = None
    processing_run_id: str | None = None
    prompt_assembly_id: str | None = None
    provider_policy_ref: str | None = None
    budget_ref: str | None = None
    model_wall_seconds: float | None = None
    persist_payload_artifacts: bool = False
    public_metadata: dict[str, JsonValue]


def _request_coordinate(request: StructuredModelRequest) -> _RequestCoordinate:
    metadata = request.metadata
    purpose = _required_metadata(metadata, "model_purpose")
    prompt_revision = _required_metadata(metadata, "prompt_revision")
    request_owner_ref = _string_metadata(metadata, "request_owner_ref") or _infer_owner(metadata)
    if request_owner_ref is None:
        raise ValueError("recorded model request requires request_owner_ref")
    persistence = metadata.get("model_payload_persistence")
    persist_payload_artifacts = persistence == "redacted_runtime_artifact"
    public_metadata = {
        key: value for key, value in metadata.items() if key not in _PRIVATE_METADATA_KEYS
    }
    return _RequestCoordinate(
        purpose=purpose,
        request_owner_ref=request_owner_ref,
        prompt_revision=prompt_revision,
        execution_id=_string_metadata(metadata, "execution_id"),
        task_run_id=_string_metadata(metadata, "task_run_id"),
        case_id=_string_metadata(metadata, "case_id"),
        processing_run_id=_string_metadata(metadata, "processing_run_id"),
        prompt_assembly_id=_string_metadata(metadata, "prompt_assembly_id"),
        provider_policy_ref=_string_metadata(metadata, "provider_policy_ref"),
        budget_ref=_string_metadata(metadata, "budget_ref"),
        model_wall_seconds=_positive_number_metadata(metadata, "model_wall_seconds"),
        persist_payload_artifacts=persist_payload_artifacts,
        public_metadata=public_metadata,
    )


def _infer_owner(metadata: dict[str, JsonValue]) -> str | None:
    for key, prefix in (
        ("task_run_id", "task-run"),
        ("case_id", "case"),
        ("processing_run_id", "processing-run"),
        ("document_revision_id", "document-revision"),
    ):
        value = _string_metadata(metadata, key)
        if value is not None:
            return f"{prefix}:{value}"
    return None


def _positive_number_metadata(metadata: dict[str, JsonValue], key: str) -> float | None:
    value = metadata.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return float(value)
    return None


async def _generate_with_metadata(
    provider: ModelProvider,
    request: StructuredModelRequest,
    response_model: type[TStructured],
) -> ProviderModelResult[TStructured]:
    if isinstance(provider, MetadataModelProvider):
        return await provider.generate_structured_result(request, response_model)
    output = await provider.generate_structured(request, response_model)
    return ProviderModelResult(
        output=output,
        actual_model=provider.name,
        response_metadata={},
    )


def _usage(result: ProviderModelResult[Any]) -> ModelUsage:
    provider_usage = result.usage
    if provider_usage is None:
        return ModelUsage(measurement_source=ModelUsageSource.UNAVAILABLE)
    return ModelUsage(
        input_tokens=provider_usage.input_tokens,
        output_tokens=provider_usage.output_tokens,
        total_tokens=provider_usage.total_tokens,
        cached_input_tokens=provider_usage.cached_input_tokens,
        reasoning_tokens=provider_usage.reasoning_tokens,
        measurement_source=ModelUsageSource.PROVIDER_EXACT,
    )


def _cache_usage(usage: ModelUsage) -> dict[str, JsonValue]:
    if usage.cached_input_tokens is None:
        return {}
    return {
        "cached_input_tokens": usage.cached_input_tokens,
        "measurement_source": usage.measurement_source.value,
    }


async def _require_attempt(session: AsyncSession, attempt_id: str) -> ModelAttemptModel:
    attempt = await session.get(ModelAttemptModel, attempt_id)
    if attempt is None:
        raise RuntimeError(f"model attempt disappeared: {attempt_id}")
    return attempt


async def get_model_request(
    session: AsyncSession,
    model_request_id: str,
) -> ModelRequestRecord:
    model = await session.get(ModelRequestModel, model_request_id)
    if model is None:
        raise LookupError(f"model request not found: {model_request_id}")
    return _request_view(model)


async def list_model_attempts(
    session: AsyncSession,
    model_request_id: str,
) -> list[ModelAttemptRecord]:
    models = list(
        await session.scalars(
            select(ModelAttemptModel)
            .where(ModelAttemptModel.model_request_id == model_request_id)
            .order_by(ModelAttemptModel.ordinal)
        )
    )
    return [_attempt_view(item) for item in models]


def _request_view(model: ModelRequestModel) -> ModelRequestRecord:
    return ModelRequestRecord(
        model_request_id=model.model_request_id,
        purpose=model.purpose,
        request_owner_ref=model.request_owner_ref,
        execution_id=model.execution_id,
        task_run_id=model.task_run_id,
        case_id=model.case_id,
        processing_run_id=model.processing_run_id,
        prompt_assembly_id=model.prompt_assembly_id,
        prompt_revision=model.prompt_revision,
        request_schema_digest=model.request_schema_digest,
        request_digest=model.request_digest,
        request_artifact_ref=model.request_artifact_ref,
        requested_model=model.requested_model,
        provider_policy_ref=model.provider_policy_ref,
        budget_ref=model.budget_ref,
        metadata=cast(dict[str, JsonValue], dict(model.metadata_json)),
        created_at=_utc(model.created_at),
    )


def _attempt_view(model: ModelAttemptModel) -> ModelAttemptRecord:
    return ModelAttemptRecord(
        model_attempt_id=model.model_attempt_id,
        model_request_id=model.model_request_id,
        ordinal=model.ordinal,
        provider=model.provider,
        adapter_revision=model.adapter_revision,
        actual_model=model.actual_model,
        provider_request_id=model.provider_request_id,
        started_at=_utc(model.started_at),
        finished_at=_utc(model.finished_at) if model.finished_at is not None else None,
        status=ModelAttemptStatus(model.status),
        failure_class=model.failure_class,
        failure_detail=model.failure_detail,
        response_schema_digest=model.response_schema_digest,
        response_artifact_ref=model.response_artifact_ref,
        usage=ModelUsage.model_validate(model.usage_json),
        cost=cast(dict[str, JsonValue], dict(model.cost_json)),
        cache_usage=cast(dict[str, JsonValue], dict(model.cache_usage_json)),
        response_metadata=cast(dict[str, JsonValue], dict(model.response_metadata_json)),
        latency_ms=model.latency_ms,
    )


def _failure_class(exc: Exception) -> str:
    name = exc.__class__.__name__.lower()
    detail = str(exc).lower()
    if "timeout" in name or "timeout" in detail:
        return "timeout_before_response"
    if "ratelimit" in name or "rate limit" in detail or "429" in detail:
        return "rate_limited"
    if "auth" in name or "authentication" in detail or "401" in detail or "403" in detail:
        return "auth_error"
    if "json" in detail:
        return "invalid_json"
    if "schema" in detail or "satisfy" in detail or "validation" in name:
        return "schema_validation_failed"
    if "network" in name or "connect" in detail:
        return "network_error"
    if "http 5" in detail:
        return "provider_5xx"
    return "provider_error"


def _failure_detail(exc: Exception) -> str:
    detail = str(exc).strip() or exc.__class__.__name__
    return detail[:2000]


def _redacted_request(request: StructuredModelRequest) -> dict[str, JsonValue]:
    return cast(dict[str, JsonValue], _redact(request.model_dump(mode="json")))


def _redact(value: object, *, key: str | None = None) -> object:
    if key is not None and any(marker in key.lower() for marker in _SECRET_KEY_MARKERS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): _redact(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _required_metadata(metadata: dict[str, JsonValue], key: str) -> str:
    value = _string_metadata(metadata, key)
    if value is None:
        raise ValueError(f"recorded model request requires metadata.{key}")
    return value


def _string_metadata(metadata: dict[str, JsonValue], key: str) -> str | None:
    value = metadata.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _digest(value: object) -> str:
    return sha256(_canonical_bytes(value)).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


_PRIVATE_METADATA_KEYS = {
    "model_payload_persistence",
}
_SECRET_KEY_MARKERS = (
    "authorization",
    "api_key",
    "apikey",
    "password",
    "secret",
    "credential",
    "access_token",
    "refresh_token",
)
