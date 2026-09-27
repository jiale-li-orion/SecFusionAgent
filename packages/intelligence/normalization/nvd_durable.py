from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.ingestion.evidence import ObservationAck
from packages.intelligence.knowledge.contracts import ObjectCandidate, RelationCandidate
from packages.intelligence.knowledge.identity import (
    cve_canonical_key,
    stable_object_id,
    vulnerability_cve_object_id,
)
from packages.intelligence.knowledge.vocabulary import (
    VocabularyScope,
    classify_term,
    vocabulary_metadata,
)
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
    RelationModel,
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
        relations_for: Callable[[dict[str, object]], list[RelationCandidate]] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._processor_name = processor_name
        self._now = now or (lambda: datetime.now(UTC))
        self._projection = projection
        self._locator_for = locator_for
        self._relations_for = relations_for

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

        object_id = vulnerability_cve_object_id(cve_id)
        vulnerability = await session.get(ObjectModel, object_id)
        if vulnerability is None:
            vulnerability = ObjectModel(
                object_id=object_id,
                object_type="Vulnerability",
                canonical_key=cve_canonical_key(cve_id),
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
            scope = classify_term(
                "claim",
                predicate,
                origin="source_asserted",
                subject_type="Vulnerability",
            )
            if scope is VocabularyScope.UNREGISTERED:
                raise ValueError(f"unregistered canonical claim predicate: {predicate}")
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
            value_fingerprint = sha256(
                json.dumps(
                    value,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode()
            ).hexdigest()
            claim_id = _stable_id(
                f"claim:{object_id}:{predicate}:{observation.observation_id}:"
                f"{value_fingerprint}"
            )
            claim = await session.get(ClaimModel, claim_id)
            if claim is None:
                claim = ClaimModel(
                    claim_id=claim_id,
                    subject_id=object_id,
                    predicate=predicate,
                    value=value,
                    qualifier={
                        "source_id": source.source_id,
                        **vocabulary_metadata(
                            classify_term(
                                "claim",
                                predicate,
                                origin="source_asserted",
                                subject_type="Vulnerability",
                            )
                        ),
                    },
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
            else:
                claim.superseded_revision = None
            claim_ids.append(claim_id)

        relation_ids: list[str] = []
        object_ids: list[str] = [object_id]
        relation_candidates = (
            self._relations_for(dict(projection)) if self._relations_for is not None else []
        )
        relation_types = {item.relation_type for item in relation_candidates}
        for relation_type in relation_types:
            await _supersede_source_relations(
                session,
                subject_id=object_id,
                relation_type=relation_type,
                source_id=source.source_id,
                superseded_revision=revision.revision,
            )
        for relation_candidate in relation_candidates:
            target = await _upsert_related_object(
                session,
                relation_candidate.target,
                revision.revision,
            )
            if target.object_id not in object_ids:
                object_ids.append(target.object_id)
            relation_scope = classify_term(
                "relation",
                relation_candidate.relation_type,
                origin="deterministic_derived",
                subject_type="Vulnerability",
                target_type=relation_candidate.target.object_type,
                qualifier_keys=relation_candidate.qualifier.keys(),
            )
            if relation_scope is VocabularyScope.UNREGISTERED:
                raise ValueError(
                    f"unregistered canonical relation type: {relation_candidate.relation_type}"
                )
            fingerprint = sha256(
                json.dumps(
                    relation_candidate.qualifier,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
            relation_id = _stable_id(
                f"relation:{object_id}:{relation_candidate.relation_type}:{target.object_id}:"
                f"{observation.observation_id}:{fingerprint}"
            )
            existing_relation = await session.get(RelationModel, relation_id)
            if existing_relation is None:
                session.add(
                    RelationModel(
                        relation_id=relation_id,
                        source_object_id=object_id,
                        relation_type=relation_candidate.relation_type,
                        target_object_id=target.object_id,
                        qualifier={
                            **relation_candidate.qualifier,
                            "source_id": source.source_id,
                            **vocabulary_metadata(relation_scope),
                        },
                        origin="deterministic_derived",
                        lifecycle="accepted",
                        processing_run_id=run_id,
                        created_revision=revision.revision,
                    )
                )
                relation_locator = relation_candidate.locator
                locator_hash = sha256(
                    json.dumps(
                        relation_locator,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode()
                ).hexdigest()
                session.add(
                    EvidenceLinkModel(
                        evidence_link_id=_stable_id(
                            f"evidence-link:relation:{relation_id}:"
                            f"{observation.observation_id}:{locator_hash}"
                        ),
                        target_kind="relation",
                        target_id=relation_id,
                        observation_id=observation.observation_id,
                        artifact_id=observation.artifact_id,
                        locator=relation_locator,
                        locator_hash=locator_hash,
                    )
                )
            else:
                existing_relation.superseded_revision = None
            relation_ids.append(relation_id)

        change = KnowledgeChangeModel(
            change_id=_stable_id(f"knowledge-change:{run_id}"),
            revision=revision.revision,
            changed_ids={
                "objects": object_ids,
                "claims": claim_ids,
                "relations": relation_ids,
            },
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
                    "object_ids": object_ids,
                    "claim_ids": claim_ids,
                    "relation_ids": relation_ids,
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
    PROCESSOR_VERSION = "4"

    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        super().__init__(
            processor_name="nvd-canonical-normalizer",
            projection=NVDHotBugNormalizer(),
            locator_for=_nvd_locator_for,
            relations_for=_nvd_relations,
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
        "cvss_version": "$.cve.metrics",
        "cwes": "$.cve.weaknesses",
        "references": "$.cve.references",
        "exploit_references": "$.cve.references",
        "published": "$.cve.published",
        "last_modified": "$.cve.lastModified",
    }
    return {"kind": "jsonpath", "path": paths.get(predicate, "$.cve")}


def _nvd_relations(projection: dict[str, object]) -> list[RelationCandidate]:
    relations: list[RelationCandidate] = []
    raw_cwes = projection.get("cwes")
    if isinstance(raw_cwes, list):
        for value in raw_cwes:
            if not isinstance(value, str) or not value.startswith("CWE-"):
                continue
            cwe_id = value.upper()
            relations.append(
                RelationCandidate(
                    relation_type="has-weakness",
                    target=ObjectCandidate(
                        object_type="Weakness",
                        canonical_key=f"weakness:{cwe_id}",
                        properties={"cwe_id": cwe_id},
                        identifiers={"cwe": [cwe_id]},
                    ),
                    locator={"kind": "jsonpath", "path": "$.cve.weaknesses"},
                )
            )

    raw_exploits = projection.get("exploit_references")
    if isinstance(raw_exploits, list):
        for item in raw_exploits:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            reference_index = item.get("reference_index")
            if not isinstance(url, str) or not isinstance(reference_index, int):
                continue
            relations.append(
                RelationCandidate(
                    relation_type="has-poc",
                    target=ObjectCandidate(
                        object_type="ExploitArtifact",
                        canonical_key=_exploit_artifact_key(url),
                        properties={
                            "url": url,
                            "source_semantics": "nvd_reference_exploit_tag",
                        },
                    ),
                    locator={
                        "kind": "jsonpath",
                        "path": f"$.cve.references[{reference_index}]",
                    },
                )
            )
    return relations


def _exploit_artifact_key(url: str) -> str:
    digest = sha256(url.strip().encode()).hexdigest()
    return f"exploit-artifact:url-sha256:{digest}"


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


async def _supersede_source_relations(
    session: AsyncSession,
    *,
    subject_id: str,
    relation_type: str,
    source_id: str,
    superseded_revision: int,
) -> None:
    current = list(
        await session.scalars(
            select(RelationModel).where(
                RelationModel.source_object_id == subject_id,
                RelationModel.relation_type == relation_type,
                RelationModel.lifecycle == "accepted",
                RelationModel.superseded_revision.is_(None),
            )
        )
    )
    for relation in current:
        if relation.qualifier.get("source_id") == source_id:
            relation.superseded_revision = superseded_revision


async def _upsert_related_object(
    session: AsyncSession,
    candidate: ObjectCandidate,
    revision: int,
) -> ObjectModel:
    obj = await session.scalar(
        select(ObjectModel).where(
            ObjectModel.object_type == candidate.object_type,
            ObjectModel.canonical_key == candidate.canonical_key,
        )
    )
    if obj is None:
        obj = ObjectModel(
            object_id=stable_object_id(candidate.object_type, candidate.canonical_key),
            object_type=candidate.object_type,
            canonical_key=candidate.canonical_key,
            properties=candidate.properties,
            created_revision=revision,
        )
        session.add(obj)
    elif candidate.properties:
        obj.properties = {**obj.properties, **candidate.properties}
    for namespace, values in candidate.identifiers.items():
        for value in values:
            existing = await session.scalar(
                select(ExternalIdentifierModel).where(
                    ExternalIdentifierModel.namespace == namespace,
                    ExternalIdentifierModel.value == value,
                )
            )
            if existing is None:
                session.add(
                    ExternalIdentifierModel(
                        external_identifier_id=_stable_id(
                            f"external-id:{namespace}:{value}"
                        ),
                        namespace=namespace,
                        value=value,
                        object_id=obj.object_id,
                    )
                )
            elif existing.object_id != obj.object_id:
                raise ValueError(
                    f"identifier collision for {namespace}:{value}: "
                    f"{existing.object_id} != {obj.object_id}"
                )
    return obj
