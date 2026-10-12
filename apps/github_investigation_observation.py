from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import unquote, urlparse
from uuid import uuid4

import httpx
from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.observation_promotion import ObservationPromotionService
from apps.perception_execution import BrokeredPhysicalObservationPort
from apps.perception_routes import ExternalObservationRoute, StaticPerceptionExecutionResolver
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.storage.factory import create_artifact_store
from packages.intelligence.storage.knowledge_models import ObjectModel
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
from packages.sources.adapters.github_repo import GitHubRepoAdapter
from packages.sources.contracts import (
    AcquisitionTrigger,
    IngestEnvelope,
    QuerySpec,
    SourceDefinition,
)
from packages.sources.registry.loader import load_source_definitions

CAPABILITY_ID = "github.read_development_record"
SOURCE_ID = "github-target-repos"
_IMPL_ID = "github-investigation-record-v1"
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA = re.compile(r"^[0-9a-fA-F]{7,40}$")
_GITHUB_TYPES = {"Repo", "Issue", "PullRequest", "Commit", "Release"}


def github_investigation_source(settings: Settings) -> SourceDefinition:
    source = next(
        item
        for item in load_source_definitions(settings.source_registry_path)
        if item.source_id == SOURCE_ID
    )
    if (
        source.adapter_type != "github_repo"
        or source.access_rights.get("classification") != "public"
    ):
        raise ValueError("GitHub investigation source must be a registered public repository API")
    return source


def github_capability_registry() -> CapabilityRegistry:
    input_schema: dict[str, JsonValue] = {"type": "object", "required": ["object_id"]}
    output_schema: dict[str, JsonValue] = {"type": "object"}
    schema_hash = native_schema_hash(input_schema, output_schema)
    contract = CapabilityContract(
        capability_id=CAPABILITY_ID,
        contract_revision=1,
        action="read_development_record",
        applicable_resource_types=["github.development_record"],
        canonical_input_schema=input_schema,
        canonical_output_schema=output_schema,
        observation_semantics="official_github_record_before_evidence_promotion",
        effect_semantics=EffectSemantics.OBSERVATION,
        authority_semantics=[
            "GitHub records attest repository activity, not a security fix by title"
        ],
        preconditions=["Bound GitHub object in a registered repository"],
        postconditions=["Raw API result remains untrusted until evidence promotion"],
        idempotency="safe_read",
        reversibility="not_applicable",
        data_ingress_class="public",
        data_egress_class="registered_repository_reference_only",
        failure_semantics=["record_not_found", "rate_limited", "source_scope_mismatch"],
        risk_class="low",
    )
    implementation = ToolImplementation(
        tool_impl_id=_IMPL_ID,
        implementation_revision=1,
        implementation_kind=ImplementationKind.PROVIDER_API,
        native_name="github.query_development_record",
        transport="https",
        native_input_schema=input_schema,
        native_output_schema=output_schema,
        server_identity="api.github.com",
        server_origin="https://api.github.com",
        auth_class="optional_github_token",
        network_destinations=["api.github.com:443"],
        health_ref="health:github-repository-api",
        native_schema_hash=schema_hash,
    )
    binding = CapabilityBinding(
        binding_id="github-investigation-record-binding-v1",
        binding_revision=1,
        capability_id=CAPABILITY_ID,
        contract_revision=1,
        tool_impl_id=_IMPL_ID,
        implementation_revision=1,
        resource_resolver="registered_github_repository",
        effect_resolver="contract",
        authority_mapper=f"source:{SOURCE_ID}",
        execution_class=ExecutionClass.PROXIED_PROVIDER_READ,
        credential_profile="optional_github_token",
        network_profile="github_api_only",
        sandbox_profile="none",
        health_requirement="configured_provider",
        cost_class="one_or_two_provider_requests",
        latency_class="interactive",
        native_schema_hash=schema_hash,
    )
    return CapabilityRegistry(
        revision="investigation-github-v1",
        contracts=[contract],
        descriptors={
            CAPABILITY_ID: CapabilityDescriptor(
                purpose=(
                    "Read an exact GitHub issue, pull request with changed-file patches, "
                    "commit, release, release/commit comparison or repository record "
                    "for the bound registered project"
                ),
                limitations=[
                    "Registered repositories only; one exact record or bounded release list",
                    "A PR title or release note alone does not prove a vulnerability fix",
                    "GitHub lists at most the first 100 changed files",
                    "Compare verifies commit ancestry in a published release tag, not deployment",
                ],
            )
        },
        implementations=[implementation],
        bindings=[binding],
    )


def _repo_for_object(obj: ObjectModel, allowed_repos: set[str]) -> str:
    if obj.object_type not in _GITHUB_TYPES or not obj.canonical_key.startswith("github:"):
        raise ValueError("GitHub read requires a bound GitHub development object")
    canonical_repo = obj.canonical_key.removeprefix("github:").split(":", 1)[0]
    properties = obj.properties if isinstance(obj.properties, dict) else {}
    candidate = properties.get("repo_full_name") or properties.get("full_name")
    if not isinstance(candidate, str):
        candidate = canonical_repo
    if candidate.lower() != canonical_repo.lower():
        raise ValueError("GitHub object repository metadata disagrees with canonical identity")
    if _REPO.fullmatch(candidate) is None or candidate.lower() not in allowed_repos:
        raise PermissionError("GitHub repository is outside registered source scope")
    return candidate


def _selection(obj: ObjectModel, repo: str, query: str | None) -> dict[str, JsonValue]:
    properties = obj.properties if isinstance(obj.properties, dict) else {}
    if not query:
        number = properties.get("number")
        if obj.object_type in {"PullRequest", "Issue"}:
            if not isinstance(number, int) or number < 1:
                raise ValueError("bound GitHub issue or pull request lacks an exact number")
            if obj.object_type == "PullRequest":
                return {"object_type": "pull_request", "pull_number": number}
            return {"object_type": "issue", "issue_number": number}
        tag_name = properties.get("tag_name")
        if obj.object_type == "Release" and isinstance(tag_name, str):
            return {"object_type": "release", "tag": _checked_tag(tag_name)}
        if obj.object_type == "Release":
            raise ValueError("bound GitHub release lacks an exact tag")
        sha = properties.get("sha")
        if obj.object_type == "Commit" and isinstance(sha, str):
            return {"object_type": "commit", "commit_sha": sha}
        if obj.object_type == "Commit":
            raise ValueError("bound GitHub commit lacks an exact SHA")
        return {"object_type": "repository"}
    if query == "releases":
        return {"object_type": "releases", "limit": 10}
    parsed = urlparse(query)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise ValueError("GitHub read requires an exact github.com URL or 'releases'")
    segments = [unquote(part) for part in parsed.path.strip("/").split("/")]
    if len(segments) < 4 or "/".join(segments[:2]).lower() != repo.lower():
        raise PermissionError("GitHub URL does not belong to the bound repository")
    kind, value = segments[2], segments[3]
    if kind == "pull" and value.isdecimal() and (
        len(segments) == 4 or (len(segments) == 5 and segments[4] == "files")
    ):
        return {"object_type": "pull_request", "pull_number": int(value)}
    if kind == "issues" and value.isdecimal() and len(segments) == 4:
        return {"object_type": "issue", "issue_number": int(value)}
    if kind == "commit" and _SHA.fullmatch(value) and len(segments) == 4:
        return {"object_type": "commit", "commit_sha": value}
    if kind == "releases" and value == "tag" and len(segments) == 5:
        return {"object_type": "release", "tag": _checked_tag(segments[4])}
    if kind == "compare" and len(segments) == 4 and "..." in value:
        sha, tag = value.split("...", 1)
        if _SHA.fullmatch(sha):
            return {
                "object_type": "compare_commit_to_release",
                "fix_commit_sha": sha,
                "release_tag": _checked_tag(tag),
            }
    raise ValueError("unsupported GitHub development record URL")


def _checked_tag(tag: str) -> str:
    if not tag or len(tag) > 100 or ".." in tag or any(ord(char) < 32 for char in tag):
        raise ValueError("GitHub release tag is not a safe exact identifier")
    return tag


def _statements(payload: dict[str, object], kind: str) -> list[JsonValue]:
    if kind == "compare_commit_to_release":
        release = payload.get("release")
        comparison = payload.get("comparison")
        if not isinstance(release, dict) or not isinstance(comparison, dict):
            return []
        status = comparison.get("status")
        contained = status in {"ahead", "identical"}
        return [{"statement": (
            f"Official GitHub release tag {release.get('tag_name')} "
            f"(published_at={release.get('published_at')}, "
            f"draft={release.get('draft')}, prerelease={release.get('prerelease')}) "
            f"points to a commit compared with fix commit {payload.get('fix_commit_sha')}. "
            f"GitHub comparison status={status}, ahead_by={comparison.get('ahead_by')}, "
            f"behind_by={comparison.get('behind_by')}; "
            f"fix_commit_in_release_history={contained}. "
            f"Release URL={release.get('html_url')}."
        )}]
    if kind == "releases":
        releases = payload.get("releases")
        if not isinstance(releases, list):
            return []
        statements: list[JsonValue] = []
        for release in releases[:10]:
            if not isinstance(release, dict):
                continue
            statements.append({"statement": (
                f"GitHub release {str(release.get('tag_name') or '')[:100]}: "
                f"{str(release.get('name') or '')[:200]}; "
                f"published_at={release.get('published_at')}; "
                f"notes={str(release.get('body') or '')[:900]}"
            )})
        return statements
    if kind == "pull_request":
        pr = payload.get("pull_request")
        if not isinstance(pr, dict):
            return []
        fields = [
            f"GitHub pull request title: {str(pr.get('title') or '')[:250]}",
            f"GitHub pull request description: {str(pr.get('body') or '')[:1800]}",
            f"GitHub merge state: merged_at={pr.get('merged_at')}, "
            f"merge_commit_sha={pr.get('merge_commit_sha')}",
        ]
        files = payload.get("files")
        if isinstance(files, list):
            fields.append(
                f"Changed files returned: {len(files)}; "
                f"possibly_truncated={bool(payload.get('files_possibly_truncated'))}"
            )
            for item in files[:12]:
                if not isinstance(item, dict):
                    continue
                fields.append(
                    f"Changed file {str(item.get('filename') or '')[:200]}: "
                    f"status={item.get('status')}, additions={item.get('additions')}, "
                    f"deletions={item.get('deletions')}; "
                    f"patch={str(item.get('patch') or '[patch unavailable]')[:1200]}"
                )
        return [{"statement": value} for value in fields]
    fields = [
        f"GitHub {kind} title/name: {str(payload.get('title') or payload.get('name') or '')[:250]}",
        f"GitHub {kind} description/body: "
        f"{str(payload.get('body') or payload.get('description') or '')[:2000]}",
        f"GitHub {kind} state and time: state={payload.get('state')}, "
        f"published_at={payload.get('published_at')}, updated_at={payload.get('updated_at')}",
    ]
    if kind == "commit":
        commit = payload.get("commit")
        if isinstance(commit, dict):
            fields.append(f"GitHub commit message: {str(commit.get('message') or '')[:1500]}")
    return [{"statement": value} for value in fields if value.strip()]


class GitHubInvestigationExecutor:
    def __init__(
        self,
        *,
        session: AsyncSession,
        execution_id: str,
        task_run_id: str,
        allowed_object_ids: set[str],
        source: SourceDefinition,
        client: httpx.AsyncClient,
        token: str | None,
        artifacts: RuntimeArtifactService,
    ) -> None:
        self._session = session
        self._execution_id = execution_id
        self._task_run_id = task_run_id
        self._allowed_object_ids = allowed_object_ids
        self._source = source
        self._client = client
        self._token = token
        self._artifacts = artifacts

    async def execute(
        self,
        implementation: ToolImplementation,
        *,
        native_arguments: dict[str, JsonValue],
        timeout_seconds: float,
    ) -> NativeExecutionResult:
        if implementation.tool_impl_id != _IMPL_ID:
            raise ValueError("unsupported GitHub investigation implementation")
        object_id = native_arguments.get("object_id")
        if not isinstance(object_id, str) or object_id not in self._allowed_object_ids:
            raise PermissionError("GitHub read target escapes investigation TaskContract")
        obj = await self._session.get(ObjectModel, object_id)
        if obj is None:
            raise ValueError("GitHub read target object does not exist")
        configured = self._source.discovery_method.get("repos")
        allowed_repos = (
            {item.lower() for item in configured if isinstance(item, str)}
            if isinstance(configured, list)
            else set()
        )
        repo = _repo_for_object(obj, allowed_repos)
        query = native_arguments.get("query_text")
        if query is not None and not isinstance(query, str):
            raise ValueError("GitHub query_text must be a URL or 'releases'")
        filters = _selection(obj, repo, query.strip() if isinstance(query, str) else None)
        kind = str(filters["object_type"])
        run_id = str(uuid4())
        started_at = datetime.now(UTC)
        run = AcquisitionRunModel(
            run_id=run_id,
            source_id=SOURCE_ID,
            trigger=AcquisitionTrigger.INVESTIGATION.value,
            parent_run_id=self._task_run_id,
            query_spec=QuerySpec(filters={"repo_full_name": repo, **filters}).model_dump(
                mode="json"
            ),
            status="running",
            cursor_in={},
            cursor_out={},
            attempt=1,
            created_at=started_at,
            started_at=started_at,
        )
        self._session.add(run)
        await self._session.flush()
        adapter = GitHubRepoAdapter(self._client, token=self._token)
        query_spec = QuerySpec(filters={"repo_full_name": repo, **filters})
        request_count = 1
        try:
            async with asyncio.timeout(timeout_seconds):
                records = await adapter.query(
                    self._source,
                    query_spec,
                    acquisition_run_id=run_id,
                    trigger=AcquisitionTrigger.INVESTIGATION,
                )
                if not records:
                    raise LookupError("GitHub returned no development record")
                envelope = records[0]
                if kind == "releases":
                    envelope = IngestEnvelope.for_json_payload(
                        acquisition_run_id=run_id,
                        trigger=AcquisitionTrigger.INVESTIGATION,
                        source_id=SOURCE_ID,
                        external_object_id=f"{repo}:releases:investigation",
                        payload={"releases": [item.json_payload for item in records]},
                        canonical_url=f"https://github.com/{repo}/releases",
                        published_at=None,
                        updated_at=None,
                        external_revision=None,
                        request_metadata={"provider": "github", "object_type": "release_list"},
                    )
                if kind == "pull_request":
                    request_count = 2
                    files = await adapter.query(
                        self._source,
                        QuerySpec(
                            filters={
                                "repo_full_name": repo,
                                "object_type": "pull_request_files",
                                "pull_number": filters["pull_number"],
                            }
                        ),
                        acquisition_run_id=run_id,
                        trigger=AcquisitionTrigger.INVESTIGATION,
                    )
                    payload = {
                        "pull_request": envelope.json_payload,
                        "files": files[0].json_payload["files"],
                        "files_possibly_truncated": files[0].json_payload["possibly_truncated"],
                    }
                    envelope = IngestEnvelope.for_json_payload(
                        acquisition_run_id=run_id,
                        trigger=AcquisitionTrigger.INVESTIGATION,
                        source_id=SOURCE_ID,
                        external_object_id=f"{repo}:pull_request:{filters['pull_number']}:investigation",
                        payload=payload,
                        canonical_url=envelope.canonical_url,
                        published_at=envelope.published_at,
                        updated_at=envelope.updated_at,
                        external_revision=None,
                        request_metadata={
                            "provider": "github",
                            "object_type": "pull_request_with_files",
                        },
                    )
                if kind == "compare_commit_to_release":
                    comparison = envelope
                    base_commit = comparison.json_payload.get("base_commit")
                    base_sha = (
                        base_commit.get("sha") if isinstance(base_commit, dict) else None
                    )
                    if not isinstance(base_sha, str) or not base_sha.lower().startswith(
                        str(filters["fix_commit_sha"]).lower()
                    ):
                        raise ValueError("GitHub comparison did not resolve the requested commit")
                    request_count = 2
                    release = (await adapter.query(
                        self._source,
                        QuerySpec(filters={
                            "repo_full_name": repo,
                            "object_type": "release",
                            "tag": filters["release_tag"],
                        }),
                        acquisition_run_id=run_id,
                        trigger=AcquisitionTrigger.INVESTIGATION,
                    ))[0]
                    release_payload = release.json_payload
                    if release_payload.get("tag_name") != filters["release_tag"]:
                        raise ValueError("GitHub release did not resolve the requested tag")
                    if release_payload.get("draft") is True or not release_payload.get(
                        "published_at"
                    ):
                        raise ValueError("release tag is not a published GitHub release")
                    envelope = IngestEnvelope.for_json_payload(
                        acquisition_run_id=run_id,
                        trigger=AcquisitionTrigger.INVESTIGATION,
                        source_id=SOURCE_ID,
                        external_object_id=(
                            f"{repo}:compare:{filters['fix_commit_sha']}:"
                            f"{filters['release_tag']}:investigation"
                        ),
                        payload={
                            "fix_commit_sha": filters["fix_commit_sha"],
                            "release": release_payload,
                            "comparison": comparison.json_payload,
                        },
                        canonical_url=comparison.canonical_url,
                        published_at=release.published_at,
                        updated_at=release.updated_at,
                        external_revision=None,
                        request_metadata={
                            "provider": "github", "object_type": "compare_commit_to_release",
                        },
                    )
        except Exception as exc:
            run.status = "failed"
            run.finished_at = datetime.now(UTC)
            run.error_code = type(exc).__name__
            run.error_detail = str(exc)[:4000]
            return NativeExecutionResult(
                status=CapabilityResultStatus.FAILED,
                failure_code="github_development_read_failed",
                failure_detail=type(exc).__name__,
                consumed_budget={"tool_calls": Decimal("1")},
                cost={"provider_requests": request_count},
            )
        body = envelope.content_bytes()
        if len(body) > 5_000_000:
            run.status = "failed"
            run.finished_at = datetime.now(UTC)
            run.error_code = "DevelopmentRecordTooLarge"
            return NativeExecutionResult(
                status=CapabilityResultStatus.FAILED,
                failure_code="github_development_record_too_large",
                consumed_budget={"tool_calls": Decimal("1")},
                cost={"provider_requests": request_count},
            )
        run.status = "success"
        run.finished_at = datetime.now(UTC)
        run.cursor_out = {"result_count": 1, "canonical_url": envelope.canonical_url}
        artifact = await self._artifacts.write(
            self._session,
            execution_id=self._execution_id,
            producer_kind=f"capability:{CAPABILITY_ID}",
            producer_ref=run_id,
            logical_name=f"github-development-{run_id}.json",
            media_type="application/json",
            body=body,
        )
        return NativeExecutionResult(
            status=CapabilityResultStatus.SUCCEEDED,
            canonical_output_ref=artifact.artifact_ref,
            raw_artifact_ref=artifact.artifact_ref,
            provenance={
                "acquisition_run_id": run_id,
                "external_object_id": envelope.external_object_id,
                "external_revision": envelope.external_revision,
                "canonical_url": envelope.canonical_url,
                "published_at": (
                    envelope.published_at.isoformat() if envelope.published_at else None
                ),
                "updated_at": envelope.updated_at.isoformat() if envelope.updated_at else None,
                "source_id": SOURCE_ID,
                "repo_full_name": repo,
                "record_type": kind,
            },
            cost={"provider_requests": request_count},
            consumed_budget={"tool_calls": Decimal("1")},
            extracted_candidates=_statements(envelope.json_payload, kind),
        )


class GitHubInvestigationObservationPort:
    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        client: httpx.AsyncClient,
        artifacts: RuntimeArtifactService,
        registry: CapabilityRegistry,
        policy: StaticPolicyEngine,
        budget: BudgetGovernor,
        source: SourceDefinition,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._client = client
        self._artifacts = artifacts
        self._registry = registry
        self._policy = policy
        self._budget = budget
        self._source = source

    async def execute(
        self,
        *,
        task_run_id: str,
        request: PerceptionRequest,
        step: PhysicalPerceptionStep,
    ) -> PerceptionStepResult:
        if request.target.object_id is None:
            return PerceptionStepResult(unresolved=["github_read_requires_bound_object"])
        source_store = create_artifact_store(self._settings)
        await source_store.ensure_bucket()
        resolver = StaticPerceptionExecutionResolver(
            self._session_factory,
            external_routes=[
                ExternalObservationRoute(
                    route_id="github-development-record-v1",
                    route_revision=1,
                    capability_requirement="external_observation",
                    capability_id=CAPABILITY_ID,
                    contract_revision=1,
                    action="read_development_record",
                    resource_type="github.development_record",
                    resource=f"source:{SOURCE_ID}",
                    argument_map={"object_id": "object_id"},
                    optional_argument_map={"query_text": "query_text"},
                    estimated_budget={"tool_calls": Decimal("1")},
                    action_timeout_seconds=40,
                    promotion_source_id=SOURCE_ID,
                    promote_request_target=True,
                )
            ],
        )
        return await BrokeredPhysicalObservationPort(
            capability_broker=CapabilityBroker(self._registry, self._policy, self._budget),
            capability_executor=None,
            capability_executor_factory=lambda session, task, envelope: GitHubInvestigationExecutor(
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
                token=self._settings.github_token,
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
