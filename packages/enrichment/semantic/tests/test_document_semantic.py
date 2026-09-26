from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

import pytest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from packages.enrichment.semantic.documents import DocumentSemanticService
from packages.intelligence.documents.parsers import PlainTextDocumentParser
from packages.intelligence.documents.service import ManagedDocumentResult, ManagedDocumentService
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.knowledge.read import get_object_by_id
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.document_models import InsightCandidateModel
from packages.intelligence.storage.models import ProcessingRunModel
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.db import Base
from packages.shared.model_provider import ModelProvider, StructuredModelRequest
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

NOW = datetime(2026, 9, 26, 9, 0, tzinfo=UTC)
SOURCE = next(
    item
    for item in load_source_definitions(Path("config/sources"))
    if item.source_id == "arxiv-ai-security"
)
TResponse = TypeVar("TResponse", bound=BaseModel)


class FakeModelProvider(ModelProvider):
    name = "fake-structured-model"
    version = "2026-09-26"

    def __init__(self, *, invalid_quote: bool = False, empty: bool = False) -> None:
        self.invalid_quote = invalid_quote
        self.empty = empty
        self.requests: list[StructuredModelRequest] = []

    async def generate_structured(
        self,
        request: StructuredModelRequest,
        response_model: type[TResponse],
    ) -> TResponse:
        self.requests.append(request)
        if self.empty:
            return response_model.model_validate({"claims": [], "relations": []})
        quote = "not present in the document" if self.invalid_quote else "authentication bypass"
        return response_model.model_validate(
            {
                "claims": [
                    {
                        "predicate": "attack_condition",
                        "value": "unauthenticated request",
                        "qualifier": {"scope": "OpenAI-compatible endpoint"},
                        "evidence": {"quote": quote},
                    }
                ],
                "relations": [
                    {
                        "relation_type": "affects-product",
                        "target_type": "Product",
                        "target_key": "vllm",
                        "target_properties": {"name": "vLLM"},
                        "target_identifiers": {},
                        "qualifier": {},
                        "evidence": {"quote": "vLLM"},
                    }
                ],
            }
        )


@pytest.mark.asyncio
async def test_semantic_document_enrichment_requires_verbatim_evidence() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    provider = FakeModelProvider()
    try:
        result = await _seed_document(factory)
        async with factory() as session, session.begin():
            semantic = await DocumentSemanticService(provider).extract(
                session,
                source=SOURCE,
                document_revision_id=result.document_revision_id,
            )
        assert semantic.knowledge_revision is not None
        assert len(semantic.claim_ids) == 1
        assert len(semantic.relation_ids) == 1
        assert provider.requests
        assert (
            provider.requests[0].metadata["prompt_version"]
            == DocumentSemanticService.PROMPT_VERSION
        )
        assert provider.requests[0].metadata["semantic_profile"] == "research"
        assert provider.requests[0].metadata["source_class"] == "research_insight"
        assert provider.requests[0].metadata["source_role"] == "reference"

        async with factory() as session:
            view = await get_object_by_id(session, result.object_id)
            assert view is not None
            claim = next(item for item in view.claims if item.predicate == "attack_condition")
            assert claim.origin == "semantic_derived"
            assert len(claim.evidence) == 1
            locator = claim.evidence[0].locator
            assert locator["kind"] == "document_chunk"
            assert locator["quote"] == "authentication bypass"
            assert isinstance(locator["char_start"], int)
            assert isinstance(locator["char_end"], int)

            relation = next(
                item for item in view.relations if item.relation_type == "affects-product"
            )
            assert relation.target.object_type == "Product"
            assert relation.target.canonical_key == "vllm"
            assert relation.evidence[0].locator["quote"] == "vLLM"

            insight = await session.scalar(
                select(InsightCandidateModel).where(
                    InsightCandidateModel.document_revision_id == result.document_revision_id
                )
            )
            assert insight is not None
            assert insight.evidence_maturity == "semantic_extracted"
            assert insight.related_claim_ids == semantic.claim_ids
            assert insight.related_relation_ids == semantic.relation_ids

            run = await session.get(ProcessingRunModel, semantic.processing_run_id)
            assert run is not None
            assert run.model == provider.name
            assert run.prompt_version == DocumentSemanticService.PROMPT_VERSION
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_semantic_document_enrichment_rejects_hallucinated_quote() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        result = await _seed_document(factory)
        with pytest.raises(ValueError, match="not present in chunk"):
            async with factory() as session, session.begin():
                await DocumentSemanticService(FakeModelProvider(invalid_quote=True)).extract(
                    session,
                    source=SOURCE,
                    document_revision_id=result.document_revision_id,
                )

        async with factory() as session:
            view = await get_object_by_id(session, result.object_id)
            assert view is not None
            assert all(item.origin != "semantic_derived" for item in view.claims)
            assert all(item.origin != "semantic_derived" for item in view.relations)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_semantic_scan_can_record_no_supported_findings() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    provider = FakeModelProvider(empty=True)
    try:
        result = await _seed_document(factory)
        async with factory() as session, session.begin():
            first = await DocumentSemanticService(provider).extract(
                session,
                source=SOURCE,
                document_revision_id=result.document_revision_id,
            )
        assert first.knowledge_revision is None
        assert first.claim_ids == []
        assert first.relation_ids == []
        assert first.replay is False

        async with factory() as session, session.begin():
            replay = await DocumentSemanticService(provider).extract(
                session,
                source=SOURCE,
                document_revision_id=result.document_revision_id,
            )
        assert replay.processing_run_id == first.processing_run_id
        assert replay.replay is True

        async with factory() as session:
            insight = await session.scalar(
                select(InsightCandidateModel).where(
                    InsightCandidateModel.document_revision_id == result.document_revision_id
                )
            )
            assert insight is not None
            assert insight.evidence_maturity == "semantic_scanned"
    finally:
        await engine.dispose()


async def _seed_document(
    factory: async_sessionmaker[AsyncSession],
) -> ManagedDocumentResult:
    async with factory() as session, session.begin():
        await sync_source_definitions(session, [SOURCE])
        session.add(
            AcquisitionRunModel(
                run_id="semantic-paper-run",
                source_id=SOURCE.source_id,
                trigger="scheduled",
                parent_run_id=None,
                query_spec={},
                status="success",
                cursor_in={},
                cursor_out={},
                attempt=1,
                created_at=NOW,
                started_at=NOW,
                finished_at=NOW,
            )
        )

    envelope = IngestEnvelope.for_binary_payload(
        acquisition_run_id="semantic-paper-run",
        trigger=AcquisitionTrigger.SCHEDULED,
        source_id=SOURCE.source_id,
        external_object_id="2609.54321",
        body=(
            b"The paper reports an authentication bypass affecting the vLLM "
            b"OpenAI-compatible endpoint. The mitigation enforces authentication."
        ),
        media_type="text/plain",
        canonical_url="https://arxiv.org/abs/2609.54321v1",
        published_at=NOW,
        updated_at=NOW,
        external_revision="2609.54321v1",
        request_metadata={"title": "Authentication Bypass Study"},
        observed_at=NOW,
    )
    service = ManagedDocumentService(
        EvidenceIngress(MemoryArtifactStore(), now=lambda: NOW),
        {"text/plain": PlainTextDocumentParser()},
        now=lambda: NOW,
    )
    async with factory() as session, session.begin():
        return await service.ingest(session, SOURCE, envelope)
