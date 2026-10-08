from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import httpx
from pydantic import JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.observation_promotion import ObservationPromotionService
from apps.perception_execution import BrokeredPhysicalObservationPort
from apps.perception_routes import ExternalObservationRoute, StaticPerceptionExecutionResolver
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.storage.factory import create_artifact_store
from packages.intelligence.storage.knowledge_models import ExternalIdentifierModel, ObjectModel
from packages.investigation.perception.contracts import (
    PerceptionRequest,
    PerceptionStepResult,
    PhysicalPerceptionStep,
)
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.runtime.artifacts import RuntimeArtifactService
from packages.runtime.budget import BudgetGovernor
from packages.runtime.capability.broker import CapabilityBroker, NativeExecutionResult
from packages.runtime.capability.contracts import (
    CapabilityBinding,
    CapabilityContract,
    CapabilityDescriptor,
    CapabilityResultStatus,
    EffectSemantics,
    ExecutionClass,
    ImplementationKind,
    ToolImplementation,
    native_schema_hash,
)
from packages.runtime.capability.registry import CapabilityRegistry
from packages.runtime.policy.engine import StaticPolicyEngine
from packages.runtime.sandbox.broker import SandboxBroker
from packages.shared.config import Settings
from packages.sources.adapters.nvd import NVDAdapter
from packages.sources.contracts import AcquisitionTrigger, QuerySpec, SourceDefinition
from packages.sources.registry.loader import load_source_definitions

CAPABILITY_ID = "nvd.read_cve"
SOURCE_ID = "nvd-cves-2"
_CVE = re.compile(r"CVE-\d{4}-\d{4,}", re.IGNORECASE)


def nvd_capability_registry() -> CapabilityRegistry:
    input_schema: dict[str, JsonValue] = {"type": "object", "required": ["object_id"]}
    output_schema: dict[str, JsonValue] = {"type": "object"}
    schema_hash = native_schema_hash(input_schema, output_schema)
    contract = CapabilityContract(
        capability_id=CAPABILITY_ID,
        contract_revision=1,
        action="read_cve",
        applicable_resource_types=["nvd.cve"],
        canonical_input_schema=input_schema,
        canonical_output_schema=output_schema,
        observation_semantics="official_provider_observation_before_evidence_promotion",
        effect_semantics=EffectSemantics.OBSERVATION,
        authority_semantics=["NVD is authoritative only within its declared source scope"],
        preconditions=["Target must be an existing Vulnerability with a CVE identifier"],
        postconditions=["Raw response is an untrusted observation until promoted"],
        idempotency="safe_read",
        reversibility="not_applicable",
        data_ingress_class="public",
        data_egress_class="cve_identifier_only",
        failure_semantics=["not_found", "rate_limited", "provider_error"],
        risk_class="low",
    )
    implementation = ToolImplementation(
        tool_impl_id="nvd-cve-api-v1",
        implementation_revision=1,
        implementation_kind=ImplementationKind.PROVIDER_API,
        native_name="nvd.query_cve",
        transport="https",
        native_input_schema=input_schema,
        native_output_schema=output_schema,
        server_identity="services.nvd.nist.gov",
        server_origin="https://services.nvd.nist.gov",
        auth_class="optional_nvd_api_key",
        network_destinations=["services.nvd.nist.gov:443"],
        health_ref="health:nvd-cve-api",
        native_schema_hash=schema_hash,
    )
    binding = CapabilityBinding(
        binding_id="nvd-cve-api-binding-v1",
        binding_revision=1,
        capability_id=CAPABILITY_ID,
        contract_revision=1,
        tool_impl_id=implementation.tool_impl_id,
        implementation_revision=1,
        resource_resolver="fixed_nvd_source",
        effect_resolver="contract",
        authority_mapper="source:nvd-cves-2",
        execution_class=ExecutionClass.PROXIED_PROVIDER_READ,
        credential_profile="optional_nvd_api_key",
        network_profile="nvd_api_only",
        sandbox_profile="none",
        health_requirement="configured_provider",
        cost_class="one_provider_request",
        latency_class="interactive",
        native_schema_hash=schema_hash,
    )
    return CapabilityRegistry(
        revision="investigation-nvd-v1",
        contracts=[contract],
        descriptors={
            CAPABILITY_ID: CapabilityDescriptor(
                purpose=(
                    "Read the current official NVD record for an existing CVE "
                    "and attach it to the case target"
                ),
                limitations=["CVE vulnerabilities only", "NVD rate limits and availability apply"],
            )
        },
        implementations=[implementation],
        bindings=[binding],
    )


class NVDReadExecutor:
    def __init__(
        self,
        *,
        session: AsyncSession,
        execution_id: str,
        task_run_id: str,
        allowed_object_ids: set[str],
        source: SourceDefinition,
        client: httpx.AsyncClient,
        api_key: str | None,
        artifacts: RuntimeArtifactService,
    ) -> None:
        self._session = session
        self._execution_id = execution_id
        self._task_run_id = task_run_id
        self._allowed_object_ids = allowed_object_ids
        self._source = source
        self._client = client
        self._api_key = api_key
        self._artifacts = artifacts

    async def execute(
        self,
        implementation: ToolImplementation,
        *,
        native_arguments: dict[str, JsonValue],
        timeout_seconds: float,
    ) -> NativeExecutionResult:
        if implementation.tool_impl_id != "nvd-cve-api-v1":
            raise ValueError("unsupported NVD capability implementation")
        cve_id = await self._cve_for_target(native_arguments)
        # Keep the source run and raw artifact in the Broker transaction.
        acquisition_run_id = str(uuid4())
        started_at = datetime.now(UTC)
        run = AcquisitionRunModel(
            run_id=acquisition_run_id,
            source_id=SOURCE_ID,
            trigger=AcquisitionTrigger.INVESTIGATION.value,
            parent_run_id=self._task_run_id,
            query_spec=QuerySpec(filters={"cve_id": cve_id}).model_dump(mode="json"),
            status="running",
            cursor_in={},
            cursor_out={},
            attempt=1,
            created_at=started_at,
            started_at=started_at,
        )
        self._session.add(run)
        await self._session.flush()
        adapter = NVDAdapter(
            self._client,
            api_key=self._api_key,
            request_timeout_seconds=timeout_seconds,
        )
        try:
            envelopes = await adapter.query(
                self._source,
                QuerySpec(filters={"cve_id": cve_id}),
                acquisition_run_id=acquisition_run_id,
                trigger=AcquisitionTrigger.INVESTIGATION,
            )
        except Exception as exc:
            run.status = "failed"
            run.finished_at = datetime.now(UTC)
            run.error_code = type(exc).__name__
            run.error_detail = str(exc)[:4000]
            return NativeExecutionResult(
                status=CapabilityResultStatus.FAILED,
                failure_code="nvd_provider_error",
                failure_detail=type(exc).__name__,
                consumed_budget={"tool_calls": Decimal("1")},
            )
        run.status = "success" if envelopes else "no_change"
        run.finished_at = datetime.now(UTC)
        run.cursor_out = {"result_count": len(envelopes)}
        if len(envelopes) != 1 or envelopes[0].external_object_id.upper() != cve_id:
            run.status = "failed"
            run.finished_at = datetime.now(UTC)
            run.error_code = "NVDIdentityMismatchOrMissing"
            return NativeExecutionResult(
                status=CapabilityResultStatus.FAILED,
                failure_code="nvd_cve_not_found",
                consumed_budget={"tool_calls": Decimal("1")},
            )
        envelope = envelopes[0]
        artifact = await self._artifacts.write(
            self._session,
            execution_id=self._execution_id,
            producer_kind="capability:nvd.read_cve",
            producer_ref=envelope.acquisition_run_id,
            logical_name=f"nvd-{cve_id}-{acquisition_run_id}.json",
            media_type=envelope.media_type,
            body=envelope.content_bytes(),
        )
        return NativeExecutionResult(
            status=CapabilityResultStatus.SUCCEEDED,
            canonical_output_ref=artifact.artifact_ref,
            raw_artifact_ref=artifact.artifact_ref,
            provenance={
                "acquisition_run_id": envelope.acquisition_run_id,
                "external_object_id": envelope.external_object_id,
                "external_revision": envelope.external_revision,
                "canonical_url": envelope.canonical_url,
                "published_at": (
                    envelope.published_at.isoformat() if envelope.published_at else None
                ),
                "updated_at": envelope.updated_at.isoformat() if envelope.updated_at else None,
                "source_id": SOURCE_ID,
            },
            cost={"provider_requests": 1},
            consumed_budget={"tool_calls": Decimal("1")},
            extracted_candidates=_nvd_statements(envelope.json_payload),
        )

    async def _cve_for_target(self, arguments: dict[str, JsonValue]) -> str:
        object_id = arguments.get("object_id")
        if not isinstance(object_id, str) or not object_id:
            raise ValueError("NVD read requires a bound existing object_id")
        if object_id not in self._allowed_object_ids:
            raise PermissionError("NVD read target is outside the investigation TaskContract")
        obj = await self._session.get(ObjectModel, object_id)
        if obj is None or obj.object_type != "Vulnerability":
            raise ValueError("NVD read target must be an existing Vulnerability")
        cve_ids = list(
            await self._session.scalars(
                select(ExternalIdentifierModel.value).where(
                    ExternalIdentifierModel.object_id == object_id,
                    ExternalIdentifierModel.namespace == "cve",
                )
            )
        )
        if len(cve_ids) != 1 or _CVE.fullmatch(cve_ids[0]) is None:
            raise ValueError("NVD read target requires exactly one valid CVE identifier")
        cve_id = cve_ids[0].upper()
        identifier = arguments.get("identifier")
        if isinstance(identifier, dict):
            if identifier.get("namespace") != "cve":
                raise ValueError("NVD read identifier must use the cve namespace")
            requested = identifier.get("value")
            if requested is not None and (
                not isinstance(requested, str) or requested.upper() != cve_id
            ):
                raise ValueError("NVD read identifier differs from bound target")
        return cve_id


def _nvd_statements(payload: dict[str, object]) -> list[JsonValue]:
    cve = payload.get("cve")
    if not isinstance(cve, dict):
        return []
    descriptions = cve.get("descriptions")
    if not isinstance(descriptions, list):
        return []
    for description in descriptions:
        if isinstance(description, dict) and description.get("lang") == "en":
            value = description.get("value")
            if isinstance(value, str) and value.strip():
                return [{"statement": f"NVD description: {value[:1800]}"}]
    return []


class NVDObservationPort:
    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        client: httpx.AsyncClient,
        artifacts: RuntimeArtifactService,
        registry: CapabilityRegistry,
        policy: StaticPolicyEngine,
        budget: BudgetGovernor,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._client = client
        self._artifacts = artifacts
        self._registry = registry
        self._policy = policy
        self._budget = budget
        sources = {
            item.source_id: item for item in load_source_definitions(settings.source_registry_path)
        }
        self._source = sources[SOURCE_ID]

    async def execute(
        self,
        *,
        task_run_id: str,
        request: PerceptionRequest,
        step: PhysicalPerceptionStep,
    ) -> PerceptionStepResult:
        if request.target.object_id is None:
            return PerceptionStepResult(
                unresolved=["external_nvd_requires_existing_vulnerability_object"]
            )
        if request.target.source_ids and SOURCE_ID not in request.target.source_ids:
            return PerceptionStepResult(unresolved=["external_nvd_source_scope_mismatch"])
        source_store = create_artifact_store(self._settings)
        await source_store.ensure_bucket()
        resolver = StaticPerceptionExecutionResolver(
            self._session_factory,
            external_routes=[
                ExternalObservationRoute(
                    route_id="nvd-cve-official-v1",
                    route_revision=1,
                    capability_requirement="external_observation",
                    capability_id=CAPABILITY_ID,
                    contract_revision=1,
                    action="read_cve",
                    resource_type="nvd.cve",
                    resource=f"source:{SOURCE_ID}",
                    argument_map={"object_id": "object_id", "identifier": "identifier"},
                    estimated_budget={"tool_calls": Decimal("1")},
                    action_timeout_seconds=30,
                    promotion_source_id=SOURCE_ID,
                    promote_request_target=True,
                )
            ],
        )
        return await BrokeredPhysicalObservationPort(
            capability_broker=CapabilityBroker(self._registry, self._policy, self._budget),
            capability_executor=None,
            capability_executor_factory=lambda session, task, envelope: NVDReadExecutor(
                session=session,
                execution_id=envelope.execution_id,
                task_run_id=task_run_id,
                allowed_object_ids={
                    target.removeprefix("object:")
                    for target in task.target_resources
                    if target.startswith("object:")
                },
                source=self._source,
                client=self._client,
                api_key=self._settings.nvd_api_key,
                artifacts=self._artifacts,
            ),
            sandbox_broker=SandboxBroker(self._policy, {}),
            resolver=resolver,
            session_factory=self._session_factory,
            promotion_port=ObservationPromotionService(
                self._session_factory,
                self._policy,
                self._artifacts,
                EvidenceIngress(source_store),
                {SOURCE_ID: self._source},
            ),
        ).execute(task_run_id=task_run_id, request=request, step=step)
