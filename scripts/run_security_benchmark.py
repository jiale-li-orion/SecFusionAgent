from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
    metric_definition,
)
from packages.evaluation.security import SecurityCaseObservation, score_security_case
from packages.runtime.artifacts import MemoryRuntimeBlobStore, RuntimeArtifactService
from packages.runtime.budget import BudgetGovernor
from packages.runtime.capability.broker import (
    CapabilityBroker,
    CapabilityDenied,
    InvocationGrants,
)
from packages.runtime.capability.contracts import (
    CapabilityBinding,
    CapabilityContract,
    CapabilityDescriptor,
    CapabilityRequest,
    EffectSemantics,
    ExecutionClass,
    ImplementationKind,
    ToolImplementation,
    native_schema_hash,
)
from packages.runtime.capability.registry import CapabilityRegistry
from packages.runtime.model import RecordedModelProvider
from packages.runtime.model.storage import ModelRequestModel
from packages.runtime.policy.engine import StaticPolicyEngine
from packages.runtime.storage.models import ExecutionRunModel
from packages.shared.config import get_settings
from packages.shared.db import Base, create_engine, create_session_factory
from packages.shared.model_provider import StructuredModelRequest
from packages.task_runtime.contracts.execution import ExecutionEnvelope
from packages.task_runtime.contracts.models import (
    DelegationCeiling,
    EffectCeiling,
    ExecutionProfile,
    TaskContract,
    TaskKind,
)

SUITE_ID = "security-controlled-v1"
EVALUATOR_REVISION = "security-controlled-runtime-v1"
SECRET_SENTINEL = "SECURITY-BENCHMARK-SENTINEL-DO-NOT-PERSIST"


class FixedResponse(BaseModel):
    value: str


class FixedProvider:
    name = "security-fixture-model"
    version = "fixture-v1"

    async def generate_structured(self, request, response_model):
        del request
        return response_model(value="ok")


class NeverExecutor:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, implementation, *, native_arguments, timeout_seconds):
        del implementation, native_arguments, timeout_seconds
        self.calls += 1
        raise AssertionError("security denial case reached capability executor")


class SecurityProbeResult(BaseModel):
    case_id: str
    observation: SecurityCaseObservation
    diagnostics: dict[str, JsonValue]


def _task() -> TaskContract:
    return TaskContract(
        task_contract_id="security-controlled-task",
        contract_revision=1,
        principal="security:benchmark",
        task_kind=TaskKind.VERIFY_VERSION_FIX,
        target_resources=["repo:vllm-project/vllm"],
        desired_state={"goal": "verify controlled security gate"},
        evidence_contract={"source_roles": ["primary"]},
        output_contract={"format": "security_probe"},
        temporal_contract={"scope": "controlled"},
        effect_ceiling=EffectCeiling.READ_ONLY,
        delegation_ceiling=DelegationCeiling(),
        completion_predicate={"type": "security_probe_complete"},
        policy_revision="security-policy-v1",
    )


def _envelope(*, capability_scope: list[str], now: datetime) -> ExecutionEnvelope:
    return ExecutionEnvelope(
        execution_id="execution:security-controlled",
        task_contract_id="security-controlled-task",
        task_run_id="security-controlled-run",
        role_revision="InvestigationRole@1",
        context_manifest_revision=1,
        execution_profile=ExecutionProfile.VERIFY,
        capability_scope=capability_scope,
        deadline_at=now + timedelta(minutes=5),
        budget_ref="budget:security-controlled",
        policy_revision="security-policy-v1",
        identity_scope=["public"],
        network_policy="none",
        side_effect_policy="read-only",
        sandbox_profile_revision="none@1",
    )


def _capability_registry() -> CapabilityRegistry:
    input_schema: dict[str, JsonValue] = {
        "type": "object",
        "required": ["repo"],
    }
    output_schema: dict[str, JsonValue] = {"type": "object"}
    schema_hash = native_schema_hash(input_schema, output_schema)
    contract = CapabilityContract(
        capability_id="github.read_release",
        contract_revision=1,
        action="read",
        applicable_resource_types=["github.release"],
        canonical_input_schema=input_schema,
        canonical_output_schema=output_schema,
        observation_semantics="provider_observation",
        effect_semantics=EffectSemantics.OBSERVATION,
        authority_semantics=["primary_for(repository_release_state)"],
        idempotency="safe",
        reversibility="not_applicable",
        data_ingress_class="public",
        data_egress_class="none",
        failure_semantics=["provider_blocked"],
        risk_class="low",
    )
    implementation = ToolImplementation(
        tool_impl_id="security-fixture-github-release",
        implementation_revision=1,
        implementation_kind=ImplementationKind.PROVIDER_API,
        native_name="github.get_release",
        transport="https",
        native_input_schema=input_schema,
        native_output_schema=output_schema,
        server_identity="api.github.com",
        server_origin="https://api.github.com",
        auth_class="none",
        network_destinations=["api.github.com:443"],
        health_ref="health:security-fixture",
        native_schema_hash=schema_hash,
    )
    binding = CapabilityBinding(
        binding_id="security-fixture-binding",
        binding_revision=1,
        capability_id=contract.capability_id,
        contract_revision=1,
        tool_impl_id=implementation.tool_impl_id,
        implementation_revision=1,
        canonical_to_native_args={"repo": "repository"},
        resource_resolver="identity",
        effect_resolver="contract",
        authority_mapper="source-role:primary",
        execution_class=ExecutionClass.PROXIED_PROVIDER_READ,
        credential_profile="none",
        network_profile="none",
        sandbox_profile="none",
        health_requirement="healthy",
        cost_class="none",
        latency_class="controlled",
        fallback_rank=1,
        native_schema_hash=schema_hash,
    )
    return CapabilityRegistry(
        revision="security-registry-v1",
        contracts=[contract],
        descriptors={
            contract.capability_id: CapabilityDescriptor(
                purpose="Controlled read capability for security policy regression"
            )
        },
        implementations=[implementation],
        bindings=[binding],
    )


def _request() -> CapabilityRequest:
    return CapabilityRequest(
        request_id="security-request-1",
        task_contract_id="security-controlled-task",
        task_run_id="security-controlled-run",
        principal="security:benchmark",
        capability_id="github.read_release",
        contract_revision=1,
        action="read",
        resource="repo:vllm-project/vllm:release:v0.22.0",
        resource_type="github.release",
        canonical_arguments={"repo": "vllm-project/vllm"},
        intended_effect=EffectSemantics.OBSERVATION,
        evidence_purpose="security_policy_probe",
    )


async def _isolated_factory() -> tuple[Any, async_sessionmaker[AsyncSession]]:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _probe_capability_scope_denial(now: datetime) -> SecurityProbeResult:
    engine, factory = await _isolated_factory()
    executor = NeverExecutor()
    try:
        async with factory() as session:
            broker = CapabilityBroker(
                _capability_registry(),
                StaticPolicyEngine(policy_revision="security-policy-v1", rules=[]),
                BudgetGovernor(now=lambda: now),
                now=lambda: now,
            )
            denial: str | None = None
            try:
                await broker.invoke(
                    session,
                    task=_task(),
                    envelope=_envelope(capability_scope=[], now=now),
                    request=_request(),
                    executor=executor,
                    estimated_budget={"tool_calls": Decimal("1")},
                    grants=InvocationGrants(),
                )
            except CapabilityDenied as exc:
                denial = str(exc)
            conformance = (
                denial == "capability_outside_execution_envelope_scope" and executor.calls == 0
            )
            return SecurityProbeResult(
                case_id="security-capability-scope-denial",
                observation=SecurityCaseObservation(
                    authority_violation_count=executor.calls,
                    secret_exposure_count=0,
                    expected_policy_outcomes=1,
                    conforming_policy_outcomes=int(conformance),
                ),
                diagnostics={
                    "expected_denial": "capability_outside_execution_envelope_scope",
                    "observed_denial": denial,
                    "executor_calls": executor.calls,
                },
            )
    finally:
        await engine.dispose()


async def _probe_implicit_policy_denial(now: datetime) -> SecurityProbeResult:
    engine, factory = await _isolated_factory()
    executor = NeverExecutor()
    try:
        async with factory() as session:
            broker = CapabilityBroker(
                _capability_registry(),
                StaticPolicyEngine(policy_revision="security-policy-v1", rules=[]),
                BudgetGovernor(now=lambda: now),
                now=lambda: now,
            )
            denial: str | None = None
            try:
                await broker.invoke(
                    session,
                    task=_task(),
                    envelope=_envelope(capability_scope=["github.read_release"], now=now),
                    request=_request(),
                    executor=executor,
                    estimated_budget={"tool_calls": Decimal("1")},
                    grants=InvocationGrants(),
                    healthy_refs={"health:security-fixture"},
                    available_execution_classes={ExecutionClass.PROXIED_PROVIDER_READ},
                )
            except CapabilityDenied as exc:
                denial = str(exc)
            conformance = denial == "policy_deny" and executor.calls == 0
            return SecurityProbeResult(
                case_id="security-implicit-policy-denial",
                observation=SecurityCaseObservation(
                    authority_violation_count=executor.calls,
                    secret_exposure_count=0,
                    expected_policy_outcomes=1,
                    conforming_policy_outcomes=int(conformance),
                ),
                diagnostics={
                    "expected_denial": "policy_deny",
                    "observed_denial": denial,
                    "executor_calls": executor.calls,
                },
            )
    finally:
        await engine.dispose()


async def _probe_model_secret_redaction(now: datetime) -> SecurityProbeResult:
    engine, factory = await _isolated_factory()
    blob_store = MemoryRuntimeBlobStore()
    artifact_service = RuntimeArtifactService(blob_store, now=lambda: now)
    execution_id = "execution:security-secret-redaction"
    try:
        async with factory() as session, session.begin():
            session.add(
                ExecutionRunModel(
                    execution_id=execution_id,
                    parent_execution_id=None,
                    task_run_id="security-secret-task",
                    envelope_json={},
                    status="created",
                    stop_reason=None,
                    created_at=now,
                    started_at=None,
                    finished_at=None,
                )
            )
        provider = RecordedModelProvider(
            factory,
            FixedProvider(),
            artifact_service=artifact_service,
        )
        request = StructuredModelRequest(
            system_instruction="Return the fixed controlled response.",
            data={
                "api_key": SECRET_SENTINEL,
                "nested": {
                    "password": SECRET_SENTINEL,
                    "safe_value": "visible",
                },
            },
            metadata={
                "model_purpose": "security.secret_redaction",
                "prompt_revision": "security-redaction-v1",
                "request_owner_ref": "security-case:secret-redaction",
                "execution_id": execution_id,
                "model_payload_persistence": "redacted_runtime_artifact",
                "credential_hint": SECRET_SENTINEL,
                "safe_metadata": "visible",
            },
        )
        result = await provider.generate_structured(request, FixedResponse)
        if result.value != "ok":
            raise RuntimeError("security fixture provider returned unexpected response")

        async with factory() as session:
            persisted = await session.scalar(select(ModelRequestModel))
            if persisted is None or persisted.request_artifact_ref is None:
                raise RuntimeError("security redaction probe did not persist request artifact")
            artifact_body = await artifact_service.read(session, persisted.request_artifact_ref)
            metadata_text = json.dumps(
                persisted.metadata_json,
                sort_keys=True,
                ensure_ascii=False,
            )
            artifact_text = artifact_body.decode("utf-8")
            metadata_exposed = SECRET_SENTINEL in metadata_text
            artifact_exposed = SECRET_SENTINEL in artifact_text
            exposure_count = int(metadata_exposed) + int(artifact_exposed)
            redaction_present = "[REDACTED]" in metadata_text and "[REDACTED]" in artifact_text
            conformance = exposure_count == 0 and redaction_present
            return SecurityProbeResult(
                case_id="security-model-secret-redaction",
                observation=SecurityCaseObservation(
                    authority_violation_count=0,
                    secret_exposure_count=exposure_count,
                    expected_policy_outcomes=1,
                    conforming_policy_outcomes=int(conformance),
                ),
                diagnostics={
                    "metadata_secret_exposed": metadata_exposed,
                    "request_artifact_secret_exposed": artifact_exposed,
                    "redaction_marker_present": redaction_present,
                    "request_artifact_persisted": True,
                    "control_substrate": "isolated_sqlite_plus_memory_runtime_artifact_store",
                },
            )
    finally:
        await engine.dispose()


async def _run(*, suite_revision: int, deployment_revision_id: str | None) -> dict[str, Any]:
    now = datetime.now(UTC)
    probes = [
        await _probe_capability_scope_denial(now),
        await _probe_implicit_policy_denial(now),
        await _probe_model_secret_redaction(now),
    ]

    register_runtime_models()
    settings = get_settings()
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
                        input=cast(
                            dict[str, JsonValue],
                            {
                                "control": item.case_id,
                                "subsystem": (
                                    "model_recording"
                                    if item.case_id == "security-model-secret-redaction"
                                    else "capability_authorization"
                                ),
                            },
                        ),
                        execution_profile="controlled_security_runtime",
                        expected_behavior=cast(
                            dict[str, JsonValue],
                            {
                                "authority_violation_count": 0,
                                "secret_exposure_count": 0,
                                "policy_conformance": 1.0,
                            },
                        ),
                        gold_ref=f"security-controlled-gold-v1#{item.case_id}",
                        tags=["security", "controlled", "runtime-regression"],
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
                    domain=BenchmarkDomain.SECURITY,
                    purpose=(
                        "Controlled runtime security regression for authority enforcement and "
                        "durable model-payload secret redaction"
                    ),
                    case_refs=case_refs,
                    gold_revision="security-controlled-gold-v1",
                    evaluator_revision=EVALUATOR_REVISION,
                    scoring_profile={
                        "metrics": [
                            "security.authority_violation_count",
                            "security.secret_exposure_count",
                            "security.policy_conformance",
                        ],
                        "scope": "controlled_runtime_regression_not_red_team_coverage",
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
                model_config_ref="model:fixture-no-network",
                now=now,
            )

        per_case: dict[str, Any] = {}
        for item in probes:
            score = score_security_case(item.observation)
            async with factory() as session, session.begin():
                case_run = await store.start_case_run(
                    session,
                    benchmark_run_id=run.benchmark_run_id,
                    case_ref=f"{item.case_id}@{suite_revision}",
                    now=now,
                )
                observations = (
                    (
                        "security.authority_violation_count",
                        float(score.authority_violation_count),
                        MeasurementSource.EXACT,
                    ),
                    (
                        "security.secret_exposure_count",
                        float(score.secret_exposure_count),
                        MeasurementSource.EXACT,
                    ),
                    (
                        "security.policy_conformance",
                        float(score.policy_conformance or 0.0),
                        MeasurementSource.DERIVED,
                    ),
                )
                for metric_name, value, source in observations:
                    definition = metric_definition(metric_name)
                    await store.observe_metric(
                        session,
                        case_run_id=case_run.case_run_id,
                        metric_name=metric_name,
                        value=value,
                        direction=definition.direction,
                        measurement_source=source,
                        subject_ref=f"security-case:{item.case_id}",
                        metadata=item.diagnostics,
                        now=now,
                    )
                await store.finish_case_run(
                    session,
                    case_run.case_run_id,
                    status=BenchmarkCaseRunStatus.PASSED,
                    now=now,
                )
            per_case[item.case_id] = {
                "authority_violation_count": score.authority_violation_count,
                "secret_exposure_count": score.secret_exposure_count,
                "policy_conformance": score.policy_conformance,
                "diagnostics": item.diagnostics,
            }

        async with factory() as session, session.begin():
            await store.finish_run(
                session,
                run.benchmark_run_id,
                status=BenchmarkRunStatus.COMPLETED,
                now=now,
            )
        authority_total = sum(item.observation.authority_violation_count for item in probes)
        secret_total = sum(item.observation.secret_exposure_count for item in probes)
        conforming = sum(item.observation.conforming_policy_outcomes for item in probes)
        expected = sum(item.observation.expected_policy_outcomes for item in probes)
        policy_conformance = conforming / expected if expected else None
        return {
            "schema_version": "security-controlled-benchmark-v1",
            "benchmark_run_id": run.benchmark_run_id,
            "deployment_revision_id": deployment_id,
            "suite_ref": f"{SUITE_ID}@{suite_revision}",
            "execution_mode": BenchmarkExecutionMode.LIVE_CONTROLLED.value,
            "scope": "controlled_runtime_regression_not_red_team_coverage",
            "authority_violation_count": authority_total,
            "secret_exposure_count": secret_total,
            "policy_conformance": policy_conformance,
            "controlled_gate_pass": (
                authority_total == 0 and secret_total == 0 and policy_conformance == 1.0
            ),
            "cases": per_case,
        }
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run controlled security runtime benchmark")
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
    encoded = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()
