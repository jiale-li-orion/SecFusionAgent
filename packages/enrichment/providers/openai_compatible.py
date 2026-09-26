from __future__ import annotations

import json
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from packages.intelligence.retrieval.contracts import EmbeddingBatch
from packages.shared.model_provider import StructuredModelRequest

TStructured = TypeVar("TStructured", bound=BaseModel)


class AIProviderError(RuntimeError):
    pass


class AIProviderAuthError(AIProviderError):
    pass


class AIProviderRateLimited(AIProviderError):
    pass


class AIProviderResponseError(AIProviderError):
    pass


class OpenAICompatibleProvider:
    """Small OpenAI-compatible adapter for M3 semantic extraction and embeddings."""

    ADAPTER_VERSION = "openai-compatible-v1"

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        base_url: str,
        chat_model: str | None = None,
        embedding_model: str | None = None,
        api_key: str | None = None,
        embedding_dimensions: int | None = None,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._chat_model = chat_model
        self._embedding_model = embedding_model
        self._api_key = api_key
        self._embedding_dimensions = embedding_dimensions
        self.name = chat_model or "openai-compatible"
        self.version = self.ADAPTER_VERSION

    async def generate_structured(
        self,
        request: StructuredModelRequest,
        response_model: type[TStructured],
    ) -> TStructured:
        if not self._chat_model:
            raise ValueError("chat model is not configured")
        schema = response_model.model_json_schema()
        payload: dict[str, Any] = {
            "model": self._chat_model,
            "messages": [
                {"role": "system", "content": request.system_instruction},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"data": request.data, "metadata": request.metadata},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
            ],
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        response = await self._post("/chat/completions", payload)
        if response.status_code in {400, 422}:
            payload["response_format"] = {"type": "json_object"}
            response = await self._post("/chat/completions", payload)
        data = _response_json(response)
        try:
            choices = data["choices"]
            message = choices[0]["message"]
            content = message["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderResponseError(
                "chat response is missing choices[0].message.content"
            ) from exc
        if not isinstance(content, str):
            raise AIProviderResponseError("chat response content must be a JSON string")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise AIProviderResponseError("chat response content is not valid JSON") from exc
        try:
            return response_model.model_validate(parsed)
        except Exception as exc:
            raise AIProviderResponseError(
                f"chat response does not satisfy {response_model.__name__}"
            ) from exc

    async def embed(self, texts: list[str]) -> EmbeddingBatch:
        if not self._embedding_model:
            raise ValueError("embedding model is not configured")
        if not texts:
            return EmbeddingBatch(
                model=self._embedding_model,
                version=self.ADAPTER_VERSION,
                dimensions=self._embedding_dimensions or 0,
                vectors=[],
            )
        payload: dict[str, Any] = {
            "model": self._embedding_model,
            "input": texts,
        }
        if self._embedding_dimensions is not None:
            payload["dimensions"] = self._embedding_dimensions
        response = await self._post("/embeddings", payload)
        data = _response_json(response)
        raw_items = data.get("data")
        if not isinstance(raw_items, list) or len(raw_items) != len(texts):
            raise AIProviderResponseError("embedding response count does not match input count")
        indexed: list[tuple[int, list[float]]] = []
        for ordinal, item in enumerate(raw_items):
            if not isinstance(item, dict):
                raise AIProviderResponseError("embedding item must be an object")
            index = item.get("index", ordinal)
            vector = item.get("embedding")
            if not isinstance(index, int) or not isinstance(vector, list):
                raise AIProviderResponseError("embedding item is missing index/vector")
            if not all(
                isinstance(value, (int, float)) and not isinstance(value, bool) for value in vector
            ):
                raise AIProviderResponseError("embedding vector contains a non-numeric value")
            indexed.append((index, [float(value) for value in vector]))
        indexed.sort(key=lambda item: item[0])
        vectors = [vector for _, vector in indexed]
        dimensions = len(vectors[0]) if vectors else 0
        if dimensions <= 0 or any(len(vector) != dimensions for vector in vectors):
            raise AIProviderResponseError("embedding vectors have inconsistent dimensions")
        if self._embedding_dimensions is not None and dimensions != self._embedding_dimensions:
            raise AIProviderResponseError(
                "embedding dimensions mismatch: "
                f"expected {self._embedding_dimensions}, got {dimensions}"
            )
        return EmbeddingBatch(
            model=self._embedding_model,
            version=self.ADAPTER_VERSION,
            dimensions=dimensions,
            vectors=vectors,
        )

    async def _post(self, path: str, payload: dict[str, Any]) -> httpx.Response:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            response = await self._client.post(
                f"{self._base_url}{path}",
                json=payload,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise AIProviderError(
                f"model provider request failed: {exc.__class__.__name__}"
            ) from exc
        if response.status_code == 429:
            raise AIProviderRateLimited("model provider rate limit reached")
        if response.status_code in {401, 403}:
            raise AIProviderAuthError(
                f"model provider authentication failed with HTTP {response.status_code}"
            )
        if response.status_code >= 500:
            raise AIProviderError(f"model provider returned HTTP {response.status_code}")
        return response


def _response_json(response: httpx.Response) -> dict[str, Any]:
    if response.is_error:
        raise AIProviderResponseError(f"model provider returned HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise AIProviderResponseError("model provider returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise AIProviderResponseError("model provider response must be an object")
    return payload
