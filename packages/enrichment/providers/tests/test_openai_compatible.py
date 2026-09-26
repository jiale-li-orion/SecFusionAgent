from __future__ import annotations

import json

import httpx
import pytest
from pydantic import BaseModel

from packages.enrichment.providers.openai_compatible import OpenAICompatibleProvider
from packages.shared.model_provider import StructuredModelRequest


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
