import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.knowledge.write import EvidenceBackedKnowledgeWriter
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    EvidenceLinkModel,
    ExternalIdentifierModel,
    ObjectModel,
)
from packages.intelligence.structured.github_repo import GitHubRepoMapper
from packages.intelligence.structured.service import StructuredIndexService
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.db import Base
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

NOW = datetime(2026, 9, 25, 14, 0, tzinfo=UTC)
FIXTURE = json.loads(Path("tests/fixtures/github_repo.json").read_text())
SOURCE = next(
    item
    for item in load_source_definitions(Path("config/sources"))
    if item.source_id == "github-target-repos"
)


@pytest.mark.asyncio
async def test_structured_repo_ingest_is_traceable_and_replay_safe() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    service = StructuredIndexService(
        EvidenceIngress(MemoryArtifactStore(), now=lambda: NOW),
        EvidenceBackedKnowledgeWriter(now=lambda: NOW),
        {"github_repo": GitHubRepoMapper()},
    )
    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, [SOURCE])
            session.add(
                AcquisitionRunModel(
                    run_id="repo-run",
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

        envelope = IngestEnvelope.for_json_payload(
            acquisition_run_id="repo-run",
            trigger=AcquisitionTrigger.SCHEDULED,
            source_id=SOURCE.source_id,
            external_object_id="vllm-project/vllm",
            payload=FIXTURE,
            canonical_url="https://github.com/vllm-project/vllm",
            published_at=NOW,
            updated_at=NOW,
            external_revision="updated=2026-09-25T09:00:00+00:00;pushed=2026-09-25T08:55:00+00:00",
            observed_at=NOW,
        )
        async with factory() as session, session.begin():
            first = await service.ingest(session, SOURCE, envelope)
        assert first.replay is False
        assert len(first.normalization.object_ids) == 1

        async with factory() as session:
            repo = await session.scalar(
                select(ObjectModel).where(ObjectModel.canonical_key == "github:vllm-project/vllm")
            )
            assert repo is not None
            assert repo.object_type == "Repo"
            assert repo.properties["owner"] == "vllm-project"
            ids = list(
                await session.scalars(
                    select(ExternalIdentifierModel).where(
                        ExternalIdentifierModel.object_id == repo.object_id
                    )
                )
            )
            assert {item.namespace for item in ids} == {
                "github_repo",
                "github_repo_id",
                "github_node_id",
            }
            claims = list(
                await session.scalars(
                    select(ClaimModel).where(ClaimModel.subject_id == repo.object_id)
                )
            )
            values = {claim.predicate: claim.value for claim in claims}
            assert values["github_default_branch"] == "main"
            assert values["github_archived"] is False
            assert values["github_license_spdx"] == "Apache-2.0"
            assert await _count(session, EvidenceLinkModel) == len(claims)
            assert await _count(session, ObservationModel) == 1

        async with factory() as session, session.begin():
            replay = await service.ingest(session, SOURCE, envelope)
        assert replay.replay is True
        assert replay.normalization.knowledge_revision == first.normalization.knowledge_revision

        revised_payload = dict(FIXTURE)
        revised_payload["stargazers_count"] = 93000
        revised_payload["license"] = None
        revised_payload["updated_at"] = "2026-09-25T10:00:00Z"
        async with factory() as session, session.begin():
            session.add(
                AcquisitionRunModel(
                    run_id="repo-run-2",
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
        revised_envelope = IngestEnvelope.for_json_payload(
            acquisition_run_id="repo-run-2",
            trigger=AcquisitionTrigger.SCHEDULED,
            source_id=SOURCE.source_id,
            external_object_id="vllm-project/vllm",
            payload=revised_payload,
            canonical_url="https://github.com/vllm-project/vllm",
            published_at=NOW,
            updated_at=NOW,
            external_revision="updated=2026-09-25T10:00:00+00:00;pushed=2026-09-25T08:55:00+00:00",
            observed_at=NOW,
        )
        async with factory() as session, session.begin():
            revised = await service.ingest(session, SOURCE, revised_envelope)
        assert revised.replay is False
        assert revised.normalization.knowledge_revision > first.normalization.knowledge_revision

        async with factory() as session:
            repo = await session.scalar(
                select(ObjectModel).where(ObjectModel.canonical_key == "github:vllm-project/vllm")
            )
            assert repo is not None
            current_claims = list(
                await session.scalars(
                    select(ClaimModel).where(
                        ClaimModel.subject_id == repo.object_id,
                        ClaimModel.superseded_revision.is_(None),
                    )
                )
            )
            current_values = {claim.predicate: claim.value for claim in current_claims}
            assert current_values["github_stargazers_count"] == 93000
            assert "github_license_spdx" not in current_values
            old_license = await session.scalar(
                select(ClaimModel).where(
                    ClaimModel.subject_id == repo.object_id,
                    ClaimModel.predicate == "github_license_spdx",
                )
            )
            assert old_license is not None
            assert old_license.superseded_revision is not None
            assert await _count(session, ObservationModel) == 2
            assert await _count(session, ObjectModel) == 1
    finally:
        await engine.dispose()


async def _count(session: AsyncSession, model: type[object]) -> int:
    value = await session.scalar(select(func.count()).select_from(model))
    return int(value or 0)
