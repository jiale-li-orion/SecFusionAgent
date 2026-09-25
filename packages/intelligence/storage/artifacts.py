from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from botocore.exceptions import ClientError


@dataclass(frozen=True, slots=True)
class ArtifactWriteResult:
    storage_uri: str
    size_bytes: int


class ArtifactStore(Protocol):
    async def put(
        self,
        *,
        content_hash: str,
        body: bytes,
        media_type: str,
    ) -> ArtifactWriteResult: ...

    async def get(self, storage_uri: str) -> bytes: ...


class S3ArtifactStore:
    def __init__(self, client: object, *, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    async def ensure_bucket(self) -> None:
        def _ensure() -> None:
            try:
                self._client.head_bucket(Bucket=self._bucket)  # type: ignore[attr-defined]
            except ClientError:
                self._client.create_bucket(Bucket=self._bucket)  # type: ignore[attr-defined]

        await asyncio.to_thread(_ensure)

    async def put(
        self,
        *,
        content_hash: str,
        body: bytes,
        media_type: str,
    ) -> ArtifactWriteResult:
        key = f"sha256/{content_hash[:2]}/{content_hash}"

        def _put() -> None:
            self._client.put_object(  # type: ignore[attr-defined]
                Bucket=self._bucket,
                Key=key,
                Body=body,
                ContentType=media_type,
                Metadata={"sha256": content_hash},
            )

        await asyncio.to_thread(_put)
        return ArtifactWriteResult(
            storage_uri=f"s3://{self._bucket}/{key}",
            size_bytes=len(body),
        )

    async def get(self, storage_uri: str) -> bytes:
        prefix = f"s3://{self._bucket}/"
        if not storage_uri.startswith(prefix):
            raise ValueError(f"artifact URI is outside configured bucket: {storage_uri}")
        key = storage_uri[len(prefix) :]

        def _get() -> bytes:
            response = self._client.get_object(  # type: ignore[attr-defined]
                Bucket=self._bucket,
                Key=key,
            )
            return response["Body"].read()

        return await asyncio.to_thread(_get)


class MemoryArtifactStore:
    """Small deterministic store for unit tests and probes."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(
        self,
        *,
        content_hash: str,
        body: bytes,
        media_type: str,
    ) -> ArtifactWriteResult:
        del media_type
        uri = f"memory://sha256/{content_hash}"
        self.objects.setdefault(uri, body)
        return ArtifactWriteResult(storage_uri=uri, size_bytes=len(body))

    async def get(self, storage_uri: str) -> bytes:
        return self.objects[storage_uri]
