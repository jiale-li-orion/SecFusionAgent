import pytest

from packages.sources.errors import SourceAuthFailed, SourceFetchFailed, SourceRateLimited
from packages.sources.probe import looks_access_blocked, run_live_probe


def test_access_block_classification_is_narrow() -> None:
    assert looks_access_blocked("RSS feed returned HTTP 403")
    assert looks_access_blocked("HTTP 406 Not Acceptable")
    assert looks_access_blocked("Cloudflare challenge")
    assert not looks_access_blocked("provider returned HTTP 500")


@pytest.mark.asyncio
async def test_probe_reports_provider_failure_without_aborting_batch() -> None:
    async def blocked():
        raise SourceFetchFailed("feed returned HTTP 403")

    async def limited():
        raise SourceRateLimited("slow down")

    blocked_result = await run_live_probe("blocked", "discover", blocked)
    limited_result = await run_live_probe("limited", "discover", limited)
    assert blocked_result.status == "provider_blocked"
    assert limited_result.status == "rate_limited"


@pytest.mark.asyncio
async def test_probe_distinguishes_missing_auth_from_provider_failure() -> None:
    async def missing_key():
        raise SourceAuthFailed("Shodan API key is required")

    result = await run_live_probe("shodan", "query", missing_key)
    assert result.status == "auth_required"
