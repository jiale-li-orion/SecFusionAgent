from __future__ import annotations

import re

from pydantic import JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.ingestion.replay import ObservationReplay
from packages.intelligence.knowledge.contracts import (
    EnrichmentCandidate,
    EvidenceAnchor,
    ObjectCandidate,
    RelationCandidate,
)
from packages.intelligence.knowledge.identity import canonical_cve_id, cve_canonical_key
from packages.intelligence.knowledge.write import EvidenceBackedKnowledgeWriter
from packages.intelligence.normalization.canonical import NormalizationResult
from packages.intelligence.storage.document_models import DocumentChunkModel
from packages.sources.contracts import SourceDefinition

_CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)


class ExactCVEResearchBridge:
    """Materialize exact paper-to-CVE associations without semantic inference."""

    PROCESSOR_NAME = "research-exact-cve-bridge"
    PROCESSOR_VERSION = "1"

    def __init__(self, writer: EvidenceBackedKnowledgeWriter) -> None:
        self._writer = writer

    async def enrich_document_revision(
        self,
        session: AsyncSession,
        *,
        source: SourceDefinition,
        replay: ObservationReplay,
        root_object_id: str,
        document_revision_id: str,
    ) -> NormalizationResult:
        chunks = list(
            await session.scalars(
                select(DocumentChunkModel)
                .where(DocumentChunkModel.document_revision_id == document_revision_id)
                .order_by(DocumentChunkModel.ordinal, DocumentChunkModel.chunk_id)
            )
        )
        first_mentions: dict[str, dict[str, JsonValue]] = {}
        for chunk in chunks:
            for match in _CVE_RE.finditer(chunk.text):
                cve_id = canonical_cve_id(match.group(0))
                if cve_id in first_mentions:
                    continue
                first_mentions[cve_id] = {
                    "kind": "document_chunk",
                    "document_revision_id": document_revision_id,
                    "chunk_id": chunk.chunk_id,
                    "page": chunk.page_number,
                    "section": chunk.section,
                    "char_start": match.start(),
                    "char_end": match.end(),
                }

        relations = [
            RelationCandidate(
                relation_type="discusses-vulnerability",
                target=ObjectCandidate(
                    object_type="Vulnerability",
                    canonical_key=cve_canonical_key(cve_id),
                    properties={"display_name": cve_id},
                    identifiers={"cve": [cve_id]},
                ),
                locator=locator,
            )
            for cve_id, locator in sorted(first_mentions.items())
        ]
        return await self._writer.apply(
            session,
            root_object_id=root_object_id,
            source=source,
            observation=EvidenceAnchor(
                observation_id=replay.observation_id,
                artifact_id=replay.artifact_id,
            ),
            candidate=EnrichmentCandidate(
                relations=relations,
                replace_relation_types=["discusses-vulnerability"],
            ),
            processor_name=self.PROCESSOR_NAME,
            processor_version=self.PROCESSOR_VERSION,
            origin="deterministic_derived",
        )
