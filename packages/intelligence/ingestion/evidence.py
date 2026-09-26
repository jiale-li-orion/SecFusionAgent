from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.storage.artifacts import ArtifactStore
from packages.intelligence.storage.evidence_models import EvidenceArtifactModel, ObservationModel
from packages.sources.contracts import IngestEnvelope, SourceDefinition


class ObservationAck(BaseModel):
    observation_id: str
    artifact_id: str | None
    accepted_at: datetime
    replay: bool


class EvidenceIngress:
    def __init__(
        self,
        artifact_store: ArtifactStore,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._artifact_store = artifact_store
        self._now = now or (lambda: datetime.now(UTC))

    async def accept(
        self,
        session: AsyncSession,
        source: SourceDefinition,
        envelope: IngestEnvelope,
    ) -> ObservationAck:
        if envelope.source_id != source.source_id:
            raise ValueError("envelope source_id does not match source definition")

        existing = await session.scalar(
            select(ObservationModel).where(
                ObservationModel.idempotency_key == envelope.idempotency_key
            )
        )
        if existing is not None:
            if existing.content_hash == envelope.content_hash:
                return await _replay_ack(session, existing)
            effective_idempotency_key = _revision_collision_key(envelope)
            collision = await session.scalar(
                select(ObservationModel).where(
                    ObservationModel.idempotency_key == effective_idempotency_key
                )
            )
            if collision is not None:
                if collision.content_hash != envelope.content_hash:
                    raise RuntimeError("revision collision key resolved to unexpected content hash")
                return await _replay_ack(session, collision)
        else:
            effective_idempotency_key = envelope.idempotency_key

        body = envelope.content_bytes()
        artifact_write = await self._artifact_store.put(
            content_hash=envelope.content_hash,
            body=body,
            media_type=envelope.media_type,
        )
        accepted_at = self._now()
        observation_id = str(uuid4())
        artifact_id = str(uuid4())
        session.add(
            ObservationModel(
                observation_id=observation_id,
                source_id=source.source_id,
                acquisition_run_id=envelope.acquisition_run_id,
                external_object_id=envelope.external_object_id,
                external_revision=envelope.external_revision,
                canonical_url=envelope.canonical_url,
                published_at=envelope.published_at,
                updated_at=envelope.updated_at,
                observed_at=envelope.observed_at,
                content_hash=envelope.content_hash,
                idempotency_key=effective_idempotency_key,
                created_at=accepted_at,
            )
        )
        # No ORM relationship connects Observation and EvidenceArtifact, so the
        # unit-of-work cannot infer the FK insert order on every dialect. Flush
        # the parent explicitly before adding the child; PostgreSQL enforces
        # this boundary even when SQLite fast tests do not.
        await session.flush()
        session.add(
            EvidenceArtifactModel(
                artifact_id=artifact_id,
                observation_id=observation_id,
                media_type=envelope.media_type,
                storage_uri=artifact_write.storage_uri,
                content_hash=envelope.content_hash,
                access_rights=source.access_rights,
                trust_class="external_untrusted",
                created_at=accepted_at,
            )
        )
        await session.flush()
        return ObservationAck(
            observation_id=observation_id,
            artifact_id=artifact_id,
            accepted_at=accepted_at,
            replay=False,
        )


async def _replay_ack(
    session: AsyncSession,
    observation: ObservationModel,
) -> ObservationAck:
    artifact = await session.scalar(
        select(EvidenceArtifactModel).where(
            EvidenceArtifactModel.observation_id == observation.observation_id
        )
    )
    if artifact is None:
        raise RuntimeError("observation exists without evidence artifact")
    return ObservationAck(
        observation_id=observation.observation_id,
        artifact_id=artifact.artifact_id,
        accepted_at=observation.created_at,
        replay=True,
    )


def _revision_collision_key(envelope: IngestEnvelope) -> str:
    material = f"{envelope.idempotency_key}:{envelope.content_hash}"
    return sha256(material.encode()).hexdigest()
