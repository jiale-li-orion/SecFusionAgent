from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from packages.enrichment.providers.openai_compatible import (
    OpenAICompatibleProvider,
    discover_openai_compatible_models,
    select_discovered_chat_model,
)
from packages.shared.config import get_settings
from packages.shared.model_provider import StructuredModelRequest


class _ProbeResponse(BaseModel):
    status: str


async def _retry_transient(call, *, settings):
    last_error: Exception | None = None
    for ordinal in range(1, settings.model_max_attempts + 1):
        try:
            return await call()
        except Exception as exc:
            last_error = exc
            if not bool(getattr(exc, "retryable", False)) or ordinal >= settings.model_max_attempts:
                raise
            requested = getattr(exc, "retry_after_seconds", None)
            if not isinstance(requested, (int, float)) or isinstance(requested, bool):
                requested = 0.0
            delay = min(
                settings.model_retry_max_seconds,
                max(settings.model_retry_base_seconds * (2 ** (ordinal - 1)), float(requested)),
            )
            if delay > 0:
                await asyncio.sleep(delay)
    assert last_error is not None
    raise last_error


async def probe_model_provider() -> dict[str, Any]:
    settings = get_settings()
    if not settings.model_base_url:
        raise RuntimeError("SECFUSION_MODEL_BASE_URL is required")

    async with httpx.AsyncClient(timeout=settings.model_timeout_seconds) as client:
        model_name = settings.model_name
        discovery_mode = "explicit"
        discovered_models: list[str] = []
        if not model_name:
            discovered_models = await _retry_transient(
                lambda: discover_openai_compatible_models(
                    client,
                    base_url=settings.model_base_url or "",
                    api_key=settings.model_api_key,
                ),
                settings=settings,
            )
            model_name = select_discovered_chat_model(discovered_models)
            discovery_mode = "single_chat_candidate"

        provider = OpenAICompatibleProvider(
            client,
            base_url=settings.model_base_url,
            chat_model=model_name,
            api_key=settings.model_api_key,
            max_tokens=settings.model_max_tokens,
            temperature=settings.model_temperature,
            reasoning_effort=settings.model_reasoning_effort,
        )
        result = await _retry_transient(
            lambda: provider.generate_structured_result(
                StructuredModelRequest(
                    system_instruction=(
                        "Return a JSON object matching the supplied schema. "
                        "Set status to exactly 'ok'."
                    ),
                    data={"probe": "secfusion-model-provider"},
                    metadata={},
                ),
                _ProbeResponse,
            ),
            settings=settings,
        )
        if result.output.status != "ok":
            raise RuntimeError("model provider probe returned an unexpected structured value")
        return {
            "status": "ready",
            "configured_base_url": settings.model_base_url,
            "resolved_model_name": model_name,
            "model_resolution": discovery_mode,
            "discovered_models": discovered_models,
            "actual_model": result.actual_model,
            "provider_request_id": result.provider_request_id,
            "usage_available": result.usage is not None,
            "response_metadata": result.response_metadata or {},
            "api_key_present": bool(settings.model_api_key),
        }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe OpenAI-compatible auth/model/structured-output compatibility"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = asyncio.run(probe_model_provider())
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
