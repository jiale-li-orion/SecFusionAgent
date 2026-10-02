from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.evaluation_runtime import ensure_benchmark_deployment_revision
from apps.runtime_models import register_runtime_models
from packages.evaluation.benchmark import (
    BenchmarkCase,
    BenchmarkCaseRunStatus,
    BenchmarkDomain,
    BenchmarkExecutionMode,
    BenchmarkRunStatus,
    BenchmarkStore,
    BenchmarkSuite,
    MeasurementSource,
    MetricDirection,
)
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.storage.evidence_models import EvidenceArtifactModel
from packages.intelligence.storage.factory import create_artifact_store
from packages.monitoring.run_service import recover_stale_acquisition_runs
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.shared.outbox.service import dispatch_pending_events
from packages.shared.storage.models import OutboxEventModel
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope
from packages.sources.registry.loader import load_source_definitions
from packages.sources.storage.models import SourceModel


class FaultCaseDefinition(BaseModel):
    case_id: str
    mechanism: str
    expected_behavior: dict[str, JsonValue]


class FaultProbeResult(BaseModel):
    case_id: str
    mechanism: str
    success: bool
    failure_isolation: bool | None = None
    retry_correctness: bool | None = None
    bounded_termination: bool | None = None
    diagnostics: dict[str, JsonValue] = Field(default_factory=dict)


FAULT_CASES = (
    FaultCaseDefinition(
        case_id="engineering-stale-acquisition-requeue",
        mechanism="stale acquisition run -> queued + collection.requested outbox",
        expected_behavior={
            "run_status": "queued",
            "started_at": None,
            "outbox_topic": "collection.requested",
        },
    ),
    FaultCaseDefinition(
        case_id="engineering-outbox-fail-once-retry",
        mechanism="publisher failure -> pending retry -> delivered",
        expected_behavior={
            "first_status": "pending",
            "first_attempts": 1,
            "second_status": "delivered",
            "second_attempts": 2,
        },
    ),
    FaultCaseDefinition(
        case_id="engineering-legacy-artifact-replay-recovery",
        mechanism="legacy s3:// Evidence URI + missing blob -> filesystem exact replay recovery",
        expected_behavior={
            "evidence_metadata_uri_immutable": True,
            "legacy_uri_readable_after_recovery": True,
            "recovered_content_hash_exact": True,
        },
    ),
)


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode()
    ).hexdigest()


async def _probe_stale_acquisition_requeue(
    factory: async_sessionmaker[AsyncSession],
    *,
    now: datetime,
) -> FaultProbeResult:
    run_id = f"fr-{uuid4().hex}"
    control_run_id = f"fc-{uuid4().hex}"
    async with factory() as session, session.begin():
        nested = await session.begin_nested()
        try:
            source = await session.get(SourceModel, "nvd-cves-2")
            if source is None:
                raise LookupError("nvd-cves-2 source is not synchronized")
            session.add(
                AcquisitionRunModel(
                    run_id=run_id,
                    source_id=source.source_id,
                    trigger="scheduled",
                    parent_run_id=None,
                    query_spec={},
                    status="running",
                    cursor_in={},
                    cursor_out={},
                    attempt=1,
                    created_at=now - timedelta(minutes=30),
                    started_at=now - timedelta(minutes=20),
                )
            )
            session.add(
                AcquisitionRunModel(
                    run_id=control_run_id,
                    source_id=source.source_id,
                    trigger="scheduled",
                    parent_run_id=None,
                    query_spec={},
                    status="running",
                    cursor_in={},
                    cursor_out={},
                    attempt=1,
                    created_at=now - timedelta(minutes=30),
                    started_at=now - timedelta(minutes=20),
                )
            )
            await session.flush()
            recovered = await recover_stale_acquisition_runs(
                session,
                now=now,
                timeout_seconds=15 * 60,
                run_ids={run_id},
            )
            await session.flush()
            run = await session.get(AcquisitionRunModel, run_id)
            control = await session.get(AcquisitionRunModel, control_run_id)
            events = list(
                await session.scalars(
                    select(OutboxEventModel).where(OutboxEventModel.aggregate_id == run_id)
                )
            )
            control_events = list(
                await session.scalars(
                    select(OutboxEventModel).where(OutboxEventModel.aggregate_id == control_run_id)
                )
            )
            isolation_ok = (
                control is not None
                and control.status == "running"
                and control.started_at is not None
                and not control_events
            )
            success = (
                recovered == [run_id]
                and run is not None
                and run.status == "queued"
                and run.started_at is None
                and len(events) == 1
                and events[0].topic == "collection.requested"
                and events[0].status == "pending"
                and isolation_ok
            )
            return FaultProbeResult(
                case_id=FAULT_CASES[0].case_id,
                mechanism=FAULT_CASES[0].mechanism,
                success=success,
                failure_isolation=isolation_ok,
                bounded_termination=(run is not None and run.status == "queued"),
                diagnostics={
                    "recovered_count": len(recovered),
                    "run_status": run.status if run is not None else "missing",
                    "outbox_count": len(events),
                    "control_run_status": control.status if control is not None else "missing",
                    "control_outbox_count": len(control_events),
                },
            )
        finally:
            await nested.rollback()


async def _probe_legacy_artifact_replay_recovery(
    factory: async_sessionmaker[AsyncSession],
    *,
    now: datetime,
) -> FaultProbeResult:
    settings = get_settings()
    if settings.artifact_store_backend != "filesystem":
        return FaultProbeResult(
            case_id=FAULT_CASES[2].case_id,
            mechanism=FAULT_CASES[2].mechanism,
            success=False,
            diagnostics={"error": "case requires filesystem artifact backend"},
        )
    definitions = {item.source_id: item for item in load_source_definitions(Path("config/sources"))}
    source = definitions.get("nvd-cves-2")
    if source is None:
        raise LookupError("nvd-cves-2 source definition is missing")
    run_id = f"fr-{uuid4().hex}"
    body = f"secfusion-artifact-replay-{uuid4().hex}".encode()
    envelope = IngestEnvelope.for_binary_payload(
        acquisition_run_id=run_id,
        trigger=AcquisitionTrigger.REPLAY,
        source_id=source.source_id,
        external_object_id=f"fault-probe:{run_id}",
        body=body,
        media_type="application/octet-stream",
        canonical_url="https://benchmark.invalid/artifact-replay",
        published_at=now,
        updated_at=now,
        external_revision="fault-replay-v1",
        observed_at=now,
    )
    content_hash = envelope.content_hash
    key = f"sha256/{content_hash[:2]}/{content_hash}"
    legacy_uri = f"s3://{settings.s3_bucket}/{key}"
    physical_path = settings.artifact_root / settings.s3_bucket / key
    artifact_store = create_artifact_store(settings)
    await artifact_store.ensure_bucket()
    try:
        async with factory() as session, session.begin():
            nested = await session.begin_nested()
            try:
                persisted_source = await session.get(SourceModel, source.source_id)
                if persisted_source is None:
                    raise LookupError("nvd-cves-2 source is not synchronized")
                session.add(
                    AcquisitionRunModel(
                        run_id=run_id,
                        source_id=source.source_id,
                        trigger="replay",
                        parent_run_id=None,
                        query_spec={},
                        status="running",
                        cursor_in={},
                        cursor_out={},
                        attempt=1,
                        created_at=now,
                        started_at=now,
                    )
                )
                await session.flush()
                ingress = EvidenceIngress(artifact_store, now=lambda: now)
                first = await ingress.accept(session, source, envelope)
                artifact = await session.get(EvidenceArtifactModel, first.artifact_id)
                if artifact is None:
                    raise RuntimeError("fault probe EvidenceArtifact was not persisted")
                artifact.storage_uri = legacy_uri
                await session.flush()
                physical_path.unlink(missing_ok=True)
                missing_before = not await artifact_store.exists(legacy_uri)

                replay = await ingress.accept(session, source, envelope)
                restored = await session.get(EvidenceArtifactModel, first.artifact_id)
                readable = await artifact_store.exists(legacy_uri)
                restored_body = await artifact_store.get(legacy_uri) if readable else b""
                immutable_uri = restored is not None and restored.storage_uri == legacy_uri
                exact_hash = sha256(restored_body).hexdigest() == content_hash
                success = (
                    first.replay is False
                    and replay.replay is True
                    and missing_before
                    and immutable_uri
                    and readable
                    and exact_hash
                )
                return FaultProbeResult(
                    case_id=FAULT_CASES[2].case_id,
                    mechanism=FAULT_CASES[2].mechanism,
                    success=success,
                    failure_isolation=True,
                    retry_correctness=True,
                    bounded_termination=success,
                    diagnostics={
                        "missing_before_replay": missing_before,
                        "legacy_uri_immutable": immutable_uri,
                        "legacy_uri_readable": readable,
                        "content_hash_exact": exact_hash,
                    },
                )
            finally:
                await nested.rollback()
    finally:
        physical_path.unlink(missing_ok=True)


async def _probe_outbox_retry(
    factory: async_sessionmaker[AsyncSession],
    *,
    now: datetime,
) -> FaultProbeResult:
    event_id = f"fr-{uuid4().hex}"
    published: list[str] = []

    async def fail_once(topic: str, payload: dict[str, object]) -> None:
        del topic, payload
        raise RuntimeError("injected publisher failure")

    async def succeed(topic: str, payload: dict[str, object]) -> None:
        del payload
        published.append(topic)

    async with factory() as session, session.begin():
        nested = await session.begin_nested()
        try:
            session.add(
                OutboxEventModel(
                    event_id=event_id,
                    topic="benchmark.fault_probe",
                    aggregate_id=event_id,
                    payload={"event_id": event_id},
                    status="pending",
                    attempts=0,
                    available_at=now,
                )
            )
            await session.flush()
            first_delivered = await dispatch_pending_events(
                session,
                fail_once,
                now=now,
                event_ids={event_id},
            )
            await session.flush()
            first = await session.get(OutboxEventModel, event_id)
            first_ok = (
                first_delivered == 0
                and first is not None
                and first.status == "pending"
                and first.attempts == 1
                and first.last_error == "RuntimeError: injected publisher failure"
            )
            second_delivered = await dispatch_pending_events(
                session,
                succeed,
                now=now + timedelta(seconds=1),
                event_ids={event_id},
            )
            await session.flush()
            second = await session.get(OutboxEventModel, event_id)
            second_ok = (
                second_delivered == 1
                and second is not None
                and second.status == "delivered"
                and second.attempts == 2
                and second.last_error is None
                and second.delivered_at is not None
                and published == ["benchmark.fault_probe"]
            )
            return FaultProbeResult(
                case_id=FAULT_CASES[1].case_id,
                mechanism=FAULT_CASES[1].mechanism,
                success=first_ok and second_ok,
                failure_isolation=(published == ["benchmark.fault_probe"]),
                retry_correctness=first_ok and second_ok,
                bounded_termination=(
                    second is not None and second.status == "delivered" and second.attempts == 2
                ),
                diagnostics={
                    "first_delivered": first_delivered,
                    "first_pending": first_ok,
                    "second_delivered": second_delivered,
                    "second_delivered_state": second_ok,
                },
            )
        finally:
            await nested.rollback()


async def _safe_probe(
    case: FaultCaseDefinition,
    probe: Callable[[], Awaitable[FaultProbeResult]],
) -> FaultProbeResult:
    try:
        return await probe()
    except Exception as exc:
        return FaultProbeResult(
            case_id=case.case_id,
            mechanism=case.mechanism,
            success=False,
            diagnostics={
                "error_type": type(exc).__name__,
                "error": str(exc)[:500],
            },
        )


async def _run(
    *,
    suite_revision: int,
    deployment_revision_id: str | None,
) -> dict[str, Any]:
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    store = BenchmarkStore()
    now = datetime.now(UTC)
    try:
        results = [
            await _safe_probe(
                FAULT_CASES[0],
                lambda: _probe_stale_acquisition_requeue(factory, now=now),
            ),
            await _safe_probe(
                FAULT_CASES[1],
                lambda: _probe_outbox_retry(factory, now=now),
            ),
            await _safe_probe(
                FAULT_CASES[2],
                lambda: _probe_legacy_artifact_replay_recovery(factory, now=now),
            ),
        ]
        gold_revision = "fault-recovery:" + _digest(
            [item.model_dump(mode="json") for item in FAULT_CASES]
        )
        suite_id = "engineering-fault-recovery"
        case_refs = [f"{item.case_id}@{suite_revision}" for item in FAULT_CASES]
        async with factory() as session, session.begin():
            resolved_deployment_id = await ensure_benchmark_deployment_revision(
                session,
                settings,
                deployment_revision_id=deployment_revision_id,
            )
            for case in FAULT_CASES:
                await store.register_case(
                    session,
                    BenchmarkCase(
                        case_id=case.case_id,
                        case_revision=suite_revision,
                        input={"fault_injection": case.mechanism},
                        execution_profile="controlled_database_fault_injection",
                        target_refs=["postgresql-runtime-state"],
                        expected_behavior=case.expected_behavior,
                        gold_ref=f"{gold_revision}#{case.case_id}",
                        tags=["engineering", "fault-recovery", "controlled"],
                        latency_class="offline",
                        replay_tier="R0",
                        created_at=now,
                    ),
                )
            await store.register_suite(
                session,
                BenchmarkSuite(
                    suite_id=suite_id,
                    suite_revision=suite_revision,
                    domain=BenchmarkDomain.SECURITY,
                    purpose="Controlled infrastructure fault/recovery state-transition checks",
                    case_refs=case_refs,
                    gold_revision=gold_revision,
                    evaluator_revision="engineering-fault-recovery-v1",
                    scoring_profile={
                        "metrics": [
                            "engineering.fault_recovery_success",
                            "engineering.failure_isolation",
                            "engineering.retry_correctness",
                            "engineering.bounded_termination",
                        ],
                        "injected_rows_are_savepoint_rolled_back": True,
                        "case_count": len(FAULT_CASES),
                    },
                    created_at=now,
                ),
            )
            run = await store.start_run(
                session,
                suite_ref=f"{suite_id}@{suite_revision}",
                deployment_revision_id=resolved_deployment_id,
                execution_mode=BenchmarkExecutionMode.LIVE_CONTROLLED,
                environment=settings.environment,
                now=now,
            )

        by_id = {item.case_id: item for item in results}
        for case in FAULT_CASES:
            result = by_id[case.case_id]
            async with factory() as session, session.begin():
                case_run = await store.start_case_run(
                    session,
                    benchmark_run_id=run.benchmark_run_id,
                    case_ref=f"{case.case_id}@{suite_revision}",
                    now=now,
                )
                diagnostic_metrics = (
                    ("engineering.failure_isolation", result.failure_isolation),
                    ("engineering.retry_correctness", result.retry_correctness),
                    ("engineering.bounded_termination", result.bounded_termination),
                )
                for metric_name, verdict in diagnostic_metrics:
                    if verdict is None:
                        continue
                    await store.observe_metric(
                        session,
                        case_run_id=case_run.case_run_id,
                        metric_name=metric_name,
                        value=1.0 if verdict else 0.0,
                        direction=MetricDirection.HIGHER_IS_BETTER,
                        measurement_source=MeasurementSource.EXACT,
                        subject_ref=f"fault-case:{case.case_id}",
                        metadata=result.diagnostics,
                        now=now,
                    )
                await store.observe_metric(
                    session,
                    case_run_id=case_run.case_run_id,
                    metric_name="engineering.fault_recovery_success",
                    value=1.0 if result.success else 0.0,
                    direction=MetricDirection.HIGHER_IS_BETTER,
                    measurement_source=MeasurementSource.EXACT,
                    subject_ref=f"fault-case:{case.case_id}",
                    metadata=result.diagnostics,
                    now=now,
                )
                await store.finish_case_run(
                    session,
                    case_run.case_run_id,
                    status=BenchmarkCaseRunStatus.PASSED,
                    now=now,
                )
        async with factory() as session, session.begin():
            await store.finish_run(
                session,
                run.benchmark_run_id,
                status=BenchmarkRunStatus.COMPLETED,
                now=now,
            )
        return {
            "benchmark_run_id": run.benchmark_run_id,
            "deployment_revision_id": resolved_deployment_id,
            "suite_ref": f"{suite_id}@{suite_revision}",
            "gold_revision": gold_revision,
            "execution_mode": BenchmarkExecutionMode.LIVE_CONTROLLED.value,
            "success_rate": sum(item.success for item in results) / len(results),
            "cases": [item.model_dump(mode="json") for item in results],
        }
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run controlled engineering fault/recovery cases")
    parser.add_argument("--suite-revision", type=int, required=True)
    parser.add_argument("--deployment-revision-id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = asyncio.run(
        _run(
            suite_revision=args.suite_revision,
            deployment_revision_id=args.deployment_revision_id,
        )
    )
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
