from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.runtime.storage.models import ExecutionRunModel, RuntimeArtifactModel


class RuntimeBlobWrite(BaseModel):
    storage_uri: str
    size_bytes: int = Field(ge=0)


class RuntimeBlobStore(Protocol):
    async def put(
        self,
        *,
        content_hash: str,
        body: bytes,
        media_type: str,
    ) -> RuntimeBlobWrite: ...

    async def get(self, storage_uri: str) -> bytes: ...


class MemoryRuntimeBlobStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(
        self,
        *,
        content_hash: str,
        body: bytes,
        media_type: str,
    ) -> RuntimeBlobWrite:
        del media_type
        uri = f"memory://runtime/{content_hash}"
        self.objects.setdefault(uri, body)
        return RuntimeBlobWrite(storage_uri=uri, size_bytes=len(body))

    async def get(self, storage_uri: str) -> bytes:
        return self.objects[storage_uri]


class RuntimeArtifact(BaseModel):
    artifact_ref: str
    artifact_id: str
    execution_id: str
    producer_kind: str
    producer_ref: str | None = None
    logical_name: str
    media_type: str
    content_hash: str
    storage_uri: str
    size_bytes: int = Field(ge=0)
    trust_class: str
    created_at: datetime


class RuntimeArtifactService:
    def __init__(
        self,
        blob_store: RuntimeBlobStore,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._blob_store = blob_store
        self._now = now or (lambda: datetime.now(UTC))

    async def write(
        self,
        session: AsyncSession,
        *,
        execution_id: str,
        producer_kind: str,
        producer_ref: str | None,
        logical_name: str,
        media_type: str,
        body: bytes,
        trust_class: str = "execution_untrusted",
    ) -> RuntimeArtifact:
        if not producer_kind.strip() or not logical_name.strip() or not media_type.strip():
            raise ValueError("runtime artifact producer/name/media_type cannot be empty")
        execution = await session.get(ExecutionRunModel, execution_id)
        if execution is None:
            raise LookupError(f"execution run not found: {execution_id}")
        content_hash = sha256(body).hexdigest()
        existing = await session.scalar(
            select(RuntimeArtifactModel).where(
                RuntimeArtifactModel.execution_id == execution_id,
                RuntimeArtifactModel.logical_name == logical_name,
                RuntimeArtifactModel.content_hash == content_hash,
            )
        )
        if existing is not None:
            if (
                existing.media_type != media_type
                or existing.producer_kind != producer_kind
                or existing.producer_ref != producer_ref
                or existing.trust_class != trust_class
            ):
                raise ValueError("runtime artifact replay identity changed metadata")
            return _view(existing)

        write = await self._blob_store.put(
            content_hash=content_hash,
            body=body,
            media_type=media_type,
        )
        artifact_id = str(
            uuid5(
                NAMESPACE_URL,
                f"secfusion:runtime-artifact:{execution_id}:{logical_name}:{content_hash}",
            )
        )
        model = RuntimeArtifactModel(
            artifact_id=artifact_id,
            execution_id=execution_id,
            producer_kind=producer_kind,
            producer_ref=producer_ref,
            logical_name=logical_name,
            media_type=media_type,
            content_hash=content_hash,
            storage_uri=write.storage_uri,
            size_bytes=write.size_bytes,
            trust_class=trust_class,
            created_at=self._now(),
        )
        session.add(model)
        await session.flush()
        return _view(model)

    async def get(self, session: AsyncSession, artifact_ref: str) -> RuntimeArtifact:
        artifact_id = _artifact_id(artifact_ref)
        model = await session.get(RuntimeArtifactModel, artifact_id)
        if model is None:
            raise LookupError(f"runtime artifact not found: {artifact_ref}")
        return _view(model)

    async def read(self, session: AsyncSession, artifact_ref: str) -> bytes:
        artifact = await self.get(session, artifact_ref)
        body = await self._blob_store.get(artifact.storage_uri)
        if sha256(body).hexdigest() != artifact.content_hash:
            raise RuntimeError("runtime artifact content hash mismatch")
        return body


def _artifact_id(artifact_ref: str) -> str:
    if not artifact_ref.startswith("artifact:"):
        raise ValueError("runtime artifact reference must use artifact: prefix")
    artifact_id = artifact_ref.removeprefix("artifact:")
    if not artifact_id:
        raise ValueError("runtime artifact reference cannot be empty")
    return artifact_id


def _view(model: RuntimeArtifactModel) -> RuntimeArtifact:
    created_at = model.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    else:
        created_at = created_at.astimezone(UTC)
    return RuntimeArtifact(
        artifact_ref=f"artifact:{model.artifact_id}",
        artifact_id=model.artifact_id,
        execution_id=model.execution_id,
        producer_kind=model.producer_kind,
        producer_ref=model.producer_ref,
        logical_name=model.logical_name,
        media_type=model.media_type,
        content_hash=model.content_hash,
        storage_uri=model.storage_uri,
        size_bytes=model.size_bytes,
        trust_class=model.trust_class,
        created_at=created_at,
    )
