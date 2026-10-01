from __future__ import annotations

from hashlib import sha256

import pytest

from packages.intelligence.storage.artifacts import FilesystemArtifactStore


@pytest.mark.asyncio
async def test_filesystem_artifact_store_is_content_addressed_and_durable(tmp_path) -> None:
    body = b"durable secfusion evidence"
    digest = sha256(body).hexdigest()
    first = FilesystemArtifactStore(tmp_path, bucket="evidence")
    await first.ensure_bucket()
    write = await first.put(content_hash=digest, body=body, media_type="text/plain")

    assert write.storage_uri == f"artifact://evidence/sha256/{digest[:2]}/{digest}"
    assert write.size_bytes == len(body)
    assert await first.exists(write.storage_uri) is True
    assert await first.get(write.storage_uri) == body

    reopened = FilesystemArtifactStore(tmp_path, bucket="evidence")
    assert await reopened.exists(write.storage_uri) is True
    assert await reopened.get(write.storage_uri) == body
    legacy_uri = write.storage_uri.replace("artifact://", "s3://", 1)
    assert await reopened.exists(legacy_uri) is True
    assert await reopened.get(legacy_uri) == body


@pytest.mark.asyncio
async def test_filesystem_artifact_store_rejects_hash_mismatch(tmp_path) -> None:
    store = FilesystemArtifactStore(tmp_path, bucket="evidence")
    with pytest.raises(ValueError, match="content_hash"):
        await store.put(
            content_hash=sha256(b"expected").hexdigest(),
            body=b"different",
            media_type="text/plain",
        )


@pytest.mark.asyncio
async def test_filesystem_artifact_store_rejects_uri_path_escape(tmp_path) -> None:
    store = FilesystemArtifactStore(tmp_path, bucket="evidence")
    await store.ensure_bucket()
    with pytest.raises(ValueError, match="escapes configured root"):
        await store.get("artifact://evidence/../../outside")
