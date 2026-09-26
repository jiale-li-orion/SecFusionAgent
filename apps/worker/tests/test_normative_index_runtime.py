from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

import pytest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import apps.worker.tasks as worker_tasks
from packages.intelligence.documents.parsers import PlainTextDocumentParser
from packages.intelligence.documents.service import ManagedDocumentService
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.retrieval.contracts import EmbeddingBatch
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.document_models import DocumentChunkModel, InsightCandidateModel
from packages.intelligence.storage.normative_models import NormativeRequirementModel
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.config import Settings
from packages.shared.db import Base
from packages.shared.model_provider import StructuredModelRequest
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

NOW = datetime(2026, 9, 26, 21, 0, tzinfo=UTC)
SOURCE = next(
    item
    for item in load_source_definitions(Path("config/sources"))
    if item.source_id == "nist-ai-rmf"
)
TResponse = TypeVar("TResponse", bound=BaseModel)
TEXT = "NIST AI RMF is a voluntary framework. Organizations should document AI risk controls."


class FakeRuntimeNormativeProvider:
    name = "runtime-normative"
    version = "runtime-v1"

    async def embed(self, texts: list[str]) -> EmbeddingBatch:
        return EmbeddingBatch(
            model="runtime-embedding",
            version="runtime-v1",
            dimensions=3,
            vectors=[[1.0, float(index), 0.5] for index, _ in enumerate(texts)],
        )

    async def generate_structured(
        self,
        request: StructuredModelRequest,
        response_model: type[TResponse],
    ) -> TResponse:
        text = request.data.get("text")
        assert isinstance(text, str)
        assert "Organizations should document AI risk controls." in text
        assert request.metadata["semantic_profile"] == "normative"
        return response_model.model_validate(
            {
                "document_facts": [
                    {
                        "field": "binding_status",
                        "value": "voluntary",
                        "evidence": {"quote": "NIST AI RMF is a voluntary framework."},
                    }
                ],
                "requirements": [
                    {
                        "local_id": "r1",
                        "modality": "recommendation",
                        "subject": "Organizations",
                        "action": "document",
                        "object": "AI risk controls",
                        "applicability": {},
                        "risk_mapping": [],
                        "evidence": {"quote": "Organizations should document AI risk controls."},
                    }
                ],
                "controls": [],
                "control_mappings": [],
            }
        )


@pytest.mark.asyncio
async def test_document_index_worker_routes_normative_source_to_typed_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "normative-worker.sqlite3"
    database_url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    run_id = "00000000-0000-0000-0000-000000000501"
    try:
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
            external_object_id="normative-worker-test",
            body=TEXT.encode(),
            media_type="text/plain",
            canonical_url="https://www.nist.gov/itl/ai-risk-management-framework",
            published_at=NOW,
            updated_at=NOW,
            external_revision="v1",
            request_metadata={"title": "Normative worker route"},
            observed_at=NOW,
        )
        async with factory() as session, session.begin():
            managed = await ManagedDocumentService(
                EvidenceIngress(MemoryArtifactStore(), now=lambda: NOW),
                {"text/plain": PlainTextDocumentParser()},
                now=lambda: NOW,
            ).ingest(session, SOURCE, envelope)
    finally:
        await engine.dispose()

    settings = Settings(
        database_url=database_url,
        model_base_url="https://provider.example/v1",
        model_name="runtime-normative",
        embedding_model_name="runtime-embedding",
        embedding_dimensions=3,
    )
    monkeypatch.setattr(worker_tasks, "get_settings", lambda: settings)
    monkeypatch.setattr(
        worker_tasks,
        "create_configured_ai_provider",
        lambda settings, client: FakeRuntimeNormativeProvider(),
    )

    indexed = await worker_tasks._index_document_revision(
        {"document_revision_id": managed.document_revision_id}
    )
    assert indexed >= 1

    verify_engine = create_async_engine(database_url)
    verify_factory = async_sessionmaker(verify_engine, expire_on_commit=False)
    try:
        async with verify_factory() as session:
            chunks = list(
                await session.scalars(
                    select(DocumentChunkModel).where(
                        DocumentChunkModel.document_revision_id == managed.document_revision_id
                    )
                )
            )
            assert chunks
            assert {item.index_status for item in chunks} == {"retrieval_ready"}
            requirement = await session.scalar(select(NormativeRequirementModel))
            assert requirement is not None
            assert requirement.applicability_status == "not_evaluated"
            insight = await session.scalar(
                select(InsightCandidateModel).where(
                    InsightCandidateModel.document_revision_id == managed.document_revision_id
                )
            )
            assert insight is not None
            assert insight.change_type == "normative_update"
            assert insight.evidence_maturity == "normative_extracted"
            assert insight.promotion_state == "not_applicable"
    finally:
        await verify_engine.dispose()
