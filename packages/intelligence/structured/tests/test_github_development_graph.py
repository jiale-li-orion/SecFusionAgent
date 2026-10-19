import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.knowledge.contracts import ObjectCandidate, RelationCandidate
from packages.intelligence.knowledge.read import get_object_by_identifier
from packages.intelligence.knowledge.write import EvidenceBackedKnowledgeWriter
from packages.intelligence.projections.service import (
    CurrentProjectionService,
    get_current_projection,
)
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.knowledge_models import (
    EvidenceLinkModel,
    ObjectModel,
    RelationModel,
)
from packages.intelligence.structured.github_repo import GitHubRepoMapper
from packages.intelligence.structured.service import StructuredIndexService
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.db import Base
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

NOW = datetime(2026, 9, 25, 14, 0, tzinfo=UTC)
SOURCE = next(
    item
    for item in load_source_definitions(Path("config/sources"))
    if item.source_id == "github-target-repos"
)


def _fixture(name: str) -> dict[str, object]:
    return json.loads(Path(f"tests/fixtures/{name}.json").read_text())


def _envelope(
    run_id: str, object_type: str, payload: dict[str, object], external_id: str
) -> IngestEnvelope:
    html_url = payload.get("html_url")
    canonical_url = html_url if isinstance(html_url, str) else None
    return IngestEnvelope.for_json_payload(
        acquisition_run_id=run_id,
        trigger=AcquisitionTrigger.ON_DEMAND,
        source_id=SOURCE.source_id,
        external_object_id=external_id,
        payload=payload,
        canonical_url=canonical_url,
        published_at=NOW,
        updated_at=NOW,
        external_revision=f"rev:{object_type}:{external_id}",
        observed_at=NOW,
        request_metadata={
            "provider": "github",
            "object_type": object_type,
            "repo_full_name": "vllm-project/vllm",
        },
    )


@pytest.mark.parametrize(
    ("merged", "merged_at"),
    [
        (False, None),
        (False, "2026-09-24T10:00:00Z"),
        (None, "2026-09-24T10:00:00Z"),
        ("true", "2026-09-24T10:00:00Z"),
        (True, None),
        (True, ""),
        (True, "not-a-timestamp"),
        (True, "2026-09-24"),
        (True, "2026-09-24T10:00:00"),
    ],
)
@pytest.mark.parametrize("state", ["open", "closed"])
def test_pull_request_without_confirmed_merge_ignores_test_merge_sha(
    state: str, merged: object, merged_at: object
) -> None:
    payload = _fixture("github_pull_request")
    payload.update(state=state, merged=merged, merged_at=merged_at)
    candidate = GitHubRepoMapper().map(
        _envelope("pr-run", "pull_request", payload, "vllm-project/vllm#pull-9123")
    )

    assert {relation.relation_type for relation in candidate.relations} == {
        "belongs-to-repo",
        "head-commit",
    }
    head = next(item for item in candidate.relations if item.relation_type == "head-commit")
    assert head.target.identifiers["git_commit_sha"] == ["b" * 40]
    assert "merged-as" in candidate.replace_relation_types


def test_confirmed_merged_pull_request_maps_actual_merge_commit() -> None:
    candidate = GitHubRepoMapper().map(
        _envelope(
            "pr-run", "pull_request", _fixture("github_pull_request"), "vllm-project/vllm#pull-9123"
        )
    )

    merged = next(item for item in candidate.relations if item.relation_type == "merged-as")
    assert merged.target.identifiers["git_commit_sha"] == ["a" * 40]
    assert merged.locator == {"kind": "jsonpath", "path": "$.merge_commit_sha"}


@pytest.mark.asyncio
async def test_processor_refresh_supersedes_legacy_test_merge_relation() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    ingress = EvidenceIngress(MemoryArtifactStore(), now=lambda: NOW)
    writer = EvidenceBackedKnowledgeWriter(now=lambda: NOW)
    service = StructuredIndexService(ingress, writer, {"github_repo": GitHubRepoMapper()})
    payload = _fixture("github_pull_request")
    payload.update(state="open", merged=False, merged_at=None, closed_at=None)
    envelope = _envelope("pr-run", "pull_request", payload, "vllm-project/vllm#pull-9123")
    legacy_candidate = GitHubRepoMapper().map(envelope)
    # Reproduce v2's erroneous durable edge from the retained, unmerged source payload.
    legacy_candidate.relations = [
        item for item in legacy_candidate.relations if item.relation_type != "merged-as"
    ] + [
        RelationCandidate(
            relation_type="merged-as",
            target=ObjectCandidate(
                object_type="Commit",
                canonical_key=f"git:commit:{'a' * 40}",
                identifiers={"git_commit_sha": ["a" * 40]},
            ),
            locator={"kind": "jsonpath", "path": "$.merge_commit_sha"},
        )
    ]
    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, [SOURCE])
            session.add(
                AcquisitionRunModel(
                    run_id="pr-run",
                    source_id=SOURCE.source_id,
                    trigger="on_demand",
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
        async with factory() as session, session.begin():
            observation = await ingress.accept(session, SOURCE, envelope)
            legacy = await writer.apply(
                session,
                source=SOURCE,
                observation=observation,
                candidate=legacy_candidate,
                processor_name=GitHubRepoMapper.PROCESSOR_NAME,
                processor_version="2",
            )
        async with factory() as session, session.begin():
            repaired = await service.ingest(session, SOURCE, envelope)
        assert repaired.replay is True
        assert repaired.observation_id == observation.observation_id
        assert repaired.normalization.knowledge_revision > legacy.knowledge_revision

        async with factory() as session:
            relations = list(await session.scalars(select(RelationModel)))
            old_merge = next(item for item in relations if item.relation_type == "merged-as")
            assert old_merge.superseded_revision == repaired.normalization.knowledge_revision
            assert {
                item.relation_type for item in relations if item.superseded_revision is None
            } == {
                "belongs-to-repo",
                "head-commit",
            }
        async with factory() as session, session.begin():
            replay = await service.ingest(session, SOURCE, envelope)
        assert replay.normalization.knowledge_revision == repaired.normalization.knowledge_revision
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_github_development_objects_form_traceable_relation_graph() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    service = StructuredIndexService(
        EvidenceIngress(MemoryArtifactStore(), now=lambda: NOW),
        EvidenceBackedKnowledgeWriter(now=lambda: NOW),
        {"github_repo": GitHubRepoMapper()},
    )
    objects = [
        ("issue-run", "issue", _fixture("github_issue"), "vllm-project/vllm#issue-8421"),
        ("pr-run", "pull_request", _fixture("github_pull_request"), "vllm-project/vllm#pull-9123"),
        (
            "commit-run",
            "commit",
            _fixture("github_commit"),
            "vllm-project/vllm@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        ),
        ("release-run", "release", _fixture("github_release"), "vllm-project/vllm@release-101001"),
    ]
    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, [SOURCE])
            for run_id, _, _, _ in objects:
                session.add(
                    AcquisitionRunModel(
                        run_id=run_id,
                        source_id=SOURCE.source_id,
                        trigger="on_demand",
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

        for run_id, object_type, payload, external_id in objects:
            async with factory() as session, session.begin():
                await service.ingest(
                    session, SOURCE, _envelope(run_id, object_type, payload, external_id)
                )

        async with factory() as session:
            rows = list(await session.scalars(select(ObjectModel)))
            by_key = {row.canonical_key: row for row in rows}
            assert "github:vllm-project/vllm:issue:8421" in by_key
            assert "github:vllm-project/vllm:pull:9123" in by_key
            assert "git:commit:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" in by_key
            assert "github:vllm-project/vllm:release:101001" in by_key
            assert "github:vllm-project/vllm" in by_key
            assert "git:commit:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" in by_key
            assert "git:commit:cccccccccccccccccccccccccccccccccccccccc" in by_key

            relations = list(
                await session.scalars(
                    select(RelationModel).where(RelationModel.superseded_revision.is_(None))
                )
            )
            relation_types = {item.relation_type for item in relations}
            assert {
                "belongs-to-repo",
                "merged-as",
                "head-commit",
                "has-parent-commit",
            } <= relation_types

            pr = by_key["github:vllm-project/vllm:pull:9123"]
            merged = next(
                item
                for item in relations
                if item.source_object_id == pr.object_id and item.relation_type == "merged-as"
            )
            assert (
                merged.target_object_id
                == by_key["git:commit:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"].object_id
            )

            evidence_links = list(await session.scalars(select(EvidenceLinkModel)))
            relation_ids = {item.relation_id for item in relations}
            linked_relation_ids = {
                item.target_id for item in evidence_links if item.target_kind == "relation"
            }
            assert relation_ids <= linked_relation_ids

            view = await get_object_by_identifier(
                session, "github_pull_request", "vllm-project/vllm#9123"
            )
            assert view is not None
            assert view.object_type == "PullRequest"
            relation_by_type = {item.relation_type: item for item in view.relations}
            assert relation_by_type["merged-as"].target.external_identifiers["git_commit_sha"] == [
                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            ]
            assert relation_by_type["merged-as"].evidence[0].source_id == SOURCE.source_id
            assert relation_by_type["merged-as"].evidence[0].external_object_id == (
                "vllm-project/vllm#pull-9123"
            )
            assert relation_by_type["merged-as"].evidence[0].locator["path"] == (
                "$.merge_commit_sha"
            )

        async with factory() as session, session.begin():
            repo = await session.scalar(
                select(ObjectModel).where(ObjectModel.canonical_key == "github:vllm-project/vllm")
            )
            assert repo is not None
            result = await CurrentProjectionService(now=lambda: NOW).rebuild_knowledge_object_views(
                session, object_id=repo.object_id, upstream_revision=4
            )
            assert [item.projection_type for item in result] == ["current_repo_security_state"]

        async with factory() as session:
            projection = await get_current_projection(
                session,
                projection_type="current_repo_security_state",
                projection_key="github:vllm-project/vllm",
            )
            assert projection is not None
            counts = projection.data["development_object_counts"]
            assert counts == {"Commit": 1, "Issue": 1, "PullRequest": 1, "Release": 1}
    finally:
        await engine.dispose()
