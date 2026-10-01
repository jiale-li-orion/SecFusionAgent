from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError


class ArtifactStoreUnavailable(RuntimeError):
    """Durable artifact dependency could not complete an operation."""


@dataclass(frozen=True, slots=True)
class ArtifactWriteResult:
    storage_uri: str
    size_bytes: int


class ArtifactStore(Protocol):
    async def ensure_bucket(self) -> None: ...

    async def put(
        self,
        *,
        content_hash: str,
        body: bytes,
        media_type: str,
    ) -> ArtifactWriteResult: ...

    async def get(self, storage_uri: str) -> bytes: ...

    async def exists(self, storage_uri: str) -> bool: ...


class FilesystemArtifactStore:
    """Content-addressed durable store for single-host/self-deployed runtimes."""

    def __init__(self, root: Path, *, bucket: str) -> None:
        self._root = root
        self._bucket = bucket
        self._bucket_root = root / bucket

    async def ensure_bucket(self) -> None:
        try:
            await asyncio.to_thread(self._bucket_root.mkdir, parents=True, exist_ok=True)
        except OSError as exc:
            raise ArtifactStoreUnavailable(
                f"filesystem artifact root unavailable: {exc.__class__.__name__}"
            ) from exc

    async def put(
        self,
        *,
        content_hash: str,
        body: bytes,
        media_type: str,
    ) -> ArtifactWriteResult:
        del media_type
        if sha256(body).hexdigest() != content_hash:
            raise ValueError("artifact body does not match declared content_hash")
        key = f"sha256/{content_hash[:2]}/{content_hash}"
        target = self._bucket_root / key

        def _put() -> None:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if sha256(target.read_bytes()).hexdigest() != content_hash:
                    raise ArtifactStoreUnavailable(
                        "content-addressed artifact path contains different bytes"
                    )
                return
            temporary = target.parent / f".{target.name}.{uuid4().hex}.tmp"
            try:
                temporary.write_bytes(body)
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)

        try:
            await asyncio.to_thread(_put)
        except OSError as exc:
            raise ArtifactStoreUnavailable(
                f"filesystem artifact write failed: {exc.__class__.__name__}"
            ) from exc
        return ArtifactWriteResult(
            storage_uri=f"artifact://{self._bucket}/{key}",
            size_bytes=len(body),
        )

    async def get(self, storage_uri: str) -> bytes:
        path = self._path_for_uri(storage_uri)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except OSError as exc:
            raise ArtifactStoreUnavailable(
                f"filesystem artifact read failed: {exc.__class__.__name__}"
            ) from exc

    async def exists(self, storage_uri: str) -> bool:
        path = self._path_for_uri(storage_uri)
        try:
            return await asyncio.to_thread(path.is_file)
        except OSError as exc:
            raise ArtifactStoreUnavailable(
                f"filesystem artifact existence check failed: {exc.__class__.__name__}"
            ) from exc

    def _path_for_uri(self, storage_uri: str) -> Path:
        prefixes = (f"artifact://{self._bucket}/", f"s3://{self._bucket}/")
        prefix = next((value for value in prefixes if storage_uri.startswith(value)), None)
        if prefix is None:
            raise ValueError(f"artifact URI is outside configured bucket: {storage_uri}")
        key = storage_uri[len(prefix) :]
        root = self._bucket_root.resolve()
        path = (self._bucket_root / key).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError("artifact URI escapes configured root") from exc
        return path


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

        try:
            await asyncio.to_thread(_ensure)
        except BotoCoreError as exc:
            raise ArtifactStoreUnavailable(
                f"artifact store bucket check failed: {exc.__class__.__name__}"
            ) from exc

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

        try:
            await asyncio.to_thread(_put)
        except BotoCoreError as exc:
            raise ArtifactStoreUnavailable(
                f"artifact store write failed: {exc.__class__.__name__}"
            ) from exc
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

        try:
            return await asyncio.to_thread(_get)
        except BotoCoreError as exc:
            raise ArtifactStoreUnavailable(
                f"artifact store read failed: {exc.__class__.__name__}"
            ) from exc

    async def exists(self, storage_uri: str) -> bool:
        prefix = f"s3://{self._bucket}/"
        if not storage_uri.startswith(prefix):
            raise ValueError(f"artifact URI is outside configured bucket: {storage_uri}")
        key = storage_uri[len(prefix) :]

        def _exists() -> bool:
            try:
                self._client.head_object(Bucket=self._bucket, Key=key)  # type: ignore[attr-defined]
            except ClientError as exc:
                error = exc.response.get("Error", {})
                code = str(error.get("Code", ""))
                status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                if code in {"404", "NoSuchKey", "NotFound"} or status == 404:
                    return False
                raise
            return True

        try:
            return await asyncio.to_thread(_exists)
        except BotoCoreError as exc:
            raise ArtifactStoreUnavailable(
                f"artifact store existence check failed: {exc.__class__.__name__}"
            ) from exc


class MemoryArtifactStore:
    """Small deterministic store for unit tests and probes."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def ensure_bucket(self) -> None:
        return None

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

    async def exists(self, storage_uri: str) -> bool:
        return storage_uri in self.objects
