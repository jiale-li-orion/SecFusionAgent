from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from pydantic import JsonValue
from selectolax.parser import HTMLParser
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.observation_promotion import ObservationPromotionService
from apps.perception_execution import BrokeredPhysicalObservationPort
from apps.perception_routes import ExternalObservationRoute, StaticPerceptionExecutionResolver
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.storage.factory import create_artifact_store
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
from packages.sources.adapters.html_index import HTMLIndexAdapter
from packages.sources.contracts import (
    AcquisitionTrigger,
    DiscoveredRef,
    QuerySpec,
    SourceDefinition,
    SourceRole,
    SourceState,
)
from packages.sources.registry.loader import load_source_definitions

CAPABILITY_ID = "source.read_registered_document"
_IMPL_ID = "registered-html-document-v1"
_SOURCE_ROLES = {SourceRole.PRIMARY, SourceRole.AUTHORITY, SourceRole.FORENSIC}
_WORD = re.compile(r"[\w-]{3,}", re.UNICODE)


def registered_research_sources(settings: Settings) -> dict[str, SourceDefinition]:
    return {
        source.source_id: source
        for source in load_source_definitions(settings.source_registry_path)
        if source.adapter_type == "html_index"
        and source.source_role in _SOURCE_ROLES
        and source.access_rights.get("classification") == "public"
        and isinstance(source.discovery_method.get("index_url"), str)
    }


def registered_source_registry(sources: dict[str, SourceDefinition]) -> CapabilityRegistry:
    input_schema: dict[str, JsonValue] = {
        "type": "object",
        "required": ["object_id", "source_id", "query_text"],
    }
    output_schema: dict[str, JsonValue] = {"type": "object"}
    schema_hash = native_schema_hash(input_schema, output_schema)
    contract = CapabilityContract(
        capability_id=CAPABILITY_ID,
        contract_revision=1,
        action="read_registered_document",
        applicable_resource_types=["registered.html_document"],
        canonical_input_schema=input_schema,
        canonical_output_schema=output_schema,
        observation_semantics="fresh_registered_source_document_before_evidence_promotion",
        effect_semantics=EffectSemantics.OBSERVATION,
        authority_semantics=["A source speaks only within its registered authority scope"],
        preconditions=["Existing bound target", "Public registered source and permitted host"],
        postconditions=["Raw page remains untrusted until evidence promotion"],
        idempotency="safe_read",
        reversibility="not_applicable",
        data_ingress_class="public",
        data_egress_class="public_query_only",
        failure_semantics=["no_matching_document", "provider_error", "source_scope_mismatch"],
        risk_class="low",
    )
    implementation = ToolImplementation(
        tool_impl_id=_IMPL_ID,
        implementation_revision=1,
        implementation_kind=ImplementationKind.PROVIDER_API,
        native_name="registered_html.read_document",
        transport="https",
        native_input_schema=input_schema,
        native_output_schema=output_schema,
        server_identity="registered-public-sources",
        auth_class="none",
        network_destinations=sorted(
            {
                f"{host}:443"
                for source in sources.values()
                for host in _configured_hosts(source)
                if isinstance(host, str)
            }
        ),
        health_ref="health:registered-html-sources",
        native_schema_hash=schema_hash,
    )

    binding = CapabilityBinding(
        binding_id="registered-html-document-binding-v1",
        binding_revision=1,
        capability_id=CAPABILITY_ID,
        contract_revision=1,
        tool_impl_id=_IMPL_ID,
        implementation_revision=1,
        resource_resolver="registered_source_id",
        effect_resolver="contract",
        authority_mapper="registered_source_role",
        execution_class=ExecutionClass.PROXIED_PROVIDER_READ,
        credential_profile="none",
        network_profile="registered_hosts_only",
        sandbox_profile="none",
        health_requirement="configured_provider",
        cost_class="one_or_two_public_requests",
        latency_class="interactive",
        native_schema_hash=schema_hash,
    )
    return CapabilityRegistry(
        revision="investigation-registered-html-v1",
        contracts=[contract],
        descriptors={
            CAPABILITY_ID: CapabilityDescriptor(
                purpose=(
                    "Read a current document from a registered public primary, authority or "
                    "forensic source. Supply exactly one source_id and a document URL or "
                    "focused title/query; a non-URL query searches that source's current index."
                ),
                limitations=[
                    "Only registered public HTML sources and their allowed hosts",
                    "Index search is bounded; no match is evidence of absence",
                ],
            )
        },
        implementations=[implementation],
        bindings=[binding],
    )


def _configured_hosts(source: SourceDefinition) -> list[str]:
    value = source.discovery_method.get("allowed_hosts")
    return [host for host in value if isinstance(host, str)] if isinstance(value, list) else []


class RegisteredDocumentExecutor:
    def __init__(
        self,
        *,
        session: AsyncSession,
        execution_id: str,
        task_run_id: str,
        allowed_object_ids: set[str],
        sources: dict[str, SourceDefinition],
        client: httpx.AsyncClient,
        artifacts: RuntimeArtifactService,
    ) -> None:
        self._session = session
        self._execution_id = execution_id
        self._task_run_id = task_run_id
        self._allowed_object_ids = allowed_object_ids
        self._sources = sources
        self._client = client
        self._artifacts = artifacts

    async def execute(
        self,
        implementation: ToolImplementation,
        *,
        native_arguments: dict[str, JsonValue],
        timeout_seconds: float,
    ) -> NativeExecutionResult:
        if implementation.tool_impl_id != _IMPL_ID:
            raise ValueError("unsupported registered document implementation")
        object_id = native_arguments.get("object_id")
        source_id = native_arguments.get("source_id")
        query_text = native_arguments.get("query_text")
        if not isinstance(object_id, str) or object_id not in self._allowed_object_ids:
            raise PermissionError("document read target escapes investigation TaskContract")
        if not isinstance(source_id, str) or source_id not in self._sources:
            raise ValueError("document read requires a registered source_id")
        if not isinstance(query_text, str) or not query_text.strip():
            raise ValueError("document read requires a URL or focused query")
        query_text = query_text.strip()[:500]
        source = self._sources[source_id]
        acquisition_run_id = str(uuid4())
        started_at = datetime.now(UTC)
        run = AcquisitionRunModel(
            run_id=acquisition_run_id,
            source_id=source_id,
            trigger=AcquisitionTrigger.INVESTIGATION.value,
            parent_run_id=self._task_run_id,
            query_spec=QuerySpec(filters={"query": query_text}).model_dump(mode="json"),
            status="running",
            cursor_in={},
            cursor_out={},
            attempt=1,
            created_at=started_at,
            started_at=started_at,
        )
        self._session.add(run)
        await self._session.flush()
        adapter = HTMLIndexAdapter(self._client)
        try:
            async with asyncio.timeout(timeout_seconds):
                if _is_url(query_text):
                    envelopes = await adapter.query(
                        source,
                        QuerySpec(filters={"url": query_text}),
                        acquisition_run_id=acquisition_run_id,
                        trigger=AcquisitionTrigger.INVESTIGATION,
                    )
                else:
                    batch = await adapter.discover(source, SourceState())
                    match = _best_index_match(batch.items, query_text)
                    if match is None:
                        run.status = "no_change"
                        run.finished_at = datetime.now(UTC)
                        run.cursor_out = {"index_count": len(batch.items), "result_count": 0}
                        return NativeExecutionResult(
                            status=CapabilityResultStatus.FAILED,
                            failure_code="no_matching_registered_document",
                            consumed_budget={"tool_calls": Decimal("1")},
                            cost={"provider_requests": 1},
                        )
                    envelopes = [
                        await adapter.fetch(
                            source,
                            match,
                            acquisition_run_id=acquisition_run_id,
                            trigger=AcquisitionTrigger.INVESTIGATION,
                        )
                    ]
        except Exception as exc:
            run.status = "failed"
            run.finished_at = datetime.now(UTC)
            run.error_code = type(exc).__name__
            run.error_detail = str(exc)[:4000]
            return NativeExecutionResult(
                status=CapabilityResultStatus.FAILED,
                failure_code="registered_source_read_failed",
                failure_detail=type(exc).__name__,
                consumed_budget={"tool_calls": Decimal("1")},
            )
        envelope = envelopes[0]
        body = envelope.content_bytes()
        if len(body) > 5_000_000:
            run.status = "failed"
            run.finished_at = datetime.now(UTC)
            run.error_code = "DocumentTooLarge"
            return NativeExecutionResult(
                status=CapabilityResultStatus.FAILED,
                failure_code="registered_source_document_too_large",
                consumed_budget={"tool_calls": Decimal("1")},
            )
        excerpt = _document_excerpt(body, source_id)
        if not excerpt:
            run.status = "failed"
            run.finished_at = datetime.now(UTC)
            run.error_code = "NoReadableArticleText"
            return NativeExecutionResult(
                status=CapabilityResultStatus.FAILED,
                failure_code="registered_source_no_readable_text",
                consumed_budget={"tool_calls": Decimal("1")},
            )
        run.status = "success"
        run.finished_at = datetime.now(UTC)
        run.cursor_out = {"result_count": 1, "canonical_url": envelope.canonical_url}
        artifact = await self._artifacts.write(
            self._session,
            execution_id=self._execution_id,
            producer_kind=f"capability:{CAPABILITY_ID}",
            producer_ref=acquisition_run_id,
            logical_name=f"registered-source-{acquisition_run_id}.html",
            media_type=envelope.media_type,
            body=body,
        )
        return NativeExecutionResult(
            status=CapabilityResultStatus.SUCCEEDED,
            canonical_output_ref=artifact.artifact_ref,
            raw_artifact_ref=artifact.artifact_ref,
            provenance={
                "acquisition_run_id": acquisition_run_id,
                "external_object_id": envelope.external_object_id,
                "external_revision": envelope.external_revision,
                "canonical_url": envelope.canonical_url,
                "published_at": (
                    envelope.published_at.isoformat() if envelope.published_at else None
                ),
                "updated_at": envelope.updated_at.isoformat() if envelope.updated_at else None,
                "source_id": source_id,
            },
            cost={"provider_requests": 1 if _is_url(query_text) else 2},
            consumed_budget={"tool_calls": Decimal("1")},
            extracted_candidates=excerpt,
        )


def _is_url(value: str) -> bool:
    return urlparse(value).scheme.lower() in {"https", "http"}


def _best_index_match(items: list[DiscoveredRef], query: str) -> DiscoveredRef | None:
    terms = {word.lower() for word in _WORD.findall(query)}
    if not terms:
        return None
    ranked = []
    for item in items:
        title = item.locator.get("title")
        text = title if isinstance(title, str) and title.strip() else item.canonical_url or ""
        matches = terms & {word.lower() for word in _WORD.findall(text)}
        if len(matches) >= max(2 if len(terms) >= 3 else 1, (len(terms) + 1) // 2):
            ranked.append((len(matches) / len(terms), len(matches), item))
    if not ranked:
        return None
    ranked.sort(key=lambda result: (result[0], result[1]), reverse=True)
    return ranked[0][2]


def _document_excerpt(body: bytes, source_id: str) -> list[JsonValue]:
    tree = HTMLParser(body.decode("utf-8", errors="replace"))
    for selector in ("script", "style", "nav", "footer", "header", "aside"):
        for node in tree.css(selector):
            node.decompose()
    root = tree.css_first("article") or tree.css_first("main") or tree.body
    if root is None:
        return []
    text = " ".join(root.text(separator=" ", strip=True).split())[:4500]
    if len(text) < 60:
        return []
    return [{"statement": f"{source_id} source excerpt: {text}"}]


class RegisteredSourceObservationPort:
    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        client: httpx.AsyncClient,
        artifacts: RuntimeArtifactService,
        registry: CapabilityRegistry,
        policy: StaticPolicyEngine,
        budget: BudgetGovernor,
        sources: dict[str, SourceDefinition],
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._client = client
        self._artifacts = artifacts
        self._registry = registry
        self._policy = policy
        self._budget = budget
        self._sources = sources

    async def execute(
        self,
        *,
        task_run_id: str,
        request: PerceptionRequest,
        step: PhysicalPerceptionStep,
    ) -> PerceptionStepResult:
        if request.target.object_id is None:
            return PerceptionStepResult(unresolved=["registered_source_requires_bound_object"])
        if len(request.target.source_ids) != 1:
            return PerceptionStepResult(unresolved=["registered_source_requires_one_source_id"])
        source_id = request.target.source_ids[0]
        if source_id not in self._sources:
            return PerceptionStepResult(unresolved=["registered_source_not_available"])
        if not request.target.query_text:
            return PerceptionStepResult(unresolved=["registered_source_requires_url_or_query"])
        source_store = create_artifact_store(self._settings)
        await source_store.ensure_bucket()
        resolver = StaticPerceptionExecutionResolver(
            self._session_factory,
            external_routes=[
                ExternalObservationRoute(
                    route_id=f"registered-html:{source_id}",
                    route_revision=1,
                    capability_requirement="external_observation",
                    capability_id=CAPABILITY_ID,
                    contract_revision=1,
                    action="read_registered_document",
                    resource_type="registered.html_document",
                    resource=f"source:{source_id}",
                    argument_map={"object_id": "object_id", "query_text": "query_text"},
                    static_arguments={"source_id": source_id},
                    estimated_budget={"tool_calls": Decimal("1")},
                    action_timeout_seconds=40,
                    promotion_source_id=source_id,
                    promote_request_target=True,
                )
            ],
        )
        return await BrokeredPhysicalObservationPort(
            capability_broker=CapabilityBroker(self._registry, self._policy, self._budget),
            capability_executor=None,
            capability_executor_factory=lambda session, task, envelope: RegisteredDocumentExecutor(
                session=session,
                execution_id=envelope.execution_id,
                task_run_id=task_run_id,
                allowed_object_ids={
                    target.removeprefix("object:")
                    for target in task.target_resources
                    if target.startswith("object:")
                },
                sources=self._sources,
                client=self._client,
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
                self._sources,
            ),
        ).execute(task_run_id=task_run_id, request=request, step=step)
