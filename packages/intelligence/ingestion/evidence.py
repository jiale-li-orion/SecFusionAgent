from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.storage.artifacts import ArtifactStore
from packages.intelligence.storage.evidence_models import EvidenceArtifactModel, ObservationModel
from packages.sources.contracts import IngestEnvelope, SourceDefinition


class ObservationAck(BaseModel):
    observation_id: str
    artifact_id: str
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
            artifact = await session.scalar(
                select(EvidenceArtifactModel).where(
                    EvidenceArtifactModel.observation_id == existing.observation_id
                )
            )
            if artifact is None:
                raise RuntimeError("observation exists without evidence artifact")
            return ObservationAck(
                observation_id=existing.observation_id,
                artifact_id=artifact.artifact_id,
                accepted_at=existing.created_at,
                replay=True,
            )

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
                idempotency_key=envelope.idempotency_key,
                created_at=accepted_at,
            )
        )
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
