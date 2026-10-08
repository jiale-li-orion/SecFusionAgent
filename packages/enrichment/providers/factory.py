from __future__ import annotations

from collections.abc import Awaitable, Callable

import httpx

from packages.enrichment.providers.openai_compatible import OpenAICompatibleProvider
from packages.shared.config import Settings


def create_configured_ai_provider(
    settings: Settings,
    client: httpx.AsyncClient,
    *,
    on_delta: Callable[[str, str], Awaitable[None]] | None = None,
) -> OpenAICompatibleProvider | None:
    if not settings.model_base_url:
        return None
    if not settings.model_name and not settings.embedding_model_name:
        return None
    return OpenAICompatibleProvider(
        client,
        base_url=settings.model_base_url,
        chat_model=settings.model_name,
        embedding_model=settings.embedding_model_name,
        api_key=settings.model_api_key,
        embedding_dimensions=settings.embedding_dimensions,
        max_tokens=settings.model_max_tokens,
        temperature=settings.model_temperature,
        reasoning_effort=settings.model_reasoning_effort,
        on_delta=on_delta,
    )
