from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.retrieval.contracts import CandidateKind, RetrievedCandidate
from packages.intelligence.storage.document_models import (
    DocumentChunkModel,
    DocumentModel,
    DocumentRevisionModel,
)
from packages.intelligence.storage.evidence_models import EvidenceArtifactModel, ObservationModel
from packages.intelligence.storage.knowledge_models import (
    EvidenceLinkModel,
    ExternalIdentifierModel,
    ObjectModel,
    RelationModel,
)
from packages.intelligence.storage.projection_models import CurrentProjectionModel
from packages.sources.storage.models import SourceModel


class ExactRetrievalOperator:
    async def by_identifier(
        self,
        session: AsyncSession,
        *,
        namespace: str,
        value: str,
    ) -> list[RetrievedCandidate]:
        row = await session.execute(
            select(ExternalIdentifierModel, ObjectModel)
            .join(ObjectModel, ObjectModel.object_id == ExternalIdentifierModel.object_id)
            .where(
                ExternalIdentifierModel.namespace == namespace,
                ExternalIdentifierModel.value == value,
                ObjectModel.superseded_revision.is_(None),
            )
        )
        pair = row.first()
        if pair is None:
            return []
        identifier, obj = pair
        return [
            RetrievedCandidate(
                candidate_id=f"object:{obj.object_id}",
                candidate_kind=CandidateKind.OBJECT,
                object_id=obj.object_id,
                revision=obj.created_revision,
                score_channels={"exact": 1.0},
                payload={
                    "object_type": obj.object_type,
                    "canonical_key": obj.canonical_key,
                    "properties": obj.properties,
                    "matched_namespace": identifier.namespace,
                    "matched_value": identifier.value,
                },
            )
        ]

    async def by_canonical_key(
        self,
        session: AsyncSession,
        *,
        canonical_key: str,
        object_type: str | None = None,
    ) -> list[RetrievedCandidate]:
        statement = select(ObjectModel).where(
            ObjectModel.canonical_key == canonical_key,
            ObjectModel.superseded_revision.is_(None),
        )
        if object_type is not None:
            statement = statement.where(ObjectModel.object_type == object_type)
        objects = list(await session.scalars(statement.order_by(ObjectModel.object_type)))
        return [
            RetrievedCandidate(
                candidate_id=f"object:{obj.object_id}",
                candidate_kind=CandidateKind.OBJECT,
                object_id=obj.object_id,
                revision=obj.created_revision,
                score_channels={"exact": 1.0},
                payload={
                    "object_type": obj.object_type,
                    "canonical_key": obj.canonical_key,
                    "properties": obj.properties,
                },
            )
            for obj in objects
        ]


class StructuredRetrievalOperator:
    async def current(
        self,
        session: AsyncSession,
        *,
        subject_id: str | None = None,
        projection_key: str | None = None,
        projection_types: Sequence[str] | None = None,
    ) -> list[RetrievedCandidate]:
        if subject_id is None and projection_key is None:
            raise ValueError("structured retrieval requires subject_id or projection_key")
        statement = select(CurrentProjectionModel)
        conditions = []
        if subject_id is not None:
            conditions.append(CurrentProjectionModel.subject_id == subject_id)
        if projection_key is not None:
            conditions.append(CurrentProjectionModel.projection_key == projection_key)
        statement = statement.where(or_(*conditions))
        if projection_types:
            statement = statement.where(
                CurrentProjectionModel.projection_type.in_(projection_types)
            )
        rows = list(
            await session.scalars(
                statement.order_by(
                    CurrentProjectionModel.projection_type,
                    CurrentProjectionModel.projection_id,
                )
            )
        )
        return [
            RetrievedCandidate(
                candidate_id=f"projection:{row.projection_id}",
                candidate_kind=CandidateKind.PROJECTION,
                object_id=row.subject_id,
                revision=row.upstream_revision,
                valid_time=row.updated_at,
                score_channels={"structured": 1.0, "freshness": 1.0},
                payload={
                    "projection_type": row.projection_type,
                    "projection_key": row.projection_key,
                    "data": row.data,
                },
            )
            for row in rows
        ]


class LexicalRetrievalOperator:
    async def search(
        self,
        session: AsyncSession,
        *,
        query: str,
        limit: int = 20,
        source_ids: Sequence[str] | None = None,
    ) -> list[RetrievedCandidate]:
        normalized = query.strip()
        if not normalized:
            return []
        tsquery = func.plainto_tsquery("simple", normalized)
        vector = func.to_tsvector("simple", DocumentChunkModel.text)
        rank = func.ts_rank_cd(vector, tsquery).label("lexical_score")
        statement = (
            select(
                DocumentChunkModel,
                DocumentRevisionModel,
                DocumentModel,
                ObservationModel,
                SourceModel,
                rank,
            )
            .join(
                DocumentRevisionModel,
                DocumentRevisionModel.document_revision_id
                == DocumentChunkModel.document_revision_id,
            )
            .join(DocumentModel, DocumentModel.document_id == DocumentRevisionModel.document_id)
            .join(
                ObservationModel,
                ObservationModel.observation_id == DocumentRevisionModel.observation_id,
            )
            .join(SourceModel, SourceModel.source_id == ObservationModel.source_id)
            .where(vector.op("@@")(tsquery))
        )
        if source_ids:
            statement = statement.where(ObservationModel.source_id.in_(source_ids))
        rows = (
            await session.execute(
                statement.order_by(rank.desc(), DocumentChunkModel.chunk_id).limit(limit)
            )
        ).all()
        candidates: list[RetrievedCandidate] = []
        for row in rows:
            chunk = cast(DocumentChunkModel, row[0])
            revision = cast(DocumentRevisionModel, row[1])
            document = cast(DocumentModel, row[2])
            observation = cast(ObservationModel, row[3])
            source = cast(SourceModel, row[4])
            score = cast(float | None, row[5])
            candidates.append(
                _document_candidate(
                    chunk,
                    revision,
                    document,
                    observation,
                    source,
                    score_channels={"lexical": float(score or 0.0)},
                )
            )
        return candidates

    async def by_chunk_refs(
        self,
        session: AsyncSession,
        *,
        refs: Sequence[str],
    ) -> list[RetrievedCandidate]:
        parsed: list[tuple[str, str]] = []
        for ref in refs:
            prefix = "document-chunk:"
            if not ref.startswith(prefix):
                raise ValueError(f"invalid document chunk ref: {ref}")
            identity, separator, revision_id = ref.removeprefix(prefix).rpartition("@")
            if not separator or not identity or not revision_id:
                raise ValueError(f"invalid document chunk ref: {ref}")
            parsed.append((identity, revision_id))
        if not parsed:
            return []

        chunk_ids = {chunk_id for chunk_id, _ in parsed}
        rows = (
            await session.execute(
                select(
                    DocumentChunkModel,
                    DocumentRevisionModel,
                    DocumentModel,
                    ObservationModel,
                    SourceModel,
                )
                .join(
                    DocumentRevisionModel,
                    DocumentRevisionModel.document_revision_id
                    == DocumentChunkModel.document_revision_id,
                )
                .join(
                    DocumentModel,
                    DocumentModel.document_id == DocumentRevisionModel.document_id,
                )
                .join(
                    ObservationModel,
                    ObservationModel.observation_id == DocumentRevisionModel.observation_id,
                )
                .join(SourceModel, SourceModel.source_id == ObservationModel.source_id)
                .where(DocumentChunkModel.chunk_id.in_(chunk_ids))
            )
        ).all()
        candidates: dict[tuple[str, str], RetrievedCandidate] = {}
        for row in rows:
            chunk = row[0]
            revision = row[1]
            document = row[2]
            observation = row[3]
            source = row[4]
            candidates[(chunk.chunk_id, revision.document_revision_id)] = _document_candidate(
                chunk,
                revision,
                document,
                observation,
                source,
                score_channels={"reused": 1.0},
            )
        return [
            candidate
            for key in parsed
            if (candidate := candidates.get(key)) is not None
        ]


class DenseRetrievalOperator:
    async def search(
        self,
        session: AsyncSession,
        *,
        query_vector: Sequence[float],
        limit: int = 20,
        source_ids: Sequence[str] | None = None,
    ) -> list[RetrievedCandidate]:
        vector = [float(value) for value in query_vector]
        if not vector:
            raise ValueError("dense retrieval requires a non-empty query vector")
        distance = DocumentChunkModel.embedding.cosine_distance(vector).label("dense_distance")
        statement = (
            select(
                DocumentChunkModel,
                DocumentRevisionModel,
                DocumentModel,
                ObservationModel,
                SourceModel,
                distance,
            )
            .join(
                DocumentRevisionModel,
                DocumentRevisionModel.document_revision_id
                == DocumentChunkModel.document_revision_id,
            )
            .join(DocumentModel, DocumentModel.document_id == DocumentRevisionModel.document_id)
            .join(
                ObservationModel,
                ObservationModel.observation_id == DocumentRevisionModel.observation_id,
            )
            .join(SourceModel, SourceModel.source_id == ObservationModel.source_id)
            .where(DocumentChunkModel.embedding.is_not(None))
        )
        if source_ids:
            statement = statement.where(ObservationModel.source_id.in_(source_ids))
        rows = (
            await session.execute(
                statement.order_by(distance.asc(), DocumentChunkModel.chunk_id).limit(limit)
            )
        ).all()
        candidates: list[RetrievedCandidate] = []
        for row in rows:
            chunk = cast(DocumentChunkModel, row[0])
            revision = cast(DocumentRevisionModel, row[1])
            document = cast(DocumentModel, row[2])
            observation = cast(ObservationModel, row[3])
            source = cast(SourceModel, row[4])
            raw_distance = cast(float | None, row[5])
            candidates.append(
                _document_candidate(
                    chunk,
                    revision,
                    document,
                    observation,
                    source,
                    score_channels={"dense": max(0.0, 1.0 - float(raw_distance or 0.0))},
                )
            )
        return candidates


class GraphRetrievalOperator:
    async def neighbors(
        self,
        session: AsyncSession,
        *,
        object_id: str,
        direction: str = "out",
        relation_types: Sequence[str] | None = None,
        limit: int = 100,
    ) -> list[RetrievedCandidate]:
        if direction not in {"out", "in", "both"}:
            raise ValueError("graph direction must be out, in, or both")
        statement = select(RelationModel).where(
            RelationModel.lifecycle == "accepted",
            RelationModel.superseded_revision.is_(None),
        )
        if direction == "out":
            statement = statement.where(RelationModel.source_object_id == object_id)
        elif direction == "in":
            statement = statement.where(RelationModel.target_object_id == object_id)
        else:
            statement = statement.where(
                or_(
                    RelationModel.source_object_id == object_id,
                    RelationModel.target_object_id == object_id,
                )
            )
        if relation_types:
            statement = statement.where(RelationModel.relation_type.in_(relation_types))
        relations = list(
            await session.scalars(
                statement.order_by(RelationModel.created_revision, RelationModel.relation_id).limit(
                    limit
                )
            )
        )
        object_ids = {
            item
            for relation in relations
            for item in (relation.source_object_id, relation.target_object_id)
        }
        objects = {
            obj.object_id: obj
            for obj in (
                list(
                    await session.scalars(
                        select(ObjectModel).where(ObjectModel.object_id.in_(object_ids))
                    )
                )
                if object_ids
                else []
            )
        }
        return [
            RetrievedCandidate(
                candidate_id=f"relation:{relation.relation_id}",
                candidate_kind=CandidateKind.RELATION,
                relation_id=relation.relation_id,
                revision=relation.created_revision,
                score_channels={"graph": 1.0},
                payload={
                    "relation_type": relation.relation_type,
                    "origin": relation.origin,
                    "qualifier": relation.qualifier,
                    "source": _object_payload(objects.get(relation.source_object_id)),
                    "target": _object_payload(objects.get(relation.target_object_id)),
                },
            )
            for relation in relations
        ]


class EvidenceRetrievalOperator:
    async def for_target(
        self,
        session: AsyncSession,
        *,
        target_kind: str,
        target_id: str,
    ) -> list[RetrievedCandidate]:
        rows = (
            await session.execute(
                select(
                    EvidenceLinkModel,
                    ObservationModel,
                    EvidenceArtifactModel,
                    SourceModel,
                )
                .join(
                    ObservationModel,
                    ObservationModel.observation_id == EvidenceLinkModel.observation_id,
                )
                .outerjoin(
                    EvidenceArtifactModel,
                    EvidenceArtifactModel.artifact_id == EvidenceLinkModel.artifact_id,
                )
                .join(SourceModel, SourceModel.source_id == ObservationModel.source_id)
                .where(
                    EvidenceLinkModel.target_kind == target_kind,
                    EvidenceLinkModel.target_id == target_id,
                )
                .order_by(ObservationModel.observed_at, EvidenceLinkModel.evidence_link_id)
            )
        ).all()
        return [
            RetrievedCandidate(
                candidate_id=f"evidence:{link.evidence_link_id}",
                candidate_kind=CandidateKind.EVIDENCE,
                evidence_ref=link.evidence_link_id,
                source_id=source.source_id,
                source_role=source.source_role,
                source_family=source.source_family,
                upstream_source=source.upstream_source,
                revision=observation.external_revision,
                observed_at=observation.observed_at,
                valid_time=observation.updated_at or observation.published_at,
                score_channels={"evidence": 1.0, "freshness": 1.0},
                locator=link.locator,
                payload={
                    "target_kind": link.target_kind,
                    "target_id": link.target_id,
                    "observation_id": observation.observation_id,
                    "artifact_id": link.artifact_id,
                    "artifact_uri": artifact.storage_uri if artifact is not None else None,
                    "external_object_id": observation.external_object_id,
                    "canonical_url": observation.canonical_url,
                    "content_hash": observation.content_hash,
                },
            )
            for link, observation, artifact, source in rows
        ]


def _document_candidate(
    chunk: DocumentChunkModel,
    revision: DocumentRevisionModel,
    document: DocumentModel,
    observation: ObservationModel,
    source: SourceModel,
    *,
    score_channels: dict[str, float],
) -> RetrievedCandidate:
    locator = dict(chunk.locator)
    return RetrievedCandidate(
        candidate_id=f"chunk:{chunk.chunk_id}",
        candidate_kind=CandidateKind.DOCUMENT_CHUNK,
        object_id=document.object_id,
        document_chunk_id=chunk.chunk_id,
        source_id=source.source_id,
        source_role=source.source_role,
        source_family=source.source_family,
        upstream_source=source.upstream_source,
        revision=revision.document_revision_id,
        observed_at=observation.observed_at,
        valid_time=revision.updated_at or revision.published_at,
        score_channels=score_channels,
        locator=locator,
        payload={
            "document_id": document.document_id,
            "document_revision_id": revision.document_revision_id,
            "external_object_id": document.external_object_id,
            "canonical_url": document.canonical_url,
            "title": revision.title,
            "ordinal": chunk.ordinal,
            "section": chunk.section,
            "page_number": chunk.page_number,
            "text": chunk.text,
            "index_status": chunk.index_status,
            "embedding_model": chunk.embedding_model,
            "embedding_version": chunk.embedding_version,
        },
    )


def _object_payload(obj: ObjectModel | None) -> dict[str, object]:
    if obj is None:
        return {}
    return {
        "object_id": obj.object_id,
        "object_type": obj.object_type,
        "canonical_key": obj.canonical_key,
        "properties": obj.properties,
    }
