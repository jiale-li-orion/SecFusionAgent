from __future__ import annotations

import json
from hashlib import sha256
from typing import cast
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, Field, JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.storage.evidence_models import EvidenceArtifactModel, ObservationModel
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    EvidenceLinkModel,
    ObjectModel,
    RelationModel,
)


class EvidenceAttachmentResult(BaseModel):
    evidence_ref: str
    evidence_link_id: str
    observation_id: str
    artifact_id: str | None = None
    target_kind: str
    target_id: str
    locator: dict[str, JsonValue] = Field(default_factory=dict)
    replay: bool = False


class EvidenceAttachmentService:
    async def attach(
        self,
        session: AsyncSession,
        *,
        observation_id: str,
        artifact_id: str | None,
        target_kind: str,
        target_id: str,
        locator: dict[str, JsonValue] | None = None,
    ) -> EvidenceAttachmentResult:
        observation = await session.get(ObservationModel, observation_id)
        if observation is None:
            raise LookupError(f"observation not found: {observation_id}")
        if artifact_id is not None:
            artifact = await session.get(EvidenceArtifactModel, artifact_id)
            if artifact is None:
                raise LookupError(f"evidence artifact not found: {artifact_id}")
            if artifact.observation_id != observation_id:
                raise ValueError("evidence artifact does not belong to observation")
        await _validate_target(session, target_kind, target_id)
        normalized_locator = dict(locator or {})
        locator_hash = sha256(
            json.dumps(
                normalized_locator,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        existing = await session.scalar(
            select(EvidenceLinkModel).where(
                EvidenceLinkModel.target_kind == target_kind,
                EvidenceLinkModel.target_id == target_id,
                EvidenceLinkModel.observation_id == observation_id,
                EvidenceLinkModel.locator_hash == locator_hash,
            )
        )
        if existing is not None:
            if existing.artifact_id != artifact_id or existing.locator != normalized_locator:
                raise ValueError("evidence attachment replay identity changed metadata")
            return _view(existing, replay=True)
        evidence_link_id = str(
            uuid5(
                NAMESPACE_URL,
                "secfusion:evidence-attachment:"
                f"{target_kind}:{target_id}:{observation_id}:{locator_hash}",
            )
        )
        model = EvidenceLinkModel(
            evidence_link_id=evidence_link_id,
            target_kind=target_kind,
            target_id=target_id,
            observation_id=observation_id,
            artifact_id=artifact_id,
            locator=normalized_locator,
            locator_hash=locator_hash,
        )
        session.add(model)
        await session.flush()
        return _view(model, replay=False)


async def _validate_target(session: AsyncSession, target_kind: str, target_id: str) -> None:
    model_type = {
        "object": ObjectModel,
        "claim": ClaimModel,
        "relation": RelationModel,
    }.get(target_kind)
    if model_type is None:
        raise ValueError(f"unsupported evidence attachment target_kind: {target_kind}")
    if await session.get(model_type, target_id) is None:
        raise LookupError(f"evidence attachment target not found: {target_kind}:{target_id}")


def _view(model: EvidenceLinkModel, *, replay: bool) -> EvidenceAttachmentResult:
    return EvidenceAttachmentResult(
        evidence_ref=f"evidence:{model.evidence_link_id}",
        evidence_link_id=model.evidence_link_id,
        observation_id=model.observation_id,
        artifact_id=model.artifact_id,
        target_kind=model.target_kind,
        target_id=model.target_id,
        locator=cast(dict[str, JsonValue], dict(model.locator)),
        replay=replay,
    )
