from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

import httpx
from pydantic import BaseModel

from packages.sources.contracts import IngestEnvelope
from packages.sources.errors import (
    SourceAuthFailed,
    SourceFetchFailed,
    SourceRateLimited,
    SourceSchemaChanged,
)


class LiveProbeResult(BaseModel):
    source_id: str
    operation: str
    status: str
    elapsed_ms: int
    record_count: int = 0
    sample_external_id: str | None = None
    detail: str | None = None


Probe = Callable[[], Awaitable[list[IngestEnvelope] | tuple[int, str | None]]]


async def run_live_probe(source_id: str, operation: str, probe: Probe) -> LiveProbeResult:
    started = time.perf_counter()
    try:
        value = await probe()
        if isinstance(value, tuple):
            count, sample = value
        else:
            count = len(value)
            sample = value[0].external_object_id if value else None
        return LiveProbeResult(
            source_id=source_id,
            operation=operation,
            status="ok",
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            record_count=count,
            sample_external_id=sample,
        )
    except SourceRateLimited as exc:
        status = "rate_limited"
        detail = str(exc)
    except SourceAuthFailed as exc:
        detail = str(exc)
        status = "auth_required" if "required" in detail.lower() else "auth_failed"
    except SourceSchemaChanged as exc:
        status = "schema_changed"
        detail = str(exc)
    except SourceFetchFailed as exc:
        detail = str(exc)
        status = "provider_blocked" if looks_access_blocked(detail) else "failed"
    except (httpx.HTTPError, TimeoutError) as exc:
        status = "failed"
        detail = f"{type(exc).__name__}: {exc}"
    except Exception as exc:  # keep a batch probe observable even on unexpected provider failures
        status = "failed"
        detail = f"{type(exc).__name__}: {exc}"
    return LiveProbeResult(
        source_id=source_id,
        operation=operation,
        status=status,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
        detail=detail,
    )


def looks_access_blocked(detail: str) -> bool:
    lowered = detail.lower()
    return any(
        marker in lowered
        for marker in (
            "http 401",
            "http 403",
            "http 406",
            "http 521",
            "cloudflare",
            "challenge",
            "forbidden",
            "not acceptable",
            "access denied",
        )
    )
