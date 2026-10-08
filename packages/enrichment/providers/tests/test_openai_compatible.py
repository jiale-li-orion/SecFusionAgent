from __future__ import annotations

import json

import httpx
import pytest
from pydantic import BaseModel

from packages.enrichment.providers.openai_compatible import (
    OpenAICompatibleProvider,
    discover_openai_compatible_models,
    select_discovered_chat_model,
)
from packages.shared.model_provider import (
    ModelProviderMalformedOutputError,
    ModelProviderRateLimited,
    ModelProviderResponseError,
    StructuredModelRequest,
)


class Result(BaseModel):
    value: str


@pytest.mark.asyncio
async def test_structured_generation_uses_schema_and_validates_response() -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        assert request.headers["authorization"] == "Bearer secret"
        assert payload["response_format"]["type"] == "json_schema"
        assert payload["temperature"] == 0.0
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"value":"ok"}'}}]},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            client,
            base_url="https://provider.example/v1",
            chat_model="model-a",
            api_key="secret",
        )
        result = await provider.generate_structured(
            StructuredModelRequest(system_instruction="extract", data={"text": "hello"}),
            Result,
        )
    assert result.value == "ok"
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_structured_generation_streams_provider_deltas_and_validates_final_object() -> None:
    deltas: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["stream"] is True
        assert payload["stream_options"] == {"include_usage": True}
        chunks = [
            {
                "id": "stream-1",
                "model": "model-a",
                "choices": [{"delta": {"reasoning_content": "Checking evidence."}}],
            },
            {"choices": [{"delta": {"content": '{"value":"'}}]},
            {"choices": [{"delta": {"content": 'ok"}'}}]},
            {"usage": {"prompt_tokens": 12, "completion_tokens": 4}, "choices": []},
        ]
        body = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n"
        return httpx.Response(200, text=body, request=request)

    async def on_delta(kind: str, text: str) -> None:
        deltas.append((kind, text))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            client, base_url="https://provider.example/v1", chat_model="model-a", on_delta=on_delta
        )
        result = await provider.generate_structured_result(
            StructuredModelRequest(system_instruction="extract", data={"text": "hello"}), Result
        )
    assert result.output.value == "ok"
    assert result.provider_request_id == "stream-1"
    assert result.usage is not None and result.usage.input_tokens == 12
    assert deltas == [
        ("reasoning", "Checking evidence."),
        ("content", '{"value":"'),
        ("content", 'ok"}'),
    ]


@pytest.mark.asyncio
async def test_structured_generation_forwards_explicit_generation_controls() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["max_tokens"] == 8192
        assert payload["temperature"] == 0.0
        assert payload["reasoning_effort"] == "high"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"value":"ok"}'}}]},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            client,
            base_url="https://provider.example/v1",
            chat_model="model-a",
            max_tokens=8192,
            temperature=0.0,
            reasoning_effort="high",
        )
        result = await provider.generate_structured(
            StructuredModelRequest(system_instruction="extract", data={"text": "hello"}),
            Result,
        )
    assert result.value == "ok"


@pytest.mark.asyncio
async def test_structured_generation_falls_back_to_json_object() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        payload = json.loads(request.content)
        if attempts == 1:
            assert payload["response_format"]["type"] == "json_schema"
            return httpx.Response(400, json={"error": "unsupported"}, request=request)
        assert payload["response_format"] == {"type": "json_object"}
        system_instruction = payload["messages"][0]["content"]
        assert "conforms exactly to this JSON Schema" in system_instruction
        assert '"value"' in system_instruction
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"value":"fallback"}'}}]},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            client,
            base_url="https://provider.example/v1",
            chat_model="model-a",
        )
        result = await provider.generate_structured(
            StructuredModelRequest(system_instruction="extract", data={"text": "hello"}),
            Result,
        )
    assert result.value == "fallback"
    assert attempts == 2


@pytest.mark.asyncio
async def test_configured_json_object_uses_one_exchange_with_schema_validation() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type": "json_object"}
        assert '"value"' in payload["messages"][0]["content"]
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"value":"direct"}'}}]},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            client,
            base_url="https://provider.example/v1",
            chat_model="model-a",
            response_format="json_object",
        )
        result = await provider.generate_structured_result(
            StructuredModelRequest(system_instruction="extract", data={"text": "hello"}),
            Result,
        )
    assert result.output.value == "direct"
    assert attempts == 1
    assert result.response_metadata is not None
    assert result.response_metadata["response_format_fallback"] is False
    assert result.response_metadata["http_exchanges"] == 1


@pytest.mark.asyncio
async def test_configured_json_schema_does_not_negotiate_after_rejection() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        assert json.loads(request.content)["response_format"]["type"] == "json_schema"
        return httpx.Response(400, json={"error": "unsupported"}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            client,
            base_url="https://provider.example/v1",
            chat_model="model-a",
            response_format="json_schema",
        )
        with pytest.raises(ModelProviderResponseError):
            await provider.generate_structured_result(
                StructuredModelRequest(system_instruction="extract", data={"text": "hello"}),
                Result,
            )
    assert attempts == 1


@pytest.mark.asyncio
async def test_embedding_batch_preserves_index_order_and_dimensions() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload == {
            "model": "embed-a",
            "input": ["first", "second"],
            "dimensions": 3,
        }
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0, 0.0]},
                    {"index": 0, "embedding": [1.0, 0.0, 0.0]},
                ]
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            client,
            base_url="https://provider.example/v1",
            embedding_model="embed-a",
            embedding_dimensions=3,
        )
        batch = await provider.embed(["first", "second"])
    assert batch.model == "embed-a"
    assert batch.dimensions == 3
    assert batch.vectors == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]


@pytest.mark.asyncio
async def test_rate_limit_exposes_retry_after_for_runtime_retry_policy() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"Retry-After": "1.5"},
            json={"error": "rate limited"},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            client,
            base_url="https://provider.example/v1",
            chat_model="model-a",
        )
        with pytest.raises(ModelProviderRateLimited) as captured:
            await provider.generate_structured(
                StructuredModelRequest(system_instruction="extract", data={"text": "hello"}),
                Result,
            )
    assert captured.value.retry_after_seconds == 1.5


@pytest.mark.asyncio
async def test_malformed_json_is_retryable_without_exposing_provider_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"value":'}}]},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            client, base_url="https://provider.example/v1", chat_model="model-a"
        )
        with pytest.raises(ModelProviderMalformedOutputError) as captured:
            await provider.generate_structured(
                StructuredModelRequest(system_instruction="extract", data={"text": "hello"}),
                Result,
            )
    assert captured.value.retryable is True
    assert str(captured.value) == "chat response content is not valid JSON"


@pytest.mark.asyncio
async def test_model_discovery_uses_auth_and_returns_stable_ids() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        assert request.headers["authorization"] == "Bearer secret"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "embed-a"},
                    {"id": "chat-a"},
                    {"id": "chat-a"},
                ]
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        models = await discover_openai_compatible_models(
            client,
            base_url="https://provider.example/v1/",
            api_key="secret",
        )
    assert models == ["chat-a", "embed-a"]
    assert select_discovered_chat_model(models) == "chat-a"


def test_model_discovery_fails_closed_when_multiple_chat_models_exist() -> None:
    with pytest.raises(ValueError, match="SECFUSION_MODEL_NAME"):
        select_discovered_chat_model(["chat-a", "chat-b", "embed-a"])
