from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.documents.chunking import chunk_sections
from packages.intelligence.documents.parsers import ManagedDocumentParser
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.storage.document_models import (
    DocumentChunkModel,
    DocumentModel,
    DocumentRevisionModel,
    InsightCandidateModel,
)
from packages.intelligence.storage.knowledge_models import (
    EvidenceLinkModel,
    ExternalIdentifierModel,
    KnowledgeChangeModel,
    KnowledgeRevisionModel,
    ObjectModel,
)
from packages.intelligence.storage.models import ProcessingRunModel
from packages.shared.storage.models import OutboxEventModel
from packages.sources.contracts import IngestEnvelope, SourceDefinition


class ManagedDocumentResult(BaseModel):
    observation_id: str
    object_id: str
    document_id: str
    document_revision_id: str
    knowledge_revision: int
    chunk_count: int
    insight_candidate_id: str
    replay: bool = False


class ManagedDocumentService:
    CHUNKER_VERSION = "char-window-v1"

    def __init__(
        self,
        evidence_ingress: EvidenceIngress,
        parsers: dict[str, ManagedDocumentParser],
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._evidence_ingress = evidence_ingress
        self._parsers = parsers
        self._now = now or (lambda: datetime.now(UTC))

    async def ingest(
        self,
        session: AsyncSession,
        source: SourceDefinition,
        envelope: IngestEnvelope,
    ) -> ManagedDocumentResult:
        parser = self._parsers.get(envelope.media_type)
        if parser is None:
            raise ValueError(f"no managed document parser for media_type={envelope.media_type}")
        observation = await self._evidence_ingress.accept(session, source, envelope)
        existing_revision = await session.scalar(
            select(DocumentRevisionModel).where(
                DocumentRevisionModel.observation_id == observation.observation_id
            )
        )
        if existing_revision is not None:
            document = await session.get(DocumentModel, existing_revision.document_id)
            if document is None:
                raise RuntimeError("document revision exists without document")
            insight = await session.scalar(
                select(InsightCandidateModel).where(
                    InsightCandidateModel.document_revision_id
                    == existing_revision.document_revision_id
                )
            )
            if insight is None:
                raise RuntimeError("document revision exists without insight candidate")
            chunk_count = await _chunk_count(session, existing_revision.document_revision_id)
            revision = await session.scalar(
                select(KnowledgeRevisionModel)
                .where(KnowledgeRevisionModel.cause_observation_id == observation.observation_id)
                .order_by(KnowledgeRevisionModel.revision.desc())
            )
            if revision is None:
                raise RuntimeError("document revision exists without knowledge revision")
            return ManagedDocumentResult(
                observation_id=observation.observation_id,
                object_id=document.object_id,
                document_id=document.document_id,
                document_revision_id=existing_revision.document_revision_id,
                knowledge_revision=revision.revision,
                chunk_count=chunk_count,
                insight_candidate_id=insight.insight_candidate_id,
                replay=True,
            )

        now = self._now()
        run_id = _stable_id(
            f"processing:managed-document:{parser.NAME}:{parser.VERSION}:"
            f"{observation.observation_id}"
        )
        session.add(
            ProcessingRunModel(
                run_id=run_id,
                processor_type="normalization",
                processor_name=f"managed-document:{parser.NAME}",
                processor_version=parser.VERSION,
                input_revision_ids=[observation.observation_id],
                attempt=1,
                status="running",
                started_at=now,
            )
        )
        revision = KnowledgeRevisionModel(
            cause_processing_run_id=run_id,
            cause_observation_id=observation.observation_id,
            committed_at=now,
        )
        session.add(revision)
        await session.flush()

        object_type = "ResearchWork" if source.source_class == "research_insight" else "Document"
        namespace = "arxiv" if source.adapter_type == "arxiv" else source.source_family
        canonical_key = f"{namespace}:{envelope.external_object_id}"
        object_id = _stable_id(f"object:{object_type}:{canonical_key}")
        obj = await session.get(ObjectModel, object_id)
        if obj is None:
            obj = ObjectModel(
                object_id=object_id,
                object_type=object_type,
                canonical_key=canonical_key,
                properties={
                    "title": _metadata_text(envelope, "title"),
                    "source_family": source.source_family,
                },
                created_revision=revision.revision,
            )
            session.add(obj)

        identifier = await session.scalar(
            select(ExternalIdentifierModel).where(
                ExternalIdentifierModel.namespace == namespace,
                ExternalIdentifierModel.value == envelope.external_object_id,
            )
        )
        if identifier is None:
            session.add(
                ExternalIdentifierModel(
                    external_identifier_id=_stable_id(
                        f"external-id:{namespace}:{envelope.external_object_id}"
                    ),
                    namespace=namespace,
                    value=envelope.external_object_id,
                    object_id=object_id,
                )
            )

        document_id = _stable_id(f"document:{source.source_id}:{envelope.external_object_id}")
        document = await session.get(DocumentModel, document_id)
        is_new_document = document is None
        if document is None:
            document = DocumentModel(
                document_id=document_id,
                object_id=object_id,
                source_id=source.source_id,
                external_object_id=envelope.external_object_id,
                canonical_url=envelope.canonical_url,
                created_at=now,
            )
            session.add(document)

        document_revision_id = _stable_id(
            f"document-revision:{document_id}:{observation.observation_id}"
        )
        session.add(
            DocumentRevisionModel(
                document_revision_id=document_revision_id,
                document_id=document_id,
                observation_id=observation.observation_id,
                external_revision=envelope.external_revision,
                title=_metadata_text(envelope, "title"),
                metadata_json=dict(envelope.request_metadata),
                published_at=envelope.published_at,
                updated_at=envelope.updated_at,
                content_hash=envelope.content_hash,
                parser_name=parser.NAME,
                parser_version=parser.VERSION,
                created_at=now,
            )
        )
        sections = parser.parse(envelope.content_bytes())
        chunks = chunk_sections(sections)
        for chunk in chunks:
            session.add(
                DocumentChunkModel(
                    chunk_id=_stable_id(
                        f"document-chunk:{document_revision_id}:{chunk.ordinal}:"
                        f"{chunk.content_hash}"
                    ),
                    document_revision_id=document_revision_id,
                    ordinal=chunk.ordinal,
                    section=chunk.section,
                    page_number=chunk.page_number,
                    text=chunk.text,
                    metadata_json={
                        "source_id": source.source_id,
                        "object_id": object_id,
                    },
                    locator={
                        "kind": "pdf_page" if chunk.page_number is not None else "text_range",
                        "page": chunk.page_number,
                        "char_start": chunk.char_start,
                        "char_end": chunk.char_end,
                    },
                    content_hash=chunk.content_hash,
                    chunker_version=self.CHUNKER_VERSION,
                    index_status="pending",
                )
            )

        locator = {
            "kind": "document",
            "external_revision": envelope.external_revision,
        }
        locator_hash = sha256(
            json.dumps(locator, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        session.add(
            EvidenceLinkModel(
                evidence_link_id=_stable_id(
                    f"evidence-link:object:{object_id}:{observation.observation_id}:{locator_hash}"
                ),
                target_kind="object",
                target_id=object_id,
                observation_id=observation.observation_id,
                artifact_id=observation.artifact_id,
                locator=locator,
                locator_hash=locator_hash,
            )
        )

        change_type = "new_document" if is_new_document else "new_revision"
        insight_candidate_id = _stable_id(f"insight-candidate:{document_revision_id}")
        session.add(
            InsightCandidateModel(
                insight_candidate_id=insight_candidate_id,
                document_revision_id=document_revision_id,
                change_type=change_type,
                evidence_maturity="raw_managed",
                promotion_state="candidate",
                related_object_ids=[object_id],
                related_claim_ids=[],
                related_relation_ids=[],
                created_at=now,
            )
        )
        change = KnowledgeChangeModel(
            change_id=_stable_id(f"knowledge-change:{run_id}"),
            revision=revision.revision,
            changed_ids={"objects": [object_id], "claims": [], "relations": []},
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
                    "claim_ids": [],
                    "relation_ids": [],
                },
                status="pending",
                attempts=0,
                available_at=now,
            )
        )
        run = await session.get(ProcessingRunModel, run_id)
        if run is None:
            raise RuntimeError("managed document processing run disappeared")
        run.status = "success"
        run.finished_at = now
        await session.flush()
        return ManagedDocumentResult(
            observation_id=observation.observation_id,
            object_id=object_id,
            document_id=document_id,
            document_revision_id=document_revision_id,
            knowledge_revision=revision.revision,
            chunk_count=len(chunks),
            insight_candidate_id=insight_candidate_id,
        )


async def _chunk_count(session: AsyncSession, document_revision_id: str) -> int:
    chunks = list(
        await session.scalars(
            select(DocumentChunkModel.chunk_id).where(
                DocumentChunkModel.document_revision_id == document_revision_id
            )
        )
    )
    return len(chunks)


def _metadata_text(envelope: IngestEnvelope, key: str) -> str | None:
    value = envelope.request_metadata.get(key)
    return value if isinstance(value, str) else None


def _stable_id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"secfusion:{value}"))
