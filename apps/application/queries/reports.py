"""Resolve report display sources from retained evidence, without new reasoning."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.application.queries.evidence import get_evidence_by_ref
from packages.intelligence.storage.document_models import (
    DocumentChunkModel,
    DocumentModel,
    DocumentRevisionModel,
)
from packages.reasoning.citation import DecisionCitation
from packages.reasoning.report_html import ReportSource


async def report_sources(
    session: AsyncSession,
    citations: list[DecisionCitation],
) -> list[ReportSource]:
    result = []
    for ref in dict.fromkeys(item.evidence_ref for item in citations):
        if ref.startswith("document-chunk:"):
            chunk_id, separator, revision_id = ref.removeprefix("document-chunk:").partition("@")
            if not separator:
                continue
            row = (
                await session.execute(
                    select(DocumentChunkModel, DocumentRevisionModel, DocumentModel)
                    .join(
                        DocumentRevisionModel,
                        DocumentRevisionModel.document_revision_id
                        == DocumentChunkModel.document_revision_id,
                    )
                    .join(
                        DocumentModel,
                        DocumentModel.document_id == DocumentRevisionModel.document_id,
                    )
                    .where(
                        DocumentChunkModel.chunk_id == chunk_id,
                        DocumentRevisionModel.document_revision_id == revision_id,
                    )
                )
            ).first()
            if row is not None:
                chunk, revision, document = row
                result.append(
                    ReportSource(
                        evidence_ref=ref,
                        label=revision.title or document.source_id,
                        url=document.canonical_url,
                        detail=chunk.section,
                        revision_id=revision.document_revision_id,
                    )
                )
        else:
            evidence = await get_evidence_by_ref(session, ref)
            if evidence is not None:
                section = evidence.locator.get("section") or evidence.locator.get("field")
                result.append(
                    ReportSource(
                        evidence_ref=ref,
                        label=evidence.source.source_family,
                        url=evidence.observation.canonical_url,
                        detail=str(section) if section else None,
                    )
                )
    return result
