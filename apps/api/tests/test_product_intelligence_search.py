from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.dependencies import database_session
from apps.api.main import create_app
from apps.runtime_models import register_runtime_models
from packages.intelligence.storage.document_models import (
    DocumentChunkModel,
    DocumentModel,
    DocumentRevisionModel,
    InsightCandidateModel,
)
from packages.intelligence.storage.knowledge_models import (
    ExternalIdentifierModel,
    KnowledgeRevisionModel,
    ObjectModel,
    RelationModel,
)
from packages.shared.db import Base

NOW = datetime(2026, 10, 7, 0, 0, tzinfo=UTC)


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        revision = KnowledgeRevisionModel(
            revision=1,
            cause_processing_run_id=None,
            cause_observation_id=None,
            committed_at=NOW,
        )
        vulnerability = ObjectModel(
            object_id="object-vulnerability",
            object_type="Vulnerability",
            canonical_key="cve:CVE-2026-42424",
            properties={"display_name": "CVE-2026-42424"},
            created_revision=1,
            superseded_revision=None,
        )
        repository = ObjectModel(
            object_id="object-repository",
            object_type="Repository",
            canonical_key="github:vllm-project/vllm",
            properties={"display_name": "vLLM"},
            created_revision=1,
            superseded_revision=None,
        )
        document_object = ObjectModel(
            object_id="object-document",
            object_type="Document",
            canonical_key="vendor:advisory-1",
            properties={"title": "Vendor Advisory 1"},
            created_revision=1,
            superseded_revision=None,
        )
        session.add_all(
            [
                revision,
                vulnerability,
                repository,
                document_object,
                ExternalIdentifierModel(
                    external_identifier_id="identifier-cve",
                    namespace="cve",
                    value="CVE-2026-42424",
                    object_id=vulnerability.object_id,
                ),
                ExternalIdentifierModel(
                    external_identifier_id="identifier-repo",
                    namespace="github_repo",
                    value="vllm-project/vllm",
                    object_id=repository.object_id,
                ),
                RelationModel(
                    relation_id="relation-vuln-repo",
                    source_object_id=vulnerability.object_id,
                    relation_type="fixed_in_repository",
                    target_object_id=repository.object_id,
                    qualifier={},
                    origin="canonical",
                    lifecycle="accepted",
                    processing_run_id=None,
                    created_revision=1,
                    superseded_revision=None,
                ),
                DocumentModel(
                    document_id="document-1",
                    object_id=document_object.object_id,
                    source_id="vendor-source",
                    external_object_id="advisory-1",
                    canonical_url="https://example.invalid/advisory-1",
                    created_at=NOW,
                ),
                DocumentRevisionModel(
                    document_revision_id="document-revision-1",
                    document_id="document-1",
                    observation_id="observation-document-1",
                    external_revision="rev-1",
                    title="Vendor Advisory 1",
                    metadata_json={},
                    published_at=NOW,
                    updated_at=NOW,
                    content_hash="a" * 64,
                    parser_name="fixture-parser",
                    parser_version="1",
                    created_at=NOW,
                ),
                DocumentChunkModel(
                    chunk_id="chunk-1",
                    document_revision_id="document-revision-1",
                    ordinal=0,
                    section="Summary",
                    page_number=1,
                    text="SECRET DOCUMENT BODY SHOULD NOT LEAK",
                    metadata_json={},
                    locator={"page": 1},
                    content_hash="b" * 64,
                    chunker_version="fixture",
                    index_status="lexical_ready",
                    embedding=[0.1, 0.2],
                    embedding_model="fixture-embedding",
                    embedding_version="1",
                ),
                DocumentChunkModel(
                    chunk_id="chunk-2",
                    document_revision_id="document-revision-1",
                    ordinal=1,
                    section="Remediation",
                    page_number=2,
                    text="SECOND SECRET DOCUMENT BODY SHOULD NOT LEAK",
                    metadata_json={},
                    locator={"page": 2},
                    content_hash="c" * 64,
                    chunker_version="fixture",
                    index_status="lexical_ready",
                    embedding=None,
                    embedding_model=None,
                    embedding_version=None,
                ),
                InsightCandidateModel(
                    insight_candidate_id="insight-candidate-1",
                    document_revision_id="document-revision-1",
                    change_type="new_document",
                    evidence_maturity="corroborated",
                    promotion_state="candidate",
                    related_object_ids=["object-vulnerability"],
                    related_claim_ids=[],
                    related_relation_ids=[],
                    created_at=NOW,
                ),
            ]
        )
    return engine, factory


@pytest.mark.asyncio
async def test_product_intelligence_search_resolves_names_and_external_ids() -> None:
    engine, factory = await _database()
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            by_name = await client.get("/api/v1/intelligence/search", params={"q": "vLLM"})
            by_id = await client.get("/api/v1/intelligence/search", params={"q": "42424"})
            document = await client.get("/api/v1/documents/by-object/object-document")
            object_alias = await client.get(
                "/api/v1/intelligence/objects/object-vulnerability"
            )
            graph = await client.get(
                "/api/v1/intelligence/objects/object-vulnerability/graph",
                params={"limit": 1},
            )

        assert by_name.status_code == 200, by_name.text
        assert by_name.json()["items"][0]["object_id"] == "object-repository"
        assert by_name.json()["items"][0]["label"] == "vLLM"

        assert by_id.status_code == 200, by_id.text
        assert by_id.json()["items"][0]["object_id"] == "object-vulnerability"
        assert by_id.json()["items"][0]["external_identifiers"]["cve"] == ["CVE-2026-42424"]

        assert object_alias.status_code == 200, object_alias.text
        assert object_alias.json()["object_id"] == "object-vulnerability"

        assert graph.status_code == 200, graph.text
        graph_body = graph.json()
        assert graph_body["center"]["object_id"] == "object-vulnerability"
        assert graph_body["center"]["label"] == "CVE-2026-42424"
        assert graph_body["neighborhood"] == "canonical_outbound_one_hop"
        assert graph_body["total_relation_count"] == 1
        assert graph_body["relations"][0]["relation_id"] == "relation-vuln-repo"
        assert graph_body["relations"][0]["target"]["object_id"] == "object-repository"

        assert document.status_code == 200, document.text
        document_body = document.json()
        assert document_body["document_id"] == "document-1"
        assert document_body["current_revision"]["document_revision_id"] == "document-revision-1"
        assert document_body["chunk_count"] == 2
        assert document_body["index_status_counts"] == {"lexical_ready": 2}
        assert document_body["embedded_chunk_count"] == 1
        assert document_body["embedding_models"] == ["fixture-embedding"]
        assert document_body["sections"] == ["Remediation", "Summary"]
        assert document_body["insight"]["promotion_state"] == "candidate"
        assert "SECRET DOCUMENT BODY" not in document.text
    finally:
        await engine.dispose()
