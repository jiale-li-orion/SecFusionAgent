from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.runtime.model import (
    ModelAttemptStatus,
    ModelRetryPolicy,
    ModelUsageSource,
    RecordedModelProvider,
)
from packages.runtime.model.storage import ModelAttemptModel, ModelRequestModel
from packages.shared.db import Base
from packages.shared.model_provider import (
    ModelProviderAuthError,
    ModelProviderTransientError,
    ProviderModelResult,
    ProviderUsage,
    StructuredModelRequest,
)


class Result(BaseModel):
    value: str


class MetadataProvider:
    name = "test-model"
    version = "adapter-v1"

    async def generate_structured(self, request, response_model):
        return (await self.generate_structured_result(request, response_model)).output

    async def generate_structured_result(self, request, response_model):
        del request
        return ProviderModelResult(
            output=response_model(value="ok"),
            actual_model="test-model-actual",
            provider_request_id="provider-request-1",
            usage=ProviderUsage(
                input_tokens=12,
                output_tokens=3,
                total_tokens=15,
                cached_input_tokens=4,
            ),
            response_metadata={"response_format_fallback": True},
        )


class RateLimitedProvider:
    name = "rate-limited-model"
    version = "adapter-v1"

    async def generate_structured(self, request, response_model):
        del request, response_model
        raise RuntimeError("model provider rate limit reached (429)")


class FlakyProvider:
    name = "flaky-model"
    version = "adapter-v1"

    def __init__(self) -> None:
        self.calls = 0

    async def generate_structured(self, request, response_model):
        del request
        self.calls += 1
        if self.calls == 1:
            raise ModelProviderTransientError("provider returned HTTP 503")
        return response_model(value="recovered")


class AuthFailureProvider:
    name = "auth-model"
    version = "adapter-v1"

    def __init__(self) -> None:
        self.calls = 0

    async def generate_structured(self, request, response_model):
        del request, response_model
        self.calls += 1
        raise ModelProviderAuthError("model provider authentication failed with HTTP 401")


class SlowProvider:
    name = "slow-model"
    version = "adapter-v1"

    async def generate_structured(self, request, response_model):
        del request
        await asyncio.sleep(0.05)
        return response_model(value="too-late")


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _request() -> StructuredModelRequest:
    return StructuredModelRequest(
        system_instruction="decide",
        data={"x": 1},
        metadata={
            "model_purpose": "m6.decision",
            "prompt_revision": "decision-v1",
            "request_owner_ref": "case:case-1",
            "case_id": "case-1",
        },
    )


def _request_with_wall_seconds(seconds: float) -> StructuredModelRequest:
    request = _request()
    return request.model_copy(
        update={"metadata": {**request.metadata, "model_wall_seconds": seconds}}
    )


@pytest.mark.asyncio
async def test_recorded_provider_persists_request_attempt_usage_and_metadata() -> None:
    engine, factory = await _database()
    try:
        provider = RecordedModelProvider(factory, MetadataProvider())
        result = await provider.generate_structured(_request(), Result)
        assert result == Result(value="ok")

        async with factory() as session:
            request = await session.scalar(select(ModelRequestModel))
            attempt = await session.scalar(select(ModelAttemptModel))
            assert request is not None
            assert request.purpose == "m6.decision"
            assert request.request_owner_ref == "case:case-1"
            assert request.case_id == "case-1"
            assert request.request_digest
            assert attempt is not None
            assert attempt.model_request_id == request.model_request_id
            assert attempt.status == ModelAttemptStatus.SUCCEEDED.value
            assert attempt.actual_model == "test-model-actual"
            assert attempt.provider_request_id == "provider-request-1"
            assert attempt.usage_json == {
                "input_tokens": 12,
                "output_tokens": 3,
                "total_tokens": 15,
                "cached_input_tokens": 4,
                "reasoning_tokens": None,
                "provider_cost": None,
                "measurement_source": ModelUsageSource.PROVIDER_EXACT.value,
            }
            assert attempt.cache_usage_json["cached_input_tokens"] == 4
            assert attempt.response_metadata_json["response_format_fallback"] is True
            assert attempt.finished_at is not None
            assert attempt.latency_ms is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_recorded_provider_enforces_logical_model_wall_deadline() -> None:
    engine, factory = await _database()
    try:
        provider = RecordedModelProvider(
            factory,
            SlowProvider(),
            retry_policy=ModelRetryPolicy(max_attempts=3, base_delay_seconds=0),
        )
        with pytest.raises(TimeoutError):
            await provider.generate_structured(_request_with_wall_seconds(0.01), Result)

        async with factory() as session:
            attempts = list(await session.scalars(select(ModelAttemptModel)))
            assert len(attempts) == 1
            assert attempts[0].status == ModelAttemptStatus.FAILED.value
            assert attempts[0].failure_class == "timeout_before_response"
            assert attempts[0].response_metadata_json["retry_scheduled"] is False
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_recorded_provider_retries_transient_failure_as_distinct_attempts() -> None:
    engine, factory = await _database()
    try:
        inner = FlakyProvider()
        provider = RecordedModelProvider(
            factory,
            inner,
            retry_policy=ModelRetryPolicy(max_attempts=3, base_delay_seconds=0),
        )
        result = await provider.generate_structured(_request(), Result)
        assert result == Result(value="recovered")
        assert inner.calls == 2

        async with factory() as session:
            attempts = list(
                await session.scalars(select(ModelAttemptModel).order_by(ModelAttemptModel.ordinal))
            )
            assert [item.ordinal for item in attempts] == [1, 2]
            assert [item.status for item in attempts] == [
                ModelAttemptStatus.FAILED.value,
                ModelAttemptStatus.SUCCEEDED.value,
            ]
            assert attempts[0].failure_class == "provider_5xx"
            assert attempts[0].response_metadata_json["retry_scheduled"] is True
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_recorded_provider_does_not_retry_auth_failure() -> None:
    engine, factory = await _database()
    try:
        inner = AuthFailureProvider()
        provider = RecordedModelProvider(
            factory,
            inner,
            retry_policy=ModelRetryPolicy(max_attempts=3, base_delay_seconds=0),
        )
        with pytest.raises(ModelProviderAuthError):
            await provider.generate_structured(_request(), Result)
        assert inner.calls == 1

        async with factory() as session:
            attempts = list(await session.scalars(select(ModelAttemptModel)))
            assert len(attempts) == 1
            assert attempts[0].failure_class == "auth_error"
            assert attempts[0].response_metadata_json["retry_scheduled"] is False
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_recorded_provider_keeps_failed_attempt_instead_of_overwriting_it() -> None:
    engine, factory = await _database()
    try:
        provider = RecordedModelProvider(factory, RateLimitedProvider())
        with pytest.raises(RuntimeError, match="rate limit"):
            await provider.generate_structured(_request(), Result)

        async with factory() as session:
            attempt = await session.scalar(select(ModelAttemptModel))
            assert attempt is not None
            assert attempt.status == ModelAttemptStatus.FAILED.value
            assert attempt.failure_class == "rate_limited"
            assert attempt.finished_at is not None
            assert attempt.usage_json["measurement_source"] == ModelUsageSource.UNAVAILABLE.value
    finally:
        await engine.dispose()
