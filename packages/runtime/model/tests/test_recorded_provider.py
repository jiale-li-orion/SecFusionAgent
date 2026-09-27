from __future__ import annotations

import pytest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.runtime.model import ModelAttemptStatus, ModelUsageSource, RecordedModelProvider
from packages.runtime.model.storage import ModelAttemptModel, ModelRequestModel
from packages.shared.db import Base
from packages.shared.model_provider import (
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
