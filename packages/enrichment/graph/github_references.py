from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from urllib.parse import unquote, urlparse

from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.knowledge.contracts import (
    EnrichmentCandidate,
    EvidenceAnchor,
    ObjectCandidate,
    RelationCandidate,
)
from packages.intelligence.knowledge.read import (
    ClaimView,
    EvidenceRef,
    KnowledgeObjectView,
    get_object_by_identifier,
    get_vulnerability_by_cve,
)
from packages.intelligence.knowledge.write import EvidenceBackedKnowledgeWriter
from packages.intelligence.normalization.canonical import NormalizationResult
from packages.intelligence.structured.github_repo import GitHubRepoMapper
from packages.intelligence.structured.service import StructuredIndexService
from packages.monitoring.acquisition.service import AcquisitionService
from packages.sources.contracts import QuerySpec, SourceAdapter, SourceDefinition


@dataclass(frozen=True, slots=True)
class GitHubDevelopmentReference:
    url: str
    repo_full_name: str
    object_type: str
    filters: dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class _EvidenceGroup:
    source_id: str
    evidence: EvidenceRef
    references: tuple[GitHubDevelopmentReference, ...]


class GitHubReferenceGraphService:
    PROCESSOR_NAME = "github-reference-graph"
    PROCESSOR_VERSION = "1"

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        acquisition: AcquisitionService,
        evidence_ingress: EvidenceIngress,
        writer: EvidenceBackedKnowledgeWriter,
        sources: dict[str, SourceDefinition],
        adapters: dict[str, SourceAdapter],
        *,
        github_source_id: str = "github-target-repos",
    ) -> None:
        self._session_factory = session_factory
        self._acquisition = acquisition
        self._writer = writer
        self._sources = sources
        self._adapters = adapters
        self._github_source_id = github_source_id
        self._mapper = GitHubRepoMapper()
        self._structured = StructuredIndexService(
            evidence_ingress,
            writer,
            {"github_repo": self._mapper},
        )

    async def enrich_cve(
        self,
        cve_id: str,
        *,
        parent_run_id: str | None = None,
    ) -> list[NormalizationResult]:
        async with self._session_factory() as session:
            view = await get_vulnerability_by_cve(session, cve_id)
        if view is None:
            raise LookupError(f"vulnerability not found: {cve_id}")

        github_source = self._sources[self._github_source_id]
        github_adapter = self._adapters[self._github_source_id]
        allowed_repos = _configured_repos(github_source)
        groups = _reference_groups(view.claims, allowed_repos)
        results: list[NormalizationResult] = []

        for group in groups:
            relation_candidates: list[RelationCandidate] = []
            for reference in group.references:
                target = await self._existing_target(reference)
                if target is None:
                    target = await self._acquire_target(
                        reference,
                        github_source=github_source,
                        github_adapter=github_adapter,
                        parent_run_id=parent_run_id,
                    )
                if target is None:
                    continue
                relation_candidates.append(
                    RelationCandidate(
                        relation_type="references-development-object",
                        target=target,
                        qualifier={
                            "reference_url": reference.url,
                            "reference_kind": reference.object_type,
                        },
                        locator=cast(dict[str, JsonValue], group.evidence.locator),
                    )
                )

            if not relation_candidates:
                continue
            source = self._sources[group.source_id]
            observation = EvidenceAnchor(
                observation_id=group.evidence.observation_id,
                artifact_id=group.evidence.artifact_id,
            )
            candidate = EnrichmentCandidate(
                relations=relation_candidates,
                replace_relation_types=["references-development-object"],
            )
            async with self._session_factory() as session, session.begin():
                result = await self._writer.apply(
                    session,
                    root_object_id=view.object_id,
                    source=source,
                    observation=observation,
                    candidate=candidate,
                    processor_name=self.PROCESSOR_NAME,
                    processor_version=self.PROCESSOR_VERSION,
                    origin="deterministic_derived",
                )
            results.append(result)
        return results

    async def _existing_target(
        self,
        reference: GitHubDevelopmentReference,
    ) -> ObjectCandidate | None:
        identity = _reference_identity(reference)
        if identity is None:
            return None
        namespace, value = identity
        async with self._session_factory() as session:
            view = await get_object_by_identifier(session, namespace, value)
        return _object_candidate(view) if view is not None else None

    async def _acquire_target(
        self,
        reference: GitHubDevelopmentReference,
        *,
        github_source: SourceDefinition,
        github_adapter: SourceAdapter,
        parent_run_id: str | None,
    ) -> ObjectCandidate | None:
        envelopes = await self._acquisition.query(
            github_source,
            github_adapter,
            QuerySpec(filters=reference.filters),
            parent_run_id=parent_run_id,
        )
        for envelope in envelopes:
            mapped = self._mapper.map(envelope)
            if mapped.root_object is None:
                continue
            async with self._session_factory() as session, session.begin():
                await self._structured.ingest(session, github_source, envelope)
            return mapped.root_object
        return None


def parse_github_development_reference(url: str) -> GitHubDevelopmentReference | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in {
        "github.com",
        "www.github.com",
    }:
        return None
    parts = [unquote(item) for item in parsed.path.split("/") if item]
    if len(parts) < 4:
        return None
    full_name = f"{parts[0]}/{parts[1]}"
    marker = parts[2]
    value = parts[3]
    base: dict[str, JsonValue] = {"repo_full_name": full_name}
    if marker == "issues" and value.isdigit():
        return GitHubDevelopmentReference(
            url=url,
            repo_full_name=full_name,
            object_type="issue",
            filters={**base, "object_type": "issue", "issue_number": int(value)},
        )
    if marker == "pull" and value.isdigit():
        return GitHubDevelopmentReference(
            url=url,
            repo_full_name=full_name,
            object_type="pull_request",
            filters={**base, "object_type": "pull_request", "pull_number": int(value)},
        )
    if marker == "commit" and value:
        return GitHubDevelopmentReference(
            url=url,
            repo_full_name=full_name,
            object_type="commit",
            filters={**base, "object_type": "commit", "commit_sha": value},
        )
    if marker == "releases" and value == "tag" and len(parts) >= 5:
        tag = "/".join(parts[4:])
        return GitHubDevelopmentReference(
            url=url,
            repo_full_name=full_name,
            object_type="release",
            filters={**base, "object_type": "release", "tag": tag},
        )
    return None


def _reference_groups(
    claims: list[ClaimView],
    allowed_repos: set[str],
) -> list[_EvidenceGroup]:
    grouped: dict[tuple[str, str], tuple[EvidenceRef, dict[str, GitHubDevelopmentReference]]] = {}
    for claim in claims:
        if claim.predicate not in {"references", "github_references"}:
            continue
        urls = _claim_urls(claim.value)
        if not urls:
            continue
        for evidence in claim.evidence:
            key = (evidence.source_id, evidence.observation_id)
            if key not in grouped:
                grouped[key] = (evidence, {})
            refs = grouped[key][1]
            for url in urls:
                reference = parse_github_development_reference(url)
                if reference is None or reference.repo_full_name not in allowed_repos:
                    continue
                refs[reference.url] = reference
    return [
        _EvidenceGroup(source_id=source_id, evidence=evidence, references=tuple(refs.values()))
        for (source_id, _), (evidence, refs) in grouped.items()
        if refs
    ]


def _claim_urls(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _configured_repos(source: SourceDefinition) -> set[str]:
    value = source.discovery_method.get("repos")
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str) and item}


def _reference_identity(
    reference: GitHubDevelopmentReference,
) -> tuple[str, str] | None:
    filters = reference.filters
    if reference.object_type == "pull_request":
        number = filters.get("pull_number")
        if isinstance(number, int):
            return "github_pull_request", f"{reference.repo_full_name}#{number}"
    if reference.object_type == "issue":
        number = filters.get("issue_number")
        if isinstance(number, int):
            return "github_issue", f"{reference.repo_full_name}#{number}"
    if reference.object_type == "commit":
        sha = filters.get("commit_sha")
        if isinstance(sha, str) and sha:
            return "git_commit_sha", sha
    if reference.object_type == "release":
        tag = filters.get("tag")
        if isinstance(tag, str) and tag:
            return "github_release_tag", f"{reference.repo_full_name}@{tag}"
    return None


def _object_candidate(view: KnowledgeObjectView) -> ObjectCandidate:
    return ObjectCandidate(
        object_type=view.object_type,
        canonical_key=view.canonical_key,
        properties=cast(dict[str, JsonValue], dict(view.properties)),
        identifiers={key: list(values) for key, values in view.external_identifiers.items()},
    )
