from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.intelligence.storage.artifacts import ArtifactStore
from packages.intelligence.storage.factory import create_s3_artifact_store
from packages.runtime.artifacts import (
    RuntimeArtifactService,
    RuntimeBlobStore,
    RuntimeBlobWrite,
)
from packages.shared.config import Settings


class ArtifactStoreRuntimeBlobAdapter(RuntimeBlobStore):
    def __init__(self, store: ArtifactStore) -> None:
        self._store = store

    async def put(
        self,
        *,
        content_hash: str,
        body: bytes,
        media_type: str,
    ) -> RuntimeBlobWrite:
        result = await self._store.put(
            content_hash=content_hash,
            body=body,
            media_type=media_type,
        )
        return RuntimeBlobWrite(storage_uri=result.storage_uri, size_bytes=result.size_bytes)

    async def get(self, storage_uri: str) -> bytes:
        return await self._store.get(storage_uri)


class RuntimeArtifactSandboxBridge:
    """App composition bridge between Sandbox ArtifactRef and durable runtime blobs."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        service: RuntimeArtifactService,
        *,
        execution_id: str,
        allowed_external_refs: set[str] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._service = service
        self._execution_id = execution_id
        self._allowed_external_refs = set(allowed_external_refs or set())

    async def materialize(self, artifact_ref: str, *, destination_dir: Path) -> Path:
        async with self._session_factory() as session:
            artifact = await self._service.get(session, artifact_ref)
            if (
                artifact.execution_id != self._execution_id
                and artifact_ref not in self._allowed_external_refs
            ):
                raise PermissionError("runtime artifact is outside sandbox execution scope")
            body = await self._service.read(session, artifact_ref)
        await asyncio.to_thread(destination_dir.mkdir, parents=True, exist_ok=True)
        name = _safe_filename(artifact.logical_name)
        destination = destination_dir / f"{artifact.artifact_id[:12]}-{name}"
        await asyncio.to_thread(destination.write_bytes, body)
        return destination

    async def ingest_bytes(
        self,
        body: bytes,
        *,
        media_type: str,
        logical_name: str,
    ) -> str:
        async with self._session_factory() as session, session.begin():
            artifact = await self._service.write(
                session,
                execution_id=self._execution_id,
                producer_kind="sandbox",
                producer_ref=None,
                logical_name=logical_name,
                media_type=media_type,
                body=body,
            )
        return artifact.artifact_ref

    async def ingest_file(self, path: Path, *, logical_name: str) -> str:
        body = await asyncio.to_thread(path.read_bytes)
        return await self.ingest_bytes(
            body,
            media_type="application/octet-stream",
            logical_name=logical_name,
        )


async def create_runtime_artifact_service(settings: Settings) -> RuntimeArtifactService:
    store = create_s3_artifact_store(settings, bucket=settings.runtime_artifact_bucket)
    await store.ensure_bucket()
    return RuntimeArtifactService(ArtifactStoreRuntimeBlobAdapter(store))


def _safe_filename(value: str) -> str:
    name = Path(value).name
    normalized = "".join(
        character if character.isalnum() or character in "-_." else "-" for character in name
    ).strip(".-_")
    return normalized[:128] or "artifact.bin"
