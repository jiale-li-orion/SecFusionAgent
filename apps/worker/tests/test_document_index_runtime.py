from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import apps.worker.tasks as worker_tasks
from packages.enrichment.semantic.documents import DocumentChunkExtraction
from packages.intelligence.documents.parsers import PlainTextDocumentParser
from packages.intelligence.documents.service import ManagedDocumentService
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.retrieval.contracts import EmbeddingBatch
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.document_models import DocumentChunkModel, InsightCandidateModel
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.config import Settings
from packages.shared.db import Base
from packages.shared.model_provider import StructuredModelRequest
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

NOW = datetime(2026, 9, 26, 16, 0, tzinfo=UTC)
SOURCE = next(
    item
    for item in load_source_definitions(Path("config/sources"))
    if item.source_id == "trailofbits-research"
)


class FakeRuntimeAIProvider:
    name = "runtime-chat"
    version = "runtime-v1"

    async def embed(self, texts: list[str]) -> EmbeddingBatch:
        return EmbeddingBatch(
            model="runtime-embedding",
            version="runtime-v1",
            dimensions=3,
            vectors=[[1.0, 0.0, float(index)] for index, _ in enumerate(texts)],
        )

    async def generate_structured(
        self,
        request: StructuredModelRequest,
        response_model: type[DocumentChunkExtraction],
    ) -> DocumentChunkExtraction:
        text = request.data.get("text")
        assert isinstance(text, str)
        quote = "authentication bypass"
        assert quote in text
        return response_model.model_validate(
            {
                "claims": [
                    {
                        "predicate": "attack_condition",
                        "value": "unauthenticated request",
                        "evidence": {"quote": quote},
                    }
                ],
                "relations": [],
            }
        )


@pytest.mark.parametrize("background_enabled", [True, False])
@pytest.mark.asyncio
async def test_document_index_worker_runs_dense_and_semantic_when_configured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    background_enabled: bool,
) -> None:
    db_path = tmp_path / "worker-runtime.sqlite3"
    database_url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    run_id = "00000000-0000-0000-0000-000000000123"
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
            external_object_id="worker-runtime-doc",
            body=b"The report confirms an authentication bypass in the exposed endpoint.",
            media_type="text/plain",
            canonical_url="https://example.invalid/worker-runtime",
            published_at=NOW,
            updated_at=NOW,
            external_revision="v1",
            request_metadata={"title": "Worker runtime probe"},
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
        model_base_url="https://provider.invalid/v1",
        model_name="runtime-chat",
        background_llm_enabled=background_enabled,
        embedding_model_name="runtime-embedding",
        embedding_dimensions=3,
    )
    monkeypatch.setattr(worker_tasks, "get_settings", lambda: settings)

    def provider_factory(settings, client):
        assert background_enabled, "paused indexing must not construct any model provider"
        return FakeRuntimeAIProvider()

    monkeypatch.setattr(worker_tasks, "create_configured_ai_provider", provider_factory)

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
            expected_status = "retrieval_ready" if background_enabled else "lexical_ready"
            assert {item.index_status for item in chunks} == {expected_status}
            if not background_enabled:
                assert all(item.embedding_model is None for item in chunks)
                insights = list(await session.scalars(select(InsightCandidateModel)))
                assert all(item.evidence_maturity != "semantic_extracted" for item in insights)
                assert all(not item.related_claim_ids for item in insights)
                return
            assert all(item.embedding_model == "runtime-embedding" for item in chunks)
            insight = await session.scalar(
                select(InsightCandidateModel).where(
                    InsightCandidateModel.document_revision_id == managed.document_revision_id
                )
            )
            assert insight is not None
            assert insight.evidence_maturity == "semantic_extracted"
            assert insight.related_claim_ids
    finally:
        await verify_engine.dispose()


@pytest.mark.asyncio
async def test_document_worker_terminally_skips_material_rejection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from packages.intelligence.documents.quality import DocumentMaterialRejectedError

    class RejectedIndex:
        async def build_lexical_index(self, session, *, document_revision_id):
            raise DocumentMaterialRejectedError("document rejected by material quality assessment")

    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'skip.sqlite3'}",
        model_base_url="https://provider.invalid/v1",
        model_name="fake",
    )
    monkeypatch.setattr(worker_tasks, "get_settings", lambda: settings)
    monkeypatch.setattr(worker_tasks, "DocumentIndexService", RejectedIndex)
    monkeypatch.setattr(
        worker_tasks,
        "create_configured_ai_provider",
        lambda *args: pytest.fail("rejected material must not create a model"),
    )
    with caplog.at_level("INFO"):
        assert await worker_tasks._index_document_revision({"document_revision_id": "bad"}) == 0
    assert "document_index_skipped" in caplog.text
    assert "bad" in caplog.text


@pytest.mark.asyncio
async def test_document_worker_does_not_swallow_genuine_processing_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenIndex:
        async def build_lexical_index(self, session, *, document_revision_id):
            raise ValueError("corrupt indexing state")

    settings = Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 'error.sqlite3'}")
    monkeypatch.setattr(worker_tasks, "get_settings", lambda: settings)
    monkeypatch.setattr(worker_tasks, "DocumentIndexService", BrokenIndex)
    with pytest.raises(ValueError, match="corrupt indexing state"):
        await worker_tasks._index_document_revision({"document_revision_id": "broken"})
