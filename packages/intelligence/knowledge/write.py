from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from pydantic import JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.knowledge.contracts import (
    EnrichmentCandidate,
    EvidencePointer,
    KnowledgeOrigin,
    ObjectCandidate,
)
from packages.intelligence.knowledge.vocabulary import (
    VocabularyScope,
    canonical_term,
    classify_object_type,
    classify_term,
    vocabulary_metadata,
)
from packages.intelligence.normalization.canonical import NormalizationResult
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
from packages.sources.contracts import SourceDefinition


class EvidenceBackedKnowledgeWriter:
    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(UTC))

    async def apply(
        self,
        session: AsyncSession,
        *,
        root_object_id: str | None = None,
        source: SourceDefinition,
        observation: EvidencePointer,
        candidate: EnrichmentCandidate,
        processor_name: str,
        processor_version: str,
        origin: KnowledgeOrigin = "source_asserted",
    ) -> NormalizationResult:
        root_seed = root_object_id
        if root_seed is None and candidate.root_object is not None:
            root_seed = f"{candidate.root_object.object_type}:{candidate.root_object.canonical_key}"
        if root_seed is None:
            raise ValueError("knowledge writer requires root_object_id or candidate.root_object")
        run_id = _stable_id(
            f"processing:{processor_name}:{processor_version}:{root_seed}:"
            f"{observation.observation_id}"
        )
        existing_run = await session.get(ProcessingRunModel, run_id)
        if existing_run is not None and existing_run.status == "success":
            change = await session.scalar(
                select(KnowledgeChangeModel).where(
                    KnowledgeChangeModel.cause_processing_run_id == run_id
                )
            )
            if change is None:
                raise RuntimeError("successful enrichment has no knowledge change")
            return _result(change, observation.observation_id, run_id)

        _validate_candidate_vocabulary(candidate, origin=origin)
        now = self._now()
        if existing_run is None:
            session.add(
                ProcessingRunModel(
                    run_id=run_id,
                    processor_type="enrichment",
                    processor_name=processor_name,
                    processor_version=processor_version,
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

        if root_object_id is None:
            if candidate.root_object is None:
                raise ValueError("candidate.root_object is required when root_object_id is absent")
            root = await _upsert_object(session, candidate.root_object, revision.revision)
            root_object_id = root.object_id
        else:
            existing_root = await session.get(ObjectModel, root_object_id)
            if existing_root is None:
                raise LookupError(f"root object not found: {root_object_id}")
            root = existing_root
        await _upsert_identifiers(
            session,
            root.object_id,
            candidate.root_identifiers,
        )
        _validate_candidate_shapes(candidate, origin=origin, subject_type=root.object_type)

        for predicate in candidate.replace_predicates:
            await _supersede_source_claims(
                session,
                subject_id=root_object_id,
                predicate=predicate,
                source_id=source.source_id,
                superseded_revision=revision.revision,
            )
        for relation_type in candidate.replace_relation_types:
            await _supersede_source_relations(
                session,
                subject_id=root_object_id,
                relation_type=relation_type,
                source_id=source.source_id,
                superseded_revision=revision.revision,
            )

        claim_ids: list[str] = []
        for claim_candidate in candidate.claims:
            if claim_candidate.predicate not in candidate.replace_predicates:
                await _supersede_source_claims(
                    session,
                    subject_id=root_object_id,
                    predicate=claim_candidate.predicate,
                    source_id=source.source_id,
                    superseded_revision=revision.revision,
                )
            fingerprint = _json_hash(
                {"value": claim_candidate.value, "qualifier": claim_candidate.qualifier}
            )
            claim_id = _stable_id(
                f"claim:{root_object_id}:{claim_candidate.predicate}:"
                f"{observation.observation_id}:{fingerprint}"
            )
            if await session.get(ClaimModel, claim_id) is None:
                session.add(
                    ClaimModel(
                        claim_id=claim_id,
                        subject_id=root_object_id,
                        predicate=claim_candidate.predicate,
                        value=claim_candidate.value,
                        qualifier={
                            **claim_candidate.qualifier,
                            "source_id": source.source_id,
                            **vocabulary_metadata(
                                classify_term(
                                    "claim",
                                    claim_candidate.predicate,
                                    origin=origin,
                                    subject_type=root.object_type,
                                    qualifier_keys=claim_candidate.qualifier.keys(),
                                )
                            ),
                        },
                        origin=origin,
                        lifecycle="accepted",
                        processing_run_id=run_id,
                        created_revision=revision.revision,
                    )
                )
                _add_evidence_link(
                    session,
                    target_kind="claim",
                    target_id=claim_id,
                    observation=observation,
                    locator=claim_candidate.locator,
                )
            claim_ids.append(claim_id)

        relation_ids: list[str] = []
        object_ids: list[str] = [root_object_id]
        for relation_candidate in candidate.relations:
            target = await _upsert_object(session, relation_candidate.target, revision.revision)
            if target.object_id not in object_ids:
                object_ids.append(target.object_id)
            fingerprint = _json_hash(relation_candidate.qualifier)
            relation_id = _stable_id(
                f"relation:{root_object_id}:{relation_candidate.relation_type}:{target.object_id}:"
                f"{observation.observation_id}:{fingerprint}"
            )
            if await session.get(RelationModel, relation_id) is None:
                session.add(
                    RelationModel(
                        relation_id=relation_id,
                        source_object_id=root_object_id,
                        relation_type=relation_candidate.relation_type,
                        target_object_id=target.object_id,
                        qualifier={
                            **relation_candidate.qualifier,
                            "source_id": source.source_id,
                            **vocabulary_metadata(
                                classify_term(
                                    "relation",
                                    relation_candidate.relation_type,
                                    origin=origin,
                                    subject_type=root.object_type,
                                    target_type=relation_candidate.target.object_type,
                                    qualifier_keys=relation_candidate.qualifier.keys(),
                                )
                            ),
                        },
                        origin=origin,
                        lifecycle="accepted",
                        processing_run_id=run_id,
                        created_revision=revision.revision,
                    )
                )
                _add_evidence_link(
                    session,
                    target_kind="relation",
                    target_id=relation_id,
                    observation=observation,
                    locator=relation_candidate.locator,
                )
            relation_ids.append(relation_id)

        change = KnowledgeChangeModel(
            change_id=_stable_id(f"knowledge-change:{run_id}"),
            revision=revision.revision,
            changed_ids={"objects": object_ids, "claims": claim_ids, "relations": relation_ids},
            cause_processing_run_id=run_id,
            cause_observation_id=observation.observation_id,
            committed_at=now,
        )
        session.add(change)
        session.add(
            OutboxEventModel(
                event_id=_stable_id(f"outbox:knowledge.changed:{run_id}"),
                topic="knowledge.changed",
                aggregate_id=root_object_id,
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
        run = await session.get(ProcessingRunModel, run_id)
        if run is None:
            raise RuntimeError("processing run disappeared during enrichment")
        run.status = "success"
        run.finished_at = now
        await session.flush()
        return _result(change, observation.observation_id, run_id)


def _validate_candidate_vocabulary(
    candidate: EnrichmentCandidate,
    *,
    origin: KnowledgeOrigin,
) -> None:
    objects = [item for item in [candidate.root_object] if item is not None]
    objects.extend(item.target for item in candidate.relations)
    for obj in objects:
        scope = classify_object_type(obj.object_type, origin=origin)
        if scope is VocabularyScope.UNREGISTERED:
            raise ValueError(f"unregistered canonical object_type: {obj.object_type}")

    claim_names = {item.predicate for item in candidate.claims}.union(candidate.replace_predicates)
    for predicate in claim_names:
        scope = classify_term("claim", predicate, origin=origin)
        if scope is VocabularyScope.UNREGISTERED:
            raise ValueError(f"unregistered canonical claim predicate: {predicate}")

    relation_names = {item.relation_type for item in candidate.relations}.union(
        candidate.replace_relation_types
    )
    for relation_type in relation_names:
        scope = classify_term("relation", relation_type, origin=origin)
        if scope is VocabularyScope.UNREGISTERED:
            raise ValueError(f"unregistered canonical relation type: {relation_type}")


def _validate_candidate_shapes(
    candidate: EnrichmentCandidate,
    *,
    origin: KnowledgeOrigin,
    subject_type: str,
) -> None:
    for claim in candidate.claims:
        scope = classify_term(
            "claim",
            claim.predicate,
            origin=origin,
            subject_type=subject_type,
            qualifier_keys=claim.qualifier.keys(),
        )
        if scope is VocabularyScope.UNREGISTERED:
            term = canonical_term("claim", claim.predicate)
            expected = term.subject_types if term is not None else ()
            raise ValueError(
                "canonical claim subject type mismatch: "
                f"{subject_type} --{claim.predicate}; expected one of {expected}"
            )

    for relation in candidate.relations:
        scope = classify_term(
            "relation",
            relation.relation_type,
            origin=origin,
            subject_type=subject_type,
            target_type=relation.target.object_type,
            qualifier_keys=relation.qualifier.keys(),
        )
        if scope is VocabularyScope.UNREGISTERED:
            term = canonical_term("relation", relation.relation_type)
            expected_subjects = term.subject_types if term is not None else ()
            expected_targets = term.target_types if term is not None else ()
            raise ValueError(
                "canonical relation shape mismatch: "
                f"{subject_type} --{relation.relation_type}-> "
                f"{relation.target.object_type}; expected subjects={expected_subjects} "
                f"targets={expected_targets} required_qualifiers="
                f"{term.required_qualifier_keys if term is not None else ()}"
            )


async def _upsert_object(
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
            object_id=_stable_id(f"object:{candidate.object_type}:{candidate.canonical_key}"),
            object_type=candidate.object_type,
            canonical_key=candidate.canonical_key,
            properties=candidate.properties,
            created_revision=revision,
        )
        session.add(obj)
    elif candidate.properties:
        obj.properties = {**obj.properties, **candidate.properties}
    await _upsert_identifiers(session, obj.object_id, candidate.identifiers)
    return obj


async def _upsert_identifiers(
    session: AsyncSession,
    object_id: str,
    identifiers: dict[str, list[str]],
) -> None:
    for namespace, values in identifiers.items():
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
                        external_identifier_id=_stable_id(f"external-id:{namespace}:{value}"),
                        namespace=namespace,
                        value=value,
                        object_id=object_id,
                    )
                )
            elif existing.object_id != object_id:
                raise ValueError(
                    f"identifier collision for {namespace}:{value}: "
                    f"{existing.object_id} != {object_id}"
                )


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


def _add_evidence_link(
    session: AsyncSession,
    *,
    target_kind: str,
    target_id: str,
    observation: EvidencePointer,
    locator: dict[str, JsonValue],
) -> None:
    locator_hash = _json_hash(locator)
    session.add(
        EvidenceLinkModel(
            evidence_link_id=_stable_id(
                f"evidence-link:{target_kind}:{target_id}:{observation.observation_id}:"
                f"{locator_hash}"
            ),
            target_kind=target_kind,
            target_id=target_id,
            observation_id=observation.observation_id,
            artifact_id=observation.artifact_id,
            locator=locator,
            locator_hash=locator_hash,
        )
    )


def _json_hash(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _stable_id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"secfusion:{value}"))


def _result(
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
