from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

import pytest
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from packages.enrichment.normative.service import NormativeKnowledgeService
from packages.intelligence.documents.parsers import PlainTextDocumentParser
from packages.intelligence.documents.service import ManagedDocumentResult, ManagedDocumentService
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.document_models import InsightCandidateModel
from packages.intelligence.storage.models import ProcessingRunModel
from packages.intelligence.storage.normative_models import (
    NormativeControlEvidenceModel,
    NormativeControlModel,
    NormativeDocumentModel,
    NormativeDocumentRevisionModel,
    NormativeRequirementModel,
    RequirementControlMappingModel,
)
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.db import Base
from packages.shared.model_provider import StructuredModelRequest
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

NOW = datetime(2026, 9, 26, 20, 0, tzinfo=UTC)
SOURCE = next(
    item
    for item in load_source_definitions(Path("config/sources"))
    if item.source_id == "nist-ai-rmf"
)
TResponse = TypeVar("TResponse", bound=BaseModel)
TEXT = (
    "NIST AI RMF is a voluntary framework for organizations. "
    "Organizations should document AI risk controls. "
    "Organizations should continuously monitor AI risks."
)


class FakeNormativeProvider:
    name = "fake-normative-model"
    version = "2026-09-26"

    def __init__(self, *, invalid_quote: bool = False) -> None:
        self.invalid_quote = invalid_quote
        self.requests: list[StructuredModelRequest] = []

    async def generate_structured(
        self,
        request: StructuredModelRequest,
        response_model: type[TResponse],
    ) -> TResponse:
        self.requests.append(request)
        quote = (
            "This obligation does not exist in the source."
            if self.invalid_quote
            else "Organizations should document AI risk controls."
        )
        payload = {
            "document_facts": [
                {
                    "field": "issuer",
                    "value": "NIST",
                    "evidence": {
                        "quote": "NIST AI RMF is a voluntary framework for organizations."
                    },
                },
                {
                    "field": "binding_status",
                    "value": "voluntary",
                    "evidence": {
                        "quote": "NIST AI RMF is a voluntary framework for organizations."
                    },
                },
            ],
            "requirements": [
                {
                    "local_id": "r1",
                    "source_clause": "Govern",
                    "modality": "recommendation",
                    "subject": "Organizations",
                    "action": "document",
                    "object": "AI risk controls",
                    "condition": None,
                    "exception": None,
                    "jurisdiction": None,
                    "applicability": {"organization_type": "AI risk manager"},
                    "risk_mapping": ["ai-risk-management"],
                    "evidence": {"quote": quote},
                }
            ],
            "controls": [
                {
                    "local_id": "c1",
                    "canonical_key": "continuous-monitoring",
                    "name": "Continuous monitoring",
                    "description": "Monitor AI risks continuously.",
                    "evidence": {"quote": "Organizations should continuously monitor AI risks."},
                }
            ],
            "control_mappings": [
                {
                    "requirement_local_id": "r1",
                    "control_local_id": "c1",
                    "relation_type": "supports",
                    "evidence": {"quote": "Organizations should continuously monitor AI risks."},
                }
            ],
        }
        return response_model.model_validate(payload)


@pytest.mark.asyncio
async def test_normative_extraction_persists_typed_evidence_and_never_sets_applicability() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    provider = FakeNormativeProvider()
    try:
        managed = await _seed_document(factory)
        async with factory() as session, session.begin():
            result = await NormativeKnowledgeService(provider, now=lambda: NOW).extract(
                session,
                source=SOURCE,
                document_revision_id=managed.document_revision_id,
            )
        assert len(result.requirement_ids) == 1
        assert len(result.control_ids) == 1
        assert len(result.mapping_ids) == 1
        assert result.replay is False
        assert provider.requests
        request = provider.requests[0]
        assert request.metadata["semantic_profile"] == "normative"
        assert "do not decide whether a requirement is applicable" in request.system_instruction
        assert "Do not create runtime policy" in request.system_instruction

        async with factory() as session:
            document = await session.get(NormativeDocumentModel, result.normative_document_id)
            assert document is not None
            assert document.source_id == SOURCE.source_id

            revision = await session.get(
                NormativeDocumentRevisionModel,
                result.normative_revision_id,
            )
            assert revision is not None
            assert revision.binding_status == "voluntary"
            assert revision.issuer == "NIST"
            assert revision.access_rights == {"classification": "public"}
            assert revision.document_revision_id == managed.document_revision_id

            requirement = await session.get(NormativeRequirementModel, result.requirement_ids[0])
            assert requirement is not None
            assert requirement.modality == "recommendation"
            assert requirement.subject == "Organizations"
            assert requirement.action == "document"
            assert requirement.object_text == "AI risk controls"
            assert requirement.applicability == {"organization_type": "AI risk manager"}
            assert requirement.applicability_status == "not_evaluated"
            assert requirement.evidence_quote == ("Organizations should document AI risk controls.")
            assert requirement.evidence_locator["kind"] == "document_chunk"
            assert requirement.evidence_locator["quote"] == requirement.evidence_quote
            assert isinstance(requirement.evidence_locator["char_start"], int)
            assert isinstance(requirement.evidence_locator["char_end"], int)

            control = await session.get(NormativeControlModel, result.control_ids[0])
            assert control is not None
            assert control.canonical_key == "continuous-monitoring"
            evidence = await session.scalar(
                select(NormativeControlEvidenceModel).where(
                    NormativeControlEvidenceModel.control_id == control.control_id
                )
            )
            assert evidence is not None
            assert evidence.evidence_quote == (
                "Organizations should continuously monitor AI risks."
            )

            mapping = await session.get(
                RequirementControlMappingModel,
                result.mapping_ids[0],
            )
            assert mapping is not None
            assert mapping.requirement_id == requirement.requirement_id
            assert mapping.control_id == control.control_id
            assert mapping.relation_type == "supports"

            insight = await session.scalar(
                select(InsightCandidateModel).where(
                    InsightCandidateModel.document_revision_id == managed.document_revision_id
                )
            )
            assert insight is not None
            assert insight.change_type == "normative_update"
            assert insight.evidence_maturity == "normative_extracted"
            assert insight.promotion_state == "not_applicable"

            run = await session.get(ProcessingRunModel, result.processing_run_id)
            assert run is not None
            assert run.status == "success"
            assert run.processor_name == NormativeKnowledgeService.PROCESSOR_NAME
            assert run.model == provider.name

        async with factory() as session, session.begin():
            replay = await NormativeKnowledgeService(provider, now=lambda: NOW).extract(
                session,
                source=SOURCE,
                document_revision_id=managed.document_revision_id,
            )
        assert replay.replay is True
        assert replay.processing_run_id == result.processing_run_id
        assert replay.requirement_ids == result.requirement_ids
        assert replay.control_ids == result.control_ids
        assert replay.mapping_ids == result.mapping_ids
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_normative_extraction_rejects_hallucinated_quote_before_derived_writes() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        managed = await _seed_document(factory)
        with pytest.raises(ValueError, match="not present in chunk"):
            async with factory() as session, session.begin():
                await NormativeKnowledgeService(
                    FakeNormativeProvider(invalid_quote=True),
                    now=lambda: NOW,
                ).extract(
                    session,
                    source=SOURCE,
                    document_revision_id=managed.document_revision_id,
                )

        async with factory() as session:
            assert await _count(session, NormativeDocumentModel) == 0
            assert await _count(session, NormativeDocumentRevisionModel) == 0
            assert await _count(session, NormativeRequirementModel) == 0
            assert await _count(session, NormativeControlModel) == 0
            assert await _count(session, RequirementControlMappingModel) == 0
            assert (
                await session.scalar(
                    select(ProcessingRunModel).where(
                        ProcessingRunModel.processor_name
                        == NormativeKnowledgeService.PROCESSOR_NAME
                    )
                )
                is None
            )
    finally:
        await engine.dispose()


async def _seed_document(
    factory: async_sessionmaker[AsyncSession],
) -> ManagedDocumentResult:
    run_id = "00000000-0000-0000-0000-000000000401"
    async with factory() as session, session.begin():
        await sync_source_definitions(session, [SOURCE])
        session.add(
            AcquisitionRunModel(
                run_id=run_id,
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
        acquisition_run_id=run_id,
        trigger=AcquisitionTrigger.SCHEDULED,
        source_id=SOURCE.source_id,
        external_object_id="nist-ai-rmf-test",
        body=TEXT.encode(),
        media_type="text/plain",
        canonical_url="https://www.nist.gov/itl/ai-risk-management-framework",
        published_at=NOW,
        updated_at=NOW,
        external_revision="test-v1",
        request_metadata={"title": "NIST AI RMF test projection"},
        observed_at=NOW,
    )
    async with factory() as session, session.begin():
        return await ManagedDocumentService(
            EvidenceIngress(MemoryArtifactStore(), now=lambda: NOW),
            {"text/plain": PlainTextDocumentParser()},
            now=lambda: NOW,
        ).ingest(session, SOURCE, envelope)


async def _count(session: AsyncSession, model: type[Base]) -> int:
    value = await session.scalar(select(func.count()).select_from(model))
    return int(value or 0)
