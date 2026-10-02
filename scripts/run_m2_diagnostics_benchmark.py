from __future__ import annotations

import argparse
import asyncio
import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, Field, JsonValue
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.evaluation_runtime import ensure_benchmark_deployment_revision
from apps.runtime_models import register_runtime_models
from packages.enrichment.runtime.state import EnrichmentStateBuilder, EnrichmentStatus
from packages.evaluation.benchmark import (
    BenchmarkCase,
    BenchmarkCaseRunStatus,
    BenchmarkDomain,
    BenchmarkExecutionMode,
    BenchmarkRunStatus,
    BenchmarkStore,
    BenchmarkSuite,
    MeasurementSource,
    metric_definition,
)
from packages.evaluation.m2_diagnostics import (
    ConflictPreservationCheck,
    EntityResolutionCheck,
    EvidenceCorrectnessCheck,
    M2DiagnosticScore,
    ParserFieldCheck,
    ReplaySuppressionCheck,
    score_m2_diagnostics,
)
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.knowledge.identity import vulnerability_cve_object_id
from packages.intelligence.knowledge.vocabulary import EnrichmentDimension
from packages.intelligence.normalization.nvd import NVDHotBugNormalizer
from packages.intelligence.normalization.nvd_durable import NVDCanonicalNormalizer
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.evidence_models import EvidenceArtifactModel, ObservationModel
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    EvidenceLinkModel,
    ExternalIdentifierModel,
    KnowledgeRevisionModel,
    RelationModel,
)
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.config import get_settings
from packages.shared.db import Base, create_engine, create_session_factory
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope, SourceDefinition
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

SUITE_ID = "m2-controlled-diagnostics-v1"
EVALUATOR_REVISION = "m2-diagnostics-v1"
FIXTURE_PATH = Path("tests/fixtures/nvd_cve_page.json")
NOW = datetime(2026, 10, 3, 0, 0, tzinfo=UTC)


class M2ProbeResult(BaseModel):
    case_id: str
    score: M2DiagnosticScore
    diagnostics: dict[str, JsonValue] = Field(default_factory=dict)


async def _isolated_factory() -> tuple[Any, async_sessionmaker[AsyncSession]]:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _nvd_source() -> SourceDefinition:
    return next(
        item
        for item in load_source_definitions(Path("config/sources"))
        if item.source_id == "nvd-cves-2"
    )


def _fixture() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(FIXTURE_PATH.read_text())["vulnerabilities"][0])


async def _seed_run(
    session: AsyncSession,
    *,
    source: SourceDefinition,
    run_id: str,
) -> None:
    session.add(
        AcquisitionRunModel(
            run_id=run_id,
            source_id=source.source_id,
            trigger="replay",
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


def _envelope(
    *,
    source: SourceDefinition,
    run_id: str,
    payload: dict[str, Any],
    revision: str,
) -> IngestEnvelope:
    cve_id = cast(str, payload["cve"]["id"])
    return IngestEnvelope.for_json_payload(
        acquisition_run_id=run_id,
        trigger=AcquisitionTrigger.REPLAY,
        source_id=source.source_id,
        external_object_id=cve_id,
        payload=payload,
        canonical_url=f"https://nvd.nist.gov/vuln/detail/{cve_id}",
        published_at=NOW,
        updated_at=NOW,
        external_revision=revision,
        observed_at=NOW,
    )


async def _probe_parser_evidence_replay() -> M2ProbeResult:
    engine, factory = await _isolated_factory()
    source = _nvd_source()
    store = MemoryArtifactStore()
    payload = _fixture()
    run_id = "m2-parser-replay"
    envelope = _envelope(
        source=source,
        run_id=run_id,
        payload=payload,
        revision="m2-parser-replay-v1",
    )
    ingress = EvidenceIngress(store, now=lambda: NOW)
    normalizer = NVDCanonicalNormalizer(now=lambda: NOW)
    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, [source])
            await _seed_run(session, source=source, run_id=run_id)
        async with factory() as session, session.begin():
            first = await ingress.accept(session, source, envelope)
            first_normalization = await normalizer.normalize(session, source, envelope, first)

        projection = NVDHotBugNormalizer().projection(envelope)
        expected_fields: dict[str, JsonValue] = {
            "status": "Analyzed",
            "cvss_score": 9.8,
            "cvss_version": "3.1",
            "cwes": ["CWE-306"],
        }
        expected_paths = {
            "status": "$.cve.vulnStatus",
            "cvss_score": "$.cve.metrics",
            "cvss_version": "$.cve.metrics",
            "cwes": "$.cve.weaknesses",
        }
        parser_checks: list[ParserFieldCheck] = []
        evidence_checks: list[EvidenceCorrectnessCheck] = []
        async with factory() as session:
            artifact_row = await session.get(EvidenceArtifactModel, first.artifact_id)
            artifact_readable = (
                artifact_row is not None and await store.exists(artifact_row.storage_uri)
            )
            claims = list(
                await session.scalars(
                    select(ClaimModel).where(
                        ClaimModel.subject_id == vulnerability_cve_object_id("CVE-2026-42424"),
                        ClaimModel.predicate.in_(list(expected_fields)),
                        ClaimModel.superseded_revision.is_(None),
                    )
                )
            )
            claim_by_predicate = {item.predicate: item for item in claims}
            for predicate, expected in expected_fields.items():
                claim = claim_by_predicate.get(predicate)
                link = None
                if claim is not None:
                    link = await session.scalar(
                        select(EvidenceLinkModel).where(
                            EvidenceLinkModel.target_kind == "claim",
                            EvidenceLinkModel.target_id == claim.claim_id,
                        )
                    )
                locator_ok = (
                    link is not None
                    and link.locator.get("kind") == "jsonpath"
                    and link.locator.get("path") == expected_paths[predicate]
                )
                parser_checks.append(
                    ParserFieldCheck(
                        check_id=f"nvd:{predicate}",
                        expected_value=expected,
                        predicted_value=projection.get(predicate),
                        locator_supports_value=locator_ok,
                    )
                )
                evidence_checks.append(
                    EvidenceCorrectnessCheck(
                        check_id=f"claim:{predicate}",
                        accepted_assertion=claim is not None and claim.lifecycle == "accepted",
                        evidence_supports_assertion=(
                            locator_ok
                            and link is not None
                            and link.observation_id == first.observation_id
                            and link.artifact_id == first.artifact_id
                            and artifact_readable
                        ),
                    )
                )

            relation = await session.scalar(
                select(RelationModel).where(
                    RelationModel.source_object_id
                    == vulnerability_cve_object_id("CVE-2026-42424"),
                    RelationModel.relation_type == "has-weakness",
                    RelationModel.superseded_revision.is_(None),
                )
            )
            relation_link = None
            if relation is not None:
                relation_link = await session.scalar(
                    select(EvidenceLinkModel).where(
                        EvidenceLinkModel.target_kind == "relation",
                        EvidenceLinkModel.target_id == relation.relation_id,
                    )
                )
            evidence_checks.append(
                EvidenceCorrectnessCheck(
                    check_id="relation:has-weakness",
                    accepted_assertion=relation is not None and relation.lifecycle == "accepted",
                    evidence_supports_assertion=(
                        relation_link is not None
                        and relation_link.observation_id == first.observation_id
                        and relation_link.artifact_id == first.artifact_id
                        and relation_link.locator.get("kind") == "jsonpath"
                    ),
                )
            )
            before_observations = int(
                await session.scalar(select(func.count()).select_from(ObservationModel)) or 0
            )
            before_revisions = int(
                await session.scalar(select(func.count()).select_from(KnowledgeRevisionModel)) or 0
            )

        async with factory() as session, session.begin():
            replay = await ingress.accept(session, source, envelope)
            replay_normalization = await normalizer.normalize(session, source, envelope, replay)
        async with factory() as session:
            after_observations = int(
                await session.scalar(select(func.count()).select_from(ObservationModel)) or 0
            )
            after_revisions = int(
                await session.scalar(select(func.count()).select_from(KnowledgeRevisionModel)) or 0
            )

        replay_checks = [
            ReplaySuppressionCheck(
                check_id="exact-envelope-replay",
                expected_suppressed=True,
                observed_suppressed=(
                    replay.replay
                    and replay_normalization.knowledge_revision
                    == first_normalization.knowledge_revision
                    and before_observations == after_observations == 1
                    and before_revisions == after_revisions == 1
                ),
            )
        ]
        score = score_m2_diagnostics(
            parser_fields=parser_checks,
            replay_checks=replay_checks,
            evidence_checks=evidence_checks,
        )
        return M2ProbeResult(
            case_id="m2-parser-evidence-replay",
            score=score,
            diagnostics={
                "parser_check_count": len(parser_checks),
                "evidence_check_count": len(evidence_checks),
                "first_observation_id": first.observation_id,
                "first_artifact_id": first.artifact_id,
                "knowledge_revision": first_normalization.knowledge_revision,
                "replay_observation_count": after_observations,
                "replay_knowledge_revision_count": after_revisions,
            },
        )
    finally:
        await engine.dispose()


async def _probe_entity_resolution() -> M2ProbeResult:
    engine, factory = await _isolated_factory()
    primary = _nvd_source()
    peer = primary.model_copy(update={"source_id": "m2-nvd-peer"})
    store = MemoryArtifactStore()
    ingress = EvidenceIngress(store, now=lambda: NOW)
    normalizer = NVDCanonicalNormalizer(now=lambda: NOW)
    same_payload = _fixture()
    other_payload = deepcopy(same_payload)
    other_payload["cve"]["id"] = "CVE-2026-42425"
    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, [primary, peer])
            await _seed_run(session, source=primary, run_id="m2-entity-primary")
            await _seed_run(session, source=peer, run_id="m2-entity-peer")
            await _seed_run(session, source=peer, run_id="m2-entity-other")

        for source, run_id, payload, revision in (
            (primary, "m2-entity-primary", same_payload, "entity-primary-v1"),
            (peer, "m2-entity-peer", same_payload, "entity-peer-v1"),
            (peer, "m2-entity-other", other_payload, "entity-other-v1"),
        ):
            envelope = _envelope(
                source=source,
                run_id=run_id,
                payload=payload,
                revision=revision,
            )
            async with factory() as session, session.begin():
                ack = await ingress.accept(session, source, envelope)
                await normalizer.normalize(session, source, envelope, ack)

        async with factory() as session:
            rows = list(
                await session.execute(
                    select(ExternalIdentifierModel.value, ExternalIdentifierModel.object_id).where(
                        ExternalIdentifierModel.namespace == "cve",
                        ExternalIdentifierModel.value.in_(
                            ["CVE-2026-42424", "CVE-2026-42425"]
                        ),
                    )
                )
            )
            object_by_cve = {value: object_id for value, object_id in rows}
            same_object = object_by_cve["CVE-2026-42424"]
            different_object = object_by_cve["CVE-2026-42425"]
            source_claims = int(
                await session.scalar(
                    select(func.count())
                    .select_from(ClaimModel)
                    .where(
                        ClaimModel.subject_id == same_object,
                        ClaimModel.predicate == "cvss_score",
                        ClaimModel.superseded_revision.is_(None),
                    )
                )
                or 0
            )
        checks = [
            EntityResolutionCheck(
                check_id="same-cve-cross-source",
                expected_same_entity=True,
                predicted_same_entity=(
                    same_object == vulnerability_cve_object_id("CVE-2026-42424")
                    and source_claims == 2
                ),
            ),
            EntityResolutionCheck(
                check_id="different-cve-separate-object",
                expected_same_entity=False,
                predicted_same_entity=(same_object == different_object),
            ),
        ]
        return M2ProbeResult(
            case_id="m2-entity-resolution",
            score=score_m2_diagnostics(entity_checks=checks),
            diagnostics={
                "same_cve_object_id": same_object,
                "different_cve_object_id": different_object,
                "active_same_cve_cvss_claims": source_claims,
            },
        )
    finally:
        await engine.dispose()


async def _probe_conflict_preservation() -> M2ProbeResult:
    engine, factory = await _isolated_factory()
    primary = _nvd_source()
    peer = primary.model_copy(update={"source_id": "m2-nvd-conflict"})
    store = MemoryArtifactStore()
    ingress = EvidenceIngress(store, now=lambda: NOW)
    normalizer = NVDCanonicalNormalizer(now=lambda: NOW)
    primary_payload = _fixture()
    conflict_payload = deepcopy(primary_payload)
    metric = conflict_payload["cve"]["metrics"]["cvssMetricV31"][0]["cvssData"]
    metric["baseScore"] = 8.1
    metric["baseSeverity"] = "HIGH"
    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, [primary, peer])
            await _seed_run(session, source=primary, run_id="m2-conflict-primary")
            await _seed_run(session, source=peer, run_id="m2-conflict-peer")
        for source, run_id, payload, revision in (
            (primary, "m2-conflict-primary", primary_payload, "conflict-primary-v1"),
            (peer, "m2-conflict-peer", conflict_payload, "conflict-peer-v1"),
        ):
            envelope = _envelope(
                source=source,
                run_id=run_id,
                payload=payload,
                revision=revision,
            )
            async with factory() as session, session.begin():
                ack = await ingress.accept(session, source, envelope)
                await normalizer.normalize(session, source, envelope, ack)
        object_id = vulnerability_cve_object_id("CVE-2026-42424")
        async with factory() as session, session.begin():
            snapshot = await EnrichmentStateBuilder().build(session, object_id, now=NOW)
        severity = snapshot.by_dimension()[EnrichmentDimension.SEVERITY]
        preserved = (
            severity.status is EnrichmentStatus.CONFLICT
            and len(severity.conflict_refs) >= 2
            and len(severity.accepted_fact_refs) >= 2
        )
        return M2ProbeResult(
            case_id="m2-conflict-preservation",
            score=score_m2_diagnostics(
                conflict_checks=[
                    ConflictPreservationCheck(
                        check_id="cvss-score-cross-source-conflict",
                        expected_conflict=True,
                        competing_assertions_preserved=preserved,
                    )
                ]
            ),
            diagnostics={
                "severity_status": severity.status.value,
                "accepted_fact_refs": cast(JsonValue, list(severity.accepted_fact_refs)),
                "conflict_refs": cast(JsonValue, list(severity.conflict_refs)),
            },
        )
    finally:
        await engine.dispose()


def _observed_metrics(result: M2ProbeResult) -> list[tuple[str, float]]:
    mapping = {
        "m2.parser_field_accuracy": result.score.parser_field_accuracy,
        "m2.replay_suppression_accuracy": result.score.replay_suppression_accuracy,
        "m2.entity_resolution_precision": result.score.entity_resolution_precision,
        "m2.entity_resolution_recall": result.score.entity_resolution_recall,
        "m2.evidence_correctness": result.score.evidence_correctness,
        "m2.conflict_preservation": result.score.conflict_preservation,
    }
    return [(name, value) for name, value in mapping.items() if value is not None]


async def _run(*, suite_revision: int, deployment_revision_id: str | None) -> dict[str, Any]:
    probes = [
        await _probe_parser_evidence_replay(),
        await _probe_entity_resolution(),
        await _probe_conflict_preservation(),
    ]
    now = datetime.now(UTC)
    settings = get_settings()
    register_runtime_models()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    store = BenchmarkStore()
    case_refs = [f"{item.case_id}@{suite_revision}" for item in probes]
    try:
        async with factory() as session, session.begin():
            deployment_id = await ensure_benchmark_deployment_revision(
                session,
                settings,
                deployment_revision_id=deployment_revision_id,
            )
            for item in probes:
                await store.register_case(
                    session,
                    BenchmarkCase(
                        case_id=item.case_id,
                        case_revision=suite_revision,
                        input={
                            "fixture": str(FIXTURE_PATH),
                            "control": item.case_id,
                        },
                        execution_profile="controlled_m2_diagnostics",
                        expected_behavior={"all_observed_metrics": 1.0},
                        gold_ref=f"m2-controlled-gold-v1#{item.case_id}",
                        tags=["m2", "controlled", "diagnostic", "deterministic"],
                        latency_class="controlled",
                        replay_tier="R0",
                        created_at=now,
                    ),
                )
            await store.register_suite(
                session,
                BenchmarkSuite(
                    suite_id=SUITE_ID,
                    suite_revision=suite_revision,
                    domain=BenchmarkDomain.M2_NORMALIZATION,
                    purpose=(
                        "Controlled M2 diagnostic regression for parser+locator, exact replay, "
                        "cross-source identity, Evidence correctness and conflict preservation"
                    ),
                    case_refs=case_refs,
                    gold_revision="m2-controlled-gold-v1",
                    evaluator_revision=EVALUATOR_REVISION,
                    scoring_profile={
                        "metrics": [
                            "m2.parser_field_accuracy",
                            "m2.replay_suppression_accuracy",
                            "m2.entity_resolution_precision",
                            "m2.entity_resolution_recall",
                            "m2.evidence_correctness",
                            "m2.conflict_preservation",
                        ],
                        "scope": "controlled_diagnostic_not_m3_competition_score",
                    },
                    created_at=now,
                ),
            )
            run = await store.start_run(
                session,
                suite_ref=f"{SUITE_ID}@{suite_revision}",
                deployment_revision_id=deployment_id,
                execution_mode=BenchmarkExecutionMode.LIVE_CONTROLLED,
                environment=settings.environment,
                model_config_ref="model:none-deterministic",
                now=now,
            )

        per_case: dict[str, Any] = {}
        for item in probes:
            observations = _observed_metrics(item)
            passed = bool(observations) and all(value == 1.0 for _, value in observations)
            async with factory() as session, session.begin():
                case_run = await store.start_case_run(
                    session,
                    benchmark_run_id=run.benchmark_run_id,
                    case_ref=f"{item.case_id}@{suite_revision}",
                    now=now,
                )
                for metric_name, value in observations:
                    definition = metric_definition(metric_name)
                    await store.observe_metric(
                        session,
                        case_run_id=case_run.case_run_id,
                        metric_name=metric_name,
                        value=value,
                        direction=definition.direction,
                        measurement_source=MeasurementSource.SCORER,
                        subject_ref=f"m2-case:{item.case_id}",
                        metadata=item.diagnostics,
                        now=now,
                    )
                await store.finish_case_run(
                    session,
                    case_run.case_run_id,
                    status=(
                        BenchmarkCaseRunStatus.PASSED
                        if passed
                        else BenchmarkCaseRunStatus.FAILED
                    ),
                    failure_class=None if passed else "m2_diagnostic_mismatch",
                    now=now,
                )
            per_case[item.case_id] = {
                "passed": passed,
                "metrics": {name: value for name, value in observations},
                "diagnostics": item.diagnostics,
            }

        run_passed = all(item["passed"] for item in per_case.values())
        async with factory() as session, session.begin():
            await store.finish_run(
                session,
                run.benchmark_run_id,
                status=(
                    BenchmarkRunStatus.COMPLETED if run_passed else BenchmarkRunStatus.FAILED
                ),
                now=now,
            )
        metric_values = {
            name: value
            for item in probes
            for name, value in _observed_metrics(item)
        }
        return {
            "schema_version": "m2-controlled-diagnostics-v1",
            "benchmark_run_id": run.benchmark_run_id,
            "deployment_revision_id": deployment_id,
            "suite_ref": f"{SUITE_ID}@{suite_revision}",
            "execution_mode": BenchmarkExecutionMode.LIVE_CONTROLLED.value,
            "scope": "controlled_diagnostic_not_m3_competition_score",
            "passed": run_passed,
            "metrics": metric_values,
            "cases": per_case,
        }
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run controlled M2 diagnostic benchmark")
    parser.add_argument("--suite-revision", type=int, required=True)
    parser.add_argument("--deployment-revision-id")
    parser.add_argument("--output", type=Path, default=Path("benchmarks/m2/current.json"))
    args = parser.parse_args()
    result = asyncio.run(
        _run(
            suite_revision=args.suite_revision,
            deployment_revision_id=args.deployment_revision_id,
        )
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
