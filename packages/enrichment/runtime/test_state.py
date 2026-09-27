from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.enrichment.runtime.state import (
    EnrichmentAttempt,
    EnrichmentAttemptStatus,
    EnrichmentSemanticOutcome,
    EnrichmentStateBuilder,
    EnrichmentStatus,
    record_enrichment_attempt,
)
from packages.enrichment.runtime.state_models import EnrichmentDimensionStateModel
from packages.intelligence.knowledge.vocabulary import (
    VOCABULARY_REVISION,
    EnrichmentDimension,
)
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    ExternalIdentifierModel,
    KnowledgeRevisionModel,
    ObjectModel,
    RelationModel,
)
from packages.shared.db import Base

NOW = datetime(2026, 9, 27, 2, 0, tzinfo=UTC)


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed_vulnerability(session, *, key: str = "cve:CVE-2026-42424") -> tuple[str, int]:
    revision = KnowledgeRevisionModel(committed_at=NOW)
    session.add(revision)
    await session.flush()
    object_id = str(uuid4())
    session.add(
        ObjectModel(
            object_id=object_id,
            object_type="Vulnerability",
            canonical_key=key,
            properties={"display_name": key.split(":", 1)[-1]},
            created_revision=revision.revision,
        )
    )
    session.add(
        ExternalIdentifierModel(
            external_identifier_id=str(uuid4()),
            namespace="cve",
            value=key.split(":", 1)[-1],
            object_id=object_id,
        )
    )
    await session.flush()
    return object_id, revision.revision


def _canonical_qualifier(**extra: object) -> dict[str, object]:
    return {
        "vocabulary_revision": VOCABULARY_REVISION,
        "vocabulary_scope": "canonical",
        **extra,
    }


@pytest.mark.asyncio
async def test_requirement_registry_is_derived_from_enrichment_v1_dimensions() -> None:
    requirements = EnrichmentStateBuilder().requirements_for("Vulnerability")
    assert [item.dimension for item in requirements] == list(EnrichmentDimension)
    by_dimension = {item.dimension: item for item in requirements}
    assert "cvss_score" in by_dimension[EnrichmentDimension.SEVERITY].canonical_terms
    assert "has-weakness" in by_dimension[EnrichmentDimension.WEAKNESS].canonical_terms
    assert (
        "asset-potentially-affected"
        in by_dimension[EnrichmentDimension.ASSET_EXPOSURE].canonical_terms
    )
    assert (
        "discusses-vulnerability"
        in by_dimension[EnrichmentDimension.RESEARCH_PAPER].canonical_terms
    )


@pytest.mark.asyncio
async def test_source_specific_fact_does_not_resolve_canonical_dimension() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            object_id, revision = await _seed_vulnerability(session)
            session.add(
                ClaimModel(
                    claim_id=str(uuid4()),
                    subject_id=object_id,
                    predicate="github_cwes",
                    value=["CWE-79"],
                    qualifier={
                        "source_id": "github-global-advisories",
                        "vocabulary_revision": VOCABULARY_REVISION,
                        "vocabulary_scope": "source_specific",
                    },
                    origin="source_asserted",
                    lifecycle="accepted",
                    processing_run_id=None,
                    created_revision=revision,
                )
            )
        async with factory() as session, session.begin():
            state = await EnrichmentStateBuilder().build(session, object_id, now=NOW)
        weakness = state.by_dimension()[EnrichmentDimension.WEAKNESS]
        assert weakness.status is EnrichmentStatus.MISSING
        assert weakness.accepted_fact_refs == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_disjoint_applicability_scopes_do_not_conflict() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            object_id, revision = await _seed_vulnerability(session)
            package_id = str(uuid4())
            session.add(
                ObjectModel(
                    object_id=package_id,
                    object_type="Package",
                    canonical_key="package:generic:example",
                    properties={"name": "example"},
                    created_revision=revision,
                )
            )
            for state_value, version in (("affected", "1.0"), ("unaffected", "2.0")):
                session.add(
                    RelationModel(
                        relation_id=str(uuid4()),
                        source_object_id=object_id,
                        relation_type="applicability-status",
                        target_object_id=package_id,
                        qualifier=_canonical_qualifier(
                            source_id="cve-program-cvelist-v5",
                            state=state_value,
                            source_semantics="cve5_version_rule",
                            version_rule={"version": version},
                        ),
                        origin="deterministic_derived",
                        lifecycle="accepted",
                        processing_run_id=None,
                        created_revision=revision,
                    )
                )
        async with factory() as session, session.begin():
            state = await EnrichmentStateBuilder().build(session, object_id, now=NOW)
        applicability = state.by_dimension()[EnrichmentDimension.VERSION_APPLICABILITY]
        assert applicability.status is EnrichmentStatus.RESOLVED
        assert len(applicability.accepted_fact_refs) == 2
        assert applicability.conflict_refs == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_complementary_multi_target_relations_resolve_without_false_conflict() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            object_id, revision = await _seed_vulnerability(session)
            for name in ("vllm", "transformers"):
                target_id = str(uuid4())
                session.add(
                    ObjectModel(
                        object_id=target_id,
                        object_type="Package",
                        canonical_key=f"package:pypi:{name}",
                        properties={"name": name},
                        created_revision=revision,
                    )
                )
                session.add(
                    RelationModel(
                        relation_id=str(uuid4()),
                        source_object_id=object_id,
                        relation_type="affects-package",
                        target_object_id=target_id,
                        qualifier=_canonical_qualifier(source_id="osv-vulnerabilities"),
                        origin="source_asserted",
                        lifecycle="accepted",
                        processing_run_id=None,
                        created_revision=revision,
                    )
                )
        async with factory() as session, session.begin():
            state = await EnrichmentStateBuilder().build(session, object_id, now=NOW)
        product = state.by_dimension()[EnrichmentDimension.PRODUCT_PACKAGE]
        assert product.status is EnrichmentStatus.RESOLVED
        assert len(product.accepted_fact_refs) == 2
        assert product.conflict_refs == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_same_canonical_claim_with_incompatible_values_is_conflict() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            object_id, revision = await _seed_vulnerability(session)
            for source_id, value in (("nvd-cves-2", 9.8), ("vendor-advisory", 8.1)):
                session.add(
                    ClaimModel(
                        claim_id=str(uuid4()),
                        subject_id=object_id,
                        predicate="cvss_score",
                        value=value,
                        qualifier=_canonical_qualifier(source_id=source_id),
                        origin="source_asserted",
                        lifecycle="accepted",
                        processing_run_id=None,
                        created_revision=revision,
                    )
                )
        async with factory() as session, session.begin():
            state = await EnrichmentStateBuilder().build(session, object_id, now=NOW)
        severity = state.by_dimension()[EnrichmentDimension.SEVERITY]
        assert severity.status is EnrichmentStatus.CONFLICT
        assert len(severity.conflict_refs) == 2
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_applicability_unknown_conflict_and_resolution_are_distinct() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            object_id, revision = await _seed_vulnerability(session)
            package_id = str(uuid4())
            session.add(
                ObjectModel(
                    object_id=package_id,
                    object_type="Package",
                    canonical_key="package:pypi:vllm",
                    properties={"name": "vllm"},
                    created_revision=revision,
                )
            )
            unknown_id = str(uuid4())
            session.add(
                RelationModel(
                    relation_id=unknown_id,
                    source_object_id=object_id,
                    relation_type="applicability-status",
                    target_object_id=package_id,
                    qualifier=_canonical_qualifier(
                        source_id="osv-vulnerabilities",
                        state="unknown",
                        source_semantics="osv_range",
                    ),
                    origin="deterministic_derived",
                    lifecycle="accepted",
                    processing_run_id=None,
                    created_revision=revision,
                )
            )
        async with factory() as session, session.begin():
            unknown_state = await EnrichmentStateBuilder().build(session, object_id, now=NOW)
        applicability = unknown_state.by_dimension()[EnrichmentDimension.VERSION_APPLICABILITY]
        assert applicability.status is EnrichmentStatus.UNKNOWN
        assert applicability.accepted_fact_refs == []

        async with factory() as session, session.begin():
            current = await session.get(RelationModel, unknown_id)
            assert current is not None
            current.superseded_revision = revision
            for source_id, state_value in (("osv", "affected"), ("vendor", "fixed")):
                session.add(
                    RelationModel(
                        relation_id=str(uuid4()),
                        source_object_id=object_id,
                        relation_type="applicability-status",
                        target_object_id=package_id,
                        qualifier=_canonical_qualifier(
                            source_id=source_id,
                            state=state_value,
                            source_semantics="test",
                        ),
                        origin="deterministic_derived",
                        lifecycle="accepted",
                        processing_run_id=None,
                        created_revision=revision,
                    )
                )
        async with factory() as session, session.begin():
            conflict_state = await EnrichmentStateBuilder().build(session, object_id, now=NOW)
        applicability = conflict_state.by_dimension()[EnrichmentDimension.VERSION_APPLICABILITY]
        assert applicability.status is EnrichmentStatus.CONFLICT
        assert len(applicability.conflict_refs) == 2
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_unknown_attempt_changes_semantic_state_but_blocked_attempt_does_not() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            object_id, revision = await _seed_vulnerability(session)
            builder = EnrichmentStateBuilder()
            requirement = next(
                item
                for item in builder.requirements_for("Vulnerability")
                if item.dimension is EnrichmentDimension.EXPLOIT_LIKELIHOOD
            )
            await record_enrichment_attempt(
                session,
                EnrichmentAttempt(
                    attempt_id=str(uuid4()),
                    target_object_id=object_id,
                    requirement_id=requirement.requirement_id,
                    dimension=requirement.dimension,
                    operator_id="epss.lookup",
                    execution_status=EnrichmentAttemptStatus.SUCCEEDED,
                    semantic_outcome=EnrichmentSemanticOutcome.UNKNOWN,
                    world_revision_before=revision,
                    world_revision_after=revision,
                    started_at=NOW,
                    finished_at=NOW,
                ),
            )
            weakness = next(
                item
                for item in builder.requirements_for("Vulnerability")
                if item.dimension is EnrichmentDimension.WEAKNESS
            )
            blocked_attempt_id = str(uuid4())
            await record_enrichment_attempt(
                session,
                EnrichmentAttempt(
                    attempt_id=blocked_attempt_id,
                    target_object_id=object_id,
                    requirement_id=weakness.requirement_id,
                    dimension=weakness.dimension,
                    operator_id="cwe.mapper",
                    execution_status=EnrichmentAttemptStatus.BLOCKED,
                    blocked_reason="provider_blocked",
                    world_revision_before=revision,
                    started_at=NOW,
                    finished_at=NOW,
                ),
            )
            state = await builder.build(session, object_id, now=NOW)
        by_dimension = state.by_dimension()
        assert (
            by_dimension[EnrichmentDimension.EXPLOIT_LIKELIHOOD].status is EnrichmentStatus.UNKNOWN
        )
        weakness_state = by_dimension[EnrichmentDimension.WEAKNESS]
        assert weakness_state.status is EnrichmentStatus.MISSING
        assert weakness_state.blocked_attempt_refs == [blocked_attempt_id]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_type", "relation_type", "dimension"),
    [
        ("Document", "discusses-vulnerability", EnrichmentDimension.RESEARCH_PAPER),
        ("InternetAsset", "asset-potentially-affected", EnrichmentDimension.ASSET_EXPOSURE),
        ("Document", "incident-exploits-vulnerability", EnrichmentDimension.INCIDENT_CONTEXT),
    ],
)
async def test_incoming_canonical_relation_resolves_target_dimension(
    source_type: str,
    relation_type: str,
    dimension: EnrichmentDimension,
) -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            object_id, revision = await _seed_vulnerability(session)
            source_id = str(uuid4())
            session.add(
                ObjectModel(
                    object_id=source_id,
                    object_type=source_type,
                    canonical_key=f"test:{source_type}:{uuid4()}",
                    properties={},
                    created_revision=revision,
                )
            )
            session.add(
                RelationModel(
                    relation_id=str(uuid4()),
                    source_object_id=source_id,
                    relation_type=relation_type,
                    target_object_id=object_id,
                    qualifier=_canonical_qualifier(source_id="test"),
                    origin="deterministic_derived",
                    lifecycle="accepted",
                    processing_run_id=None,
                    created_revision=revision,
                )
            )
        async with factory() as session, session.begin():
            state = await EnrichmentStateBuilder().build(session, object_id, now=NOW)
            rows = list(
                await session.scalars(
                    select(EnrichmentDimensionStateModel).where(
                        EnrichmentDimensionStateModel.target_object_id == object_id
                    )
                )
            )
        assert state.by_dimension()[dimension].status is EnrichmentStatus.RESOLVED
        assert len(rows) == len(EnrichmentDimension)
    finally:
        await engine.dispose()
