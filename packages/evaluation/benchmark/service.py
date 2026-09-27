from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import cast
from uuid import NAMESPACE_URL, uuid4, uuid5

from pydantic import BaseModel, JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.evaluation.benchmark.contracts import (
    BenchmarkCase,
    BenchmarkCaseRun,
    BenchmarkCaseRunStatus,
    BenchmarkDomain,
    BenchmarkExecutionMode,
    BenchmarkRun,
    BenchmarkRunStatus,
    BenchmarkSuite,
    DeploymentRevision,
    MeasurementSource,
    MetricDirection,
    MetricObservation,
)
from packages.evaluation.benchmark.metrics import MetricDefinition, metric_definition
from packages.evaluation.benchmark.storage import (
    BenchmarkCaseModel,
    BenchmarkCaseRunModel,
    BenchmarkRunModel,
    BenchmarkSuiteModel,
    DeploymentRevisionModel,
    MetricDefinitionModel,
    MetricObservationModel,
)


class BenchmarkStore:
    async def register_deployment(
        self,
        session: AsyncSession,
        deployment: DeploymentRevision,
    ) -> DeploymentRevision:
        existing = await session.get(
            DeploymentRevisionModel,
            deployment.deployment_revision_id,
        )
        if existing is not None:
            current = _deployment_view(existing)
            _assert_same_identity(current, deployment, label="deployment revision")
            return current
        session.add(
            DeploymentRevisionModel(
                deployment_revision_id=deployment.deployment_revision_id,
                git_commit=deployment.git_commit,
                container_image_digest=deployment.container_image_digest,
                schema_revision=deployment.schema_revision,
                source_inventory_hash=deployment.source_inventory_hash,
                vocabulary_revision=deployment.vocabulary_revision,
                policy_revision=deployment.policy_revision,
                capability_registry_revision=deployment.capability_registry_revision,
                skill_registry_revision=deployment.skill_registry_revision,
                model_provider_revision=deployment.model_provider_revision,
                configuration_digest=deployment.configuration_digest,
                created_at=deployment.created_at,
            )
        )
        await session.flush()
        return deployment

    async def register_case(
        self,
        session: AsyncSession,
        case: BenchmarkCase,
    ) -> BenchmarkCase:
        version_id = _case_version_id(case.case_id, case.case_revision)
        existing = await session.get(BenchmarkCaseModel, version_id)
        content_hash = _content_hash(case, exclude={"created_at"})
        if existing is not None:
            if existing.content_hash != content_hash:
                raise ValueError("benchmark case revision is immutable")
            return _case_view(existing)
        session.add(
            BenchmarkCaseModel(
                case_version_id=version_id,
                case_id=case.case_id,
                case_revision=case.case_revision,
                input_json=cast(dict[str, object], dict(case.input)),
                execution_profile=case.execution_profile,
                target_refs_json=list(case.target_refs),
                world_snapshot_ref=case.world_snapshot_ref,
                fixture_refs_json=list(case.fixture_refs),
                expected_behavior_json=cast(dict[str, object], dict(case.expected_behavior)),
                gold_ref=case.gold_ref,
                tags_json=list(case.tags),
                latency_class=case.latency_class,
                replay_tier=case.replay_tier,
                content_hash=content_hash,
                created_at=case.created_at,
            )
        )
        await session.flush()
        return case

    async def register_suite(
        self,
        session: AsyncSession,
        suite: BenchmarkSuite,
    ) -> BenchmarkSuite:
        version_id = _suite_version_id(suite.suite_id, suite.suite_revision)
        existing = await session.get(BenchmarkSuiteModel, version_id)
        content_hash = _content_hash(suite, exclude={"created_at"})
        if existing is not None:
            if existing.content_hash != content_hash:
                raise ValueError("benchmark suite revision is immutable")
            return _suite_view(existing)
        if len(set(suite.case_refs)) != len(suite.case_refs):
            raise ValueError("benchmark suite case_refs must be unique")
        for case_ref in suite.case_refs:
            await _require_case_model(session, case_ref)
        session.add(
            BenchmarkSuiteModel(
                suite_version_id=version_id,
                suite_id=suite.suite_id,
                suite_revision=suite.suite_revision,
                domain=suite.domain.value,
                purpose=suite.purpose,
                case_refs_json=list(suite.case_refs),
                gold_revision=suite.gold_revision,
                evaluator_revision=suite.evaluator_revision,
                default_world_snapshot_ref=suite.default_world_snapshot_ref,
                scoring_profile_json=cast(dict[str, object], dict(suite.scoring_profile)),
                content_hash=content_hash,
                created_at=suite.created_at,
            )
        )
        await session.flush()
        return suite

    async def start_run(
        self,
        session: AsyncSession,
        *,
        suite_ref: str,
        deployment_revision_id: str,
        execution_mode: BenchmarkExecutionMode,
        environment: str,
        model_config_ref: str | None = None,
        world_snapshot_ref: str | None = None,
        warm_cold_condition: str | None = None,
        benchmark_run_id: str | None = None,
        now: datetime | None = None,
    ) -> BenchmarkRun:
        suite_model = await _require_suite_model(session, suite_ref)
        deployment = await session.get(DeploymentRevisionModel, deployment_revision_id)
        if deployment is None:
            raise LookupError(f"deployment revision not found: {deployment_revision_id}")
        resolved_id = benchmark_run_id or str(uuid4())
        if await session.get(BenchmarkRunModel, resolved_id) is not None:
            raise ValueError(f"benchmark run already exists: {resolved_id}")
        instant = now or datetime.now(UTC)
        model = BenchmarkRunModel(
            benchmark_run_id=resolved_id,
            suite_version_id=suite_model.suite_version_id,
            suite_ref=suite_ref,
            gold_revision=suite_model.gold_revision,
            deployment_revision_id=deployment_revision_id,
            model_config_ref=model_config_ref,
            world_snapshot_ref=world_snapshot_ref or suite_model.default_world_snapshot_ref,
            started_at=instant,
            finished_at=None,
            status=BenchmarkRunStatus.RUNNING.value,
            execution_mode=execution_mode.value,
            warm_cold_condition=warm_cold_condition,
            environment=environment,
        )
        session.add(model)
        await session.flush()
        return _run_view(model)

    async def start_case_run(
        self,
        session: AsyncSession,
        *,
        benchmark_run_id: str,
        case_ref: str,
        task_run_id: str | None = None,
        execution_id: str | None = None,
        case_run_id: str | None = None,
        now: datetime | None = None,
    ) -> BenchmarkCaseRun:
        run = await session.get(BenchmarkRunModel, benchmark_run_id)
        if run is None:
            raise LookupError(f"benchmark run not found: {benchmark_run_id}")
        if run.status != BenchmarkRunStatus.RUNNING.value:
            raise ValueError("benchmark case can only start on a running benchmark run")
        suite = await session.get(BenchmarkSuiteModel, run.suite_version_id)
        if suite is None:
            raise RuntimeError("benchmark run references missing suite")
        if case_ref not in suite.case_refs_json:
            raise ValueError("benchmark case is not part of the frozen suite")
        case_model = await _require_case_model(session, case_ref)
        resolved_id = case_run_id or str(uuid4())
        model = BenchmarkCaseRunModel(
            case_run_id=resolved_id,
            benchmark_run_id=benchmark_run_id,
            case_version_id=case_model.case_version_id,
            case_ref=case_ref,
            task_run_id=task_run_id,
            execution_id=execution_id,
            decision_ref=None,
            replay_checkpoint_ref=None,
            started_at=now or datetime.now(UTC),
            finished_at=None,
            status=BenchmarkCaseRunStatus.RUNNING.value,
            failure_class=None,
            artifact_refs_json=[],
        )
        session.add(model)
        await session.flush()
        return _case_run_view(model)

    async def observe_metric(
        self,
        session: AsyncSession,
        *,
        case_run_id: str,
        metric_name: str,
        value: float,
        direction: MetricDirection,
        measurement_source: MeasurementSource,
        unit: str | None = None,
        subject_ref: str | None = None,
        evidence_refs: list[str] | None = None,
        metadata: dict[str, JsonValue] | None = None,
        metric_observation_id: str | None = None,
        now: datetime | None = None,
    ) -> MetricObservation:
        case_run = await session.get(BenchmarkCaseRunModel, case_run_id)
        if case_run is None:
            raise LookupError(f"benchmark case run not found: {case_run_id}")
        if case_run.status != BenchmarkCaseRunStatus.RUNNING.value:
            raise ValueError("metrics can only be appended to a running benchmark case")
        definition = metric_definition(metric_name)
        if direction is not definition.direction:
            raise ValueError(
                f"metric direction mismatch for {metric_name}: "
                f"{direction.value} != {definition.direction.value}"
            )
        if unit is not None and definition.unit is not None and unit != definition.unit:
            raise ValueError(
                f"metric unit mismatch for {metric_name}: {unit!r} != {definition.unit!r}"
            )
        await _register_metric_definition(
            session,
            definition=definition,
            now=now or datetime.now(UTC),
        )
        observation = MetricObservation(
            metric_observation_id=metric_observation_id or str(uuid4()),
            metric_name=metric_name,
            metric_definition_revision=definition.revision,
            value=value,
            unit=unit or definition.unit,
            direction=direction,
            measurement_source=measurement_source,
            case_run_id=case_run_id,
            subject_ref=subject_ref,
            evidence_refs=evidence_refs or [],
            metadata=metadata or {},
            created_at=now or datetime.now(UTC),
        )
        session.add(
            MetricObservationModel(
                metric_observation_id=observation.metric_observation_id,
                metric_name=observation.metric_name,
                metric_definition_revision=observation.metric_definition_revision,
                value=observation.value,
                unit=observation.unit,
                direction=observation.direction.value,
                measurement_source=observation.measurement_source.value,
                case_run_id=observation.case_run_id,
                subject_ref=observation.subject_ref,
                evidence_refs_json=list(observation.evidence_refs),
                metadata_json=cast(dict[str, object], dict(observation.metadata)),
                created_at=observation.created_at,
            )
        )
        await session.flush()
        return observation

    async def finish_case_run(
        self,
        session: AsyncSession,
        case_run_id: str,
        *,
        status: BenchmarkCaseRunStatus,
        failure_class: str | None = None,
        decision_ref: str | None = None,
        replay_checkpoint_ref: str | None = None,
        artifact_refs: list[str] | None = None,
        now: datetime | None = None,
    ) -> BenchmarkCaseRun:
        if status is BenchmarkCaseRunStatus.RUNNING:
            raise ValueError("finish_case_run requires terminal status")
        model = await session.get(BenchmarkCaseRunModel, case_run_id)
        if model is None:
            raise LookupError(f"benchmark case run not found: {case_run_id}")
        if model.status != BenchmarkCaseRunStatus.RUNNING.value:
            raise ValueError("benchmark case run is already terminal")
        model.status = status.value
        model.failure_class = failure_class
        model.decision_ref = decision_ref
        model.replay_checkpoint_ref = replay_checkpoint_ref
        model.artifact_refs_json = list(artifact_refs or [])
        model.finished_at = now or datetime.now(UTC)
        await session.flush()
        return _case_run_view(model)

    async def finish_run(
        self,
        session: AsyncSession,
        benchmark_run_id: str,
        *,
        status: BenchmarkRunStatus,
        now: datetime | None = None,
    ) -> BenchmarkRun:
        if status is BenchmarkRunStatus.RUNNING:
            raise ValueError("finish_run requires terminal status")
        model = await session.get(BenchmarkRunModel, benchmark_run_id)
        if model is None:
            raise LookupError(f"benchmark run not found: {benchmark_run_id}")
        if model.status != BenchmarkRunStatus.RUNNING.value:
            raise ValueError("benchmark run is already terminal")
        active_case = await session.scalar(
            select(BenchmarkCaseRunModel.case_run_id).where(
                BenchmarkCaseRunModel.benchmark_run_id == benchmark_run_id,
                BenchmarkCaseRunModel.status == BenchmarkCaseRunStatus.RUNNING.value,
            )
        )
        if active_case is not None:
            raise ValueError("benchmark run cannot finish with active case runs")
        model.status = status.value
        model.finished_at = now or datetime.now(UTC)
        await session.flush()
        return _run_view(model)


async def _require_suite_model(session: AsyncSession, suite_ref: str) -> BenchmarkSuiteModel:
    suite_id, revision = _split_ref(suite_ref)
    model = await session.scalar(
        select(BenchmarkSuiteModel).where(
            BenchmarkSuiteModel.suite_id == suite_id,
            BenchmarkSuiteModel.suite_revision == revision,
        )
    )
    if model is None:
        raise LookupError(f"benchmark suite not found: {suite_ref}")
    return model


async def _require_case_model(session: AsyncSession, case_ref: str) -> BenchmarkCaseModel:
    case_id, revision = _split_ref(case_ref)
    model = await session.scalar(
        select(BenchmarkCaseModel).where(
            BenchmarkCaseModel.case_id == case_id,
            BenchmarkCaseModel.case_revision == revision,
        )
    )
    if model is None:
        raise LookupError(f"benchmark case not found: {case_ref}")
    return model


def _split_ref(value: str) -> tuple[str, int]:
    identity, separator, revision = value.rpartition("@")
    if not separator or not identity:
        raise ValueError(f"invalid versioned benchmark ref: {value}")
    try:
        parsed = int(revision)
    except ValueError as exc:
        raise ValueError(f"invalid versioned benchmark ref: {value}") from exc
    if parsed < 1:
        raise ValueError(f"invalid versioned benchmark ref: {value}")
    return identity, parsed


def _suite_version_id(suite_id: str, revision: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"secfusion:benchmark-suite:{suite_id}@{revision}"))


def _case_version_id(case_id: str, revision: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"secfusion:benchmark-case:{case_id}@{revision}"))


def _content_hash(model: BaseModel, *, exclude: set[str]) -> str:
    payload = model.model_dump(mode="json", exclude=exclude)
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _assert_same_identity(current: BaseModel, incoming: BaseModel, *, label: str) -> None:
    current_payload = current.model_dump(mode="json", exclude={"created_at"})
    incoming_payload = incoming.model_dump(mode="json", exclude={"created_at"})
    if current_payload != incoming_payload:
        raise ValueError(f"{label} is immutable")


def _deployment_view(model: DeploymentRevisionModel) -> DeploymentRevision:
    return DeploymentRevision(
        deployment_revision_id=model.deployment_revision_id,
        git_commit=model.git_commit,
        container_image_digest=model.container_image_digest,
        schema_revision=model.schema_revision,
        source_inventory_hash=model.source_inventory_hash,
        vocabulary_revision=model.vocabulary_revision,
        policy_revision=model.policy_revision,
        capability_registry_revision=model.capability_registry_revision,
        skill_registry_revision=model.skill_registry_revision,
        model_provider_revision=model.model_provider_revision,
        configuration_digest=model.configuration_digest,
        created_at=_utc(model.created_at),
    )


def _suite_view(model: BenchmarkSuiteModel) -> BenchmarkSuite:
    return BenchmarkSuite(
        suite_id=model.suite_id,
        suite_revision=model.suite_revision,
        domain=BenchmarkDomain(model.domain),
        purpose=model.purpose,
        case_refs=list(model.case_refs_json),
        gold_revision=model.gold_revision,
        evaluator_revision=model.evaluator_revision,
        default_world_snapshot_ref=model.default_world_snapshot_ref,
        scoring_profile=cast(dict[str, JsonValue], dict(model.scoring_profile_json)),
        created_at=_utc(model.created_at),
    )


def _case_view(model: BenchmarkCaseModel) -> BenchmarkCase:
    return BenchmarkCase(
        case_id=model.case_id,
        case_revision=model.case_revision,
        input=cast(dict[str, JsonValue], dict(model.input_json)),
        execution_profile=model.execution_profile,
        target_refs=list(model.target_refs_json),
        world_snapshot_ref=model.world_snapshot_ref,
        fixture_refs=list(model.fixture_refs_json),
        expected_behavior=cast(dict[str, JsonValue], dict(model.expected_behavior_json)),
        gold_ref=model.gold_ref,
        tags=list(model.tags_json),
        latency_class=model.latency_class,
        replay_tier=model.replay_tier,
        created_at=_utc(model.created_at),
    )


def _run_view(model: BenchmarkRunModel) -> BenchmarkRun:
    return BenchmarkRun(
        benchmark_run_id=model.benchmark_run_id,
        suite_ref=model.suite_ref,
        gold_revision=model.gold_revision,
        deployment_revision_id=model.deployment_revision_id,
        model_config_ref=model.model_config_ref,
        world_snapshot_ref=model.world_snapshot_ref,
        started_at=_utc(model.started_at),
        finished_at=_utc(model.finished_at) if model.finished_at is not None else None,
        status=BenchmarkRunStatus(model.status),
        execution_mode=BenchmarkExecutionMode(model.execution_mode),
        warm_cold_condition=model.warm_cold_condition,
        environment=model.environment,
    )


def _case_run_view(model: BenchmarkCaseRunModel) -> BenchmarkCaseRun:
    return BenchmarkCaseRun(
        case_run_id=model.case_run_id,
        benchmark_run_id=model.benchmark_run_id,
        case_ref=model.case_ref,
        task_run_id=model.task_run_id,
        execution_id=model.execution_id,
        decision_ref=model.decision_ref,
        replay_checkpoint_ref=model.replay_checkpoint_ref,
        started_at=_utc(model.started_at),
        finished_at=_utc(model.finished_at) if model.finished_at is not None else None,
        status=BenchmarkCaseRunStatus(model.status),
        failure_class=model.failure_class,
        artifact_refs=list(model.artifact_refs_json),
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def _register_metric_definition(
    session: AsyncSession,
    *,
    definition: MetricDefinition,
    now: datetime,
) -> None:
    existing = await session.get(MetricDefinitionModel, definition.ref)
    if existing is not None:
        if existing.definition_digest != definition.digest:
            raise ValueError(f"metric definition revision is immutable: {definition.ref}")
        return
    session.add(
        MetricDefinitionModel(
            metric_definition_ref=definition.ref,
            metric_name=definition.name,
            revision=definition.revision,
            denominator=definition.denominator,
            aggregation=definition.aggregation.value,
            missing_value_policy=definition.missing_value_policy.value,
            direction=definition.direction.value,
            unit=definition.unit,
            definition_digest=definition.digest,
            created_at=now,
        )
    )
    await session.flush()
