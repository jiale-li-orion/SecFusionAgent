from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, cast

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.storage.artifacts import ArtifactStore
from packages.intelligence.storage.evidence_models import EvidenceArtifactModel, ObservationModel
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope


class ObservationReplay(BaseModel):
    observation_id: str
    artifact_id: str
    envelope: IngestEnvelope
    metadata_complete: bool
    metadata_recovery: str | None = None


class ObservationEnvelopeLoader:
    """Reconstruct the immutable input consumed by post-ingress processors.

    New observations persist request metadata exactly. Rows created before the
    replayability migration are still recoverable at the raw-content level,
    but their original request metadata is explicitly marked incomplete.
    """

    def __init__(self, artifact_store: ArtifactStore) -> None:
        self._artifact_store = artifact_store

    async def load(self, session: AsyncSession, observation_id: str) -> ObservationReplay:
        observation = await session.get(ObservationModel, observation_id)
        if observation is None:
            raise LookupError(f"observation not found: {observation_id}")
        artifact = await session.scalar(
            select(EvidenceArtifactModel).where(
                EvidenceArtifactModel.observation_id == observation.observation_id
            )
        )
        if artifact is None:
            raise RuntimeError("observation exists without evidence artifact")

        body = await self._artifact_store.get(artifact.storage_uri)
        content_hash = sha256(body).hexdigest()
        if content_hash != observation.content_hash or content_hash != artifact.content_hash:
            raise RuntimeError("artifact bytes do not match persisted observation content hash")

        try:
            trigger = AcquisitionTrigger(observation.acquisition_trigger)
        except ValueError:
            trigger = AcquisitionTrigger.REPLAY

        metadata = dict(observation.request_metadata or {})
        metadata_recovery: str | None = None
        if not observation.request_metadata_captured:
            metadata_recovery = "historical_metadata_missing"
            # Historical rows predate request_metadata persistence. Do not
            # reconstruct adapter metadata from AcquisitionRun/query fields: that
            # would conflate M1 execution context with the original source payload.
            metadata["_request_metadata_recovery"] = metadata_recovery

        acquisition_run_id = observation.acquisition_run_id or (
            f"replay:{observation.observation_id}"
        )
        if artifact.media_type == "application/json":
            try:
                decoded = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RuntimeError("persisted JSON artifact cannot be decoded") from exc
            if not isinstance(decoded, dict):
                raise RuntimeError("persisted JSON artifact root must be an object")
            payload = cast(dict[str, Any], decoded)
            envelope = IngestEnvelope(
                acquisition_run_id=acquisition_run_id,
                trigger=trigger,
                source_id=observation.source_id,
                external_object_id=observation.external_object_id,
                canonical_url=observation.canonical_url,
                published_at=observation.published_at,
                updated_at=observation.updated_at,
                observed_at=observation.observed_at,
                external_revision=observation.external_revision,
                content_hash=observation.content_hash,
                media_type=artifact.media_type,
                payload=payload,
                request_metadata=cast(Any, metadata),
                idempotency_key=observation.idempotency_key,
            )
        else:
            envelope = IngestEnvelope(
                acquisition_run_id=acquisition_run_id,
                trigger=trigger,
                source_id=observation.source_id,
                external_object_id=observation.external_object_id,
                canonical_url=observation.canonical_url,
                published_at=observation.published_at,
                updated_at=observation.updated_at,
                observed_at=observation.observed_at,
                external_revision=observation.external_revision,
                content_hash=observation.content_hash,
                media_type=artifact.media_type,
                body=body,
                request_metadata=cast(Any, metadata),
                idempotency_key=observation.idempotency_key,
            )

        return ObservationReplay(
            observation_id=observation.observation_id,
            artifact_id=artifact.artifact_id,
            envelope=envelope,
            metadata_complete=bool(observation.request_metadata_captured),
            metadata_recovery=metadata_recovery,
        )
