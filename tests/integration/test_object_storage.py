from __future__ import annotations

import hashlib
import os

import pytest

from packages.intelligence.storage.factory import create_s3_artifact_store
from packages.shared.config import Settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("SECFUSION_RUN_INTEGRATION") != "1",
        reason="set SECFUSION_RUN_INTEGRATION=1 to run local infrastructure tests",
    ),
]


@pytest.mark.asyncio
async def test_s3_artifact_store_roundtrip_and_content_addressing() -> None:
    settings = Settings(
        s3_endpoint_url=os.getenv("SECFUSION_S3_ENDPOINT_URL", "http://localhost:4566"),
        s3_access_key="secfusion-test",
        s3_secret_key="secfusion-test",
        s3_bucket="secfusion-integration-evidence",
        s3_region="us-east-1",
    )
    store = create_s3_artifact_store(settings)
    await store.ensure_bucket()

    body = b"SecFusionAgent durable artifact integration probe"
    digest = hashlib.sha256(body).hexdigest()
    first = await store.put(content_hash=digest, body=body, media_type="text/plain")
    second = await store.put(content_hash=digest, body=body, media_type="text/plain")

    assert first.storage_uri == second.storage_uri
    assert first.storage_uri == (f"s3://{settings.s3_bucket}/sha256/{digest[:2]}/{digest}")
    assert first.size_bytes == len(body)
    assert await store.get(first.storage_uri) == body

    with pytest.raises(ValueError, match="outside configured bucket"):
        await store.get("s3://another-bucket/sha256/00/invalid")
