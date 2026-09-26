from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.ingestion.evidence import ObservationAck
from packages.intelligence.normalization.canonical import NormalizationResult
from packages.intelligence.normalization.hot_bug import HotBugNormalizer
from packages.intelligence.normalization.nvd import NVDHotBugNormalizer
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    EvidenceLinkModel,
    ExternalIdentifierModel,
    KnowledgeChangeModel,
    KnowledgeRevisionModel,
    ObjectModel,
)
from packages.intelligence.storage.models import ProcessingRunModel
from packages.shared.storage.models import OutboxEventModel
from packages.sources.contracts import IngestEnvelope, SourceDefinition


class ProjectedVulnerabilityCanonicalNormalizer:
    PROCESSOR_VERSION = "1"

    def __init__(
        self,
        *,
        processor_name: str,
        projection: HotBugNormalizer,
        locator_for: Callable[[str], dict[str, object]],
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._processor_name = processor_name
        self._now = now or (lambda: datetime.now(UTC))
        self._projection = projection
        self._locator_for = locator_for

    async def normalize(
        self,
        session: AsyncSession,
        source: SourceDefinition,
        envelope: IngestEnvelope,
        observation: ObservationAck,
    ) -> NormalizationResult:
        run_id = _stable_id(
            f"processing:{self._processor_name}:{self.PROCESSOR_VERSION}:{observation.observation_id}"
        )
        existing_run = await session.get(ProcessingRunModel, run_id)
        if existing_run is not None and existing_run.status == "success":
            existing_change = await session.scalar(
                select(KnowledgeChangeModel).where(
                    KnowledgeChangeModel.cause_processing_run_id == run_id
                )
            )
            if existing_change is None:
                raise RuntimeError("successful normalization has no knowledge change")
            return _result_from_change(existing_change, observation.observation_id, run_id)

        now = self._now()
        if existing_run is None:
            session.add(
                ProcessingRunModel(
                    run_id=run_id,
                    processor_type="normalization",
                    processor_name=self._processor_name,
                    processor_version=self.PROCESSOR_VERSION,
                    input_revision_ids=[observation.observation_id],
                    attempt=1,
                    status="running",
                    started_at=now,
                )
            )
        else:
            existing_run.attempt += 1
            existing_run.status = "running"
            existing_run.started_at = now
            existing_run.finished_at = None
            existing_run.error_code = None

        revision = KnowledgeRevisionModel(
            cause_processing_run_id=run_id,
            cause_observation_id=observation.observation_id,
            committed_at=now,
        )
        session.add(revision)
        await session.flush()

        projection = self._projection.projection(envelope)
        cve_id = projection.get("cve_id")
        if not isinstance(cve_id, str):
            raise ValueError("NVD canonical normalization requires cve_id")

        object_id = _stable_id(f"object:vulnerability:cve:{cve_id.upper()}")
        vulnerability = await session.get(ObjectModel, object_id)
        if vulnerability is None:
            vulnerability = ObjectModel(
                object_id=object_id,
                object_type="Vulnerability",
                canonical_key=f"cve:{cve_id.upper()}",
                properties={"display_name": cve_id.upper()},
                created_revision=revision.revision,
            )
            session.add(vulnerability)

        external_id = await session.scalar(
            select(ExternalIdentifierModel).where(
                ExternalIdentifierModel.namespace == "cve",
                ExternalIdentifierModel.value == cve_id.upper(),
            )
        )
        if external_id is None:
            session.add(
                ExternalIdentifierModel(
                    external_identifier_id=_stable_id(f"external-id:cve:{cve_id.upper()}"),
                    namespace="cve",
                    value=cve_id.upper(),
                    object_id=object_id,
                )
            )

        for predicate in projection:
            if predicate == "cve_id":
                continue
            await _supersede_source_claims(
                session,
                subject_id=object_id,
                predicate=predicate,
                source_id=source.source_id,
                superseded_revision=revision.revision,
            )

        claim_ids: list[str] = []
        for predicate, value in projection.items():
            if predicate == "cve_id" or value is None:
                continue
            claim_id = _stable_id(f"claim:{object_id}:{predicate}:{observation.observation_id}")
            claim = await session.get(ClaimModel, claim_id)
            if claim is None:
                claim = ClaimModel(
                    claim_id=claim_id,
                    subject_id=object_id,
                    predicate=predicate,
                    value=value,
                    qualifier={"source_id": source.source_id},
                    origin="source_asserted",
                    lifecycle="accepted",
                    processing_run_id=run_id,
                    created_revision=revision.revision,
                )
                session.add(claim)
                locator = self._locator_for(predicate)
                locator_hash = sha256(
                    json.dumps(locator, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
                session.add(
                    EvidenceLinkModel(
                        evidence_link_id=_stable_id(
                            f"evidence-link:claim:{claim_id}:{observation.observation_id}:{locator_hash}"
                        ),
                        target_kind="claim",
                        target_id=claim_id,
                        observation_id=observation.observation_id,
                        artifact_id=observation.artifact_id,
                        locator=locator,
                        locator_hash=locator_hash,
                    )
                )
            claim_ids.append(claim_id)

        change = KnowledgeChangeModel(
            change_id=_stable_id(f"knowledge-change:{run_id}"),
            revision=revision.revision,
            changed_ids={"objects": [object_id], "claims": claim_ids, "relations": []},
            cause_processing_run_id=run_id,
            cause_observation_id=observation.observation_id,
            committed_at=now,
        )
        session.add(change)
        session.add(
            OutboxEventModel(
                event_id=_stable_id(f"outbox:knowledge.changed:{run_id}"),
                topic="knowledge.changed",
                aggregate_id=object_id,
                payload={
                    "revision": revision.revision,
                    "object_ids": [object_id],
                    "claim_ids": claim_ids,
                    "relation_ids": [],
                },
                status="pending",
                attempts=0,
                available_at=now,
            )
        )
        session.add(
            OutboxEventModel(
                event_id=_stable_id(f"outbox:enrichment.requested:{run_id}"),
                topic="enrichment.requested",
                aggregate_id=object_id,
                payload={
                    "object_id": object_id,
                    "cve_id": cve_id.upper(),
                    "parent_run_id": run_id,
                },
                status="pending",
                attempts=0,
                available_at=now,
            )
        )
        run = await session.get(ProcessingRunModel, run_id)
        if run is None:
            raise RuntimeError("processing run disappeared during normalization")
        run.status = "success"
        run.finished_at = now
        await session.flush()
        return _result_from_change(change, observation.observation_id, run_id)


class NVDCanonicalNormalizer(ProjectedVulnerabilityCanonicalNormalizer):
    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        super().__init__(
            processor_name="nvd-canonical-normalizer",
            projection=NVDHotBugNormalizer(),
            locator_for=_nvd_locator_for,
            now=now,
        )


def _result_from_change(
    change: KnowledgeChangeModel,
    observation_id: str,
    processing_run_id: str,
) -> NormalizationResult:
    return NormalizationResult(
        observation_id=observation_id,
        knowledge_revision=change.revision,
        committed_at=change.committed_at,
        object_ids=list(change.changed_ids.get("objects", [])),
        claim_ids=list(change.changed_ids.get("claims", [])),
        relation_ids=list(change.changed_ids.get("relations", [])),
        processing_run_id=processing_run_id,
    )


def _stable_id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"secfusion:{value}"))


def _nvd_locator_for(predicate: str) -> dict[str, object]:
    paths = {
        "status": "$.cve.vulnStatus",
        "description_en": "$.cve.descriptions[?(@.lang=='en')].value",
        "cvss_score": "$.cve.metrics",
        "cvss_severity": "$.cve.metrics",
        "cvss_vector": "$.cve.metrics",
        "cwes": "$.cve.weaknesses",
        "references": "$.cve.references",
        "published": "$.cve.published",
        "last_modified": "$.cve.lastModified",
    }
    return {"kind": "jsonpath", "path": paths.get(predicate, "$.cve")}


async def _supersede_source_claims(
    session: AsyncSession,
    *,
    subject_id: str,
    predicate: str,
    source_id: str,
    superseded_revision: int,
) -> None:
    current = list(
        await session.scalars(
            select(ClaimModel).where(
                ClaimModel.subject_id == subject_id,
                ClaimModel.predicate == predicate,
                ClaimModel.lifecycle == "accepted",
                ClaimModel.superseded_revision.is_(None),
            )
        )
    )
    for claim in current:
        if claim.qualifier.get("source_id") == source_id:
            claim.superseded_revision = superseded_revision
