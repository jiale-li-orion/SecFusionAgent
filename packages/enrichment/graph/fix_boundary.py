from __future__ import annotations

import re
from dataclasses import dataclass
from typing import cast
from urllib.parse import urlparse

from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.knowledge.contracts import (
    EnrichmentCandidate,
    EvidenceAnchor,
    ObjectCandidate,
    RelationCandidate,
)
from packages.intelligence.knowledge.read import EvidenceRef, RelationView, get_vulnerability_by_cve
from packages.intelligence.knowledge.write import EvidenceBackedKnowledgeWriter
from packages.intelligence.normalization.canonical import NormalizationResult
from packages.intelligence.structured.github_repo import GitHubRepoMapper
from packages.intelligence.structured.service import StructuredIndexService
from packages.monitoring.acquisition.service import AcquisitionService
from packages.sources.contracts import QuerySpec, SourceAdapter, SourceDefinition

_GIT_SHA = re.compile(r"^[0-9a-fA-F]{7,64}$")


@dataclass(frozen=True, slots=True)
class GitFixBoundary:
    evidence: EvidenceRef
    provider_relation_id: str
    repo_full_name: str
    repo_url: str
    fixed_sha: str
    locator: dict[str, JsonValue]


class DeterministicFixBoundaryService:
    """Promote provider-declared GIT fix boundaries into durable commit relations."""

    PROCESSOR_NAME = "osv-git-fix-boundary"
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
        osv_source_id: str = "osv-vulnerabilities",
        github_source_id: str = "github-target-repos",
    ) -> None:
        self._session_factory = session_factory
        self._acquisition = acquisition
        self._writer = writer
        self._sources = sources
        self._adapters = adapters
        self._osv_source_id = osv_source_id
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
        osv_source = self._sources[self._osv_source_id]
        github_adapter = self._adapters[self._github_source_id]
        allowed_repos = _configured_repos(github_source)
        boundaries = extract_osv_git_fix_boundaries(
            view.relations,
            source_id=self._osv_source_id,
            allowed_repos=allowed_repos,
        )
        if not boundaries:
            return []

        grouped: dict[tuple[str, str | None], list[GitFixBoundary]] = {}
        for boundary in boundaries:
            key = (boundary.evidence.observation_id, boundary.evidence.artifact_id)
            grouped.setdefault(key, []).append(boundary)

        results: list[NormalizationResult] = []
        first_group = True
        for (observation_id, artifact_id), group in grouped.items():
            relation_candidates: list[RelationCandidate] = []
            seen_targets: set[tuple[str, str]] = set()
            for boundary in group:
                envelopes = await self._acquisition.query(
                    github_source,
                    github_adapter,
                    QuerySpec(
                        filters={
                            "repo_full_name": boundary.repo_full_name,
                            "object_type": "commit",
                            "commit_sha": boundary.fixed_sha,
                        }
                    ),
                    parent_run_id=parent_run_id,
                )
                for envelope in envelopes:
                    mapped = self._mapper.map(envelope)
                    target = mapped.root_object
                    if target is None or target.object_type != "Commit":
                        continue
                    async with self._session_factory() as session, session.begin():
                        await self._structured.ingest(session, github_source, envelope)
                    resolved_sha = _commit_sha(target) or boundary.fixed_sha
                    target_key = (boundary.repo_full_name, resolved_sha.lower())
                    if target_key in seen_targets:
                        continue
                    seen_targets.add(target_key)
                    relation_candidates.append(
                        RelationCandidate(
                            relation_type="fixed-by",
                            target=target,
                            qualifier={
                                "repo_full_name": boundary.repo_full_name,
                                "repo_url": boundary.repo_url,
                                "range_type": "GIT",
                                "provider_relation_id": boundary.provider_relation_id,
                                "requested_fixed_sha": boundary.fixed_sha,
                                "resolved_fixed_sha": resolved_sha,
                            },
                            locator=boundary.locator,
                        )
                    )

            if not relation_candidates:
                continue
            candidate = EnrichmentCandidate(
                relations=relation_candidates,
                replace_relation_types=["fixed-by"] if first_group else [],
            )
            first_group = False
            async with self._session_factory() as session, session.begin():
                result = await self._writer.apply(
                    session,
                    root_object_id=view.object_id,
                    source=osv_source,
                    observation=EvidenceAnchor(
                        observation_id=observation_id,
                        artifact_id=artifact_id,
                    ),
                    candidate=candidate,
                    processor_name=self.PROCESSOR_NAME,
                    processor_version=self.PROCESSOR_VERSION,
                    origin="deterministic_derived",
                )
            results.append(result)
        return results


def extract_osv_git_fix_boundaries(
    relations: list[RelationView],
    *,
    source_id: str,
    allowed_repos: set[str],
) -> list[GitFixBoundary]:
    boundaries: list[GitFixBoundary] = []
    seen: set[tuple[str, str, str]] = set()
    for relation in relations:
        if relation.relation_type != "affects-package":
            continue
        ranges = relation.qualifier.get("ranges")
        if not isinstance(ranges, list):
            continue
        evidence_items = [item for item in relation.evidence if item.source_id == source_id]
        if not evidence_items:
            continue
        for range_index, range_item in enumerate(ranges):
            if not isinstance(range_item, dict) or str(range_item.get("type", "")).upper() != "GIT":
                continue
            repo_url = range_item.get("repo")
            if not isinstance(repo_url, str):
                continue
            repo_full_name = _github_repo_full_name(repo_url)
            if repo_full_name is None or repo_full_name not in allowed_repos:
                continue
            events = range_item.get("events")
            if not isinstance(events, list):
                continue
            for event_index, event in enumerate(events):
                if not isinstance(event, dict):
                    continue
                fixed_sha = event.get("fixed")
                if not isinstance(fixed_sha, str) or _GIT_SHA.fullmatch(fixed_sha) is None:
                    continue
                for evidence in evidence_items:
                    key = (evidence.observation_id, repo_full_name, fixed_sha.lower())
                    if key in seen:
                        continue
                    seen.add(key)
                    locator = cast(dict[str, JsonValue], dict(evidence.locator))
                    base_path = locator.get("path")
                    if isinstance(base_path, str):
                        locator["path"] = (
                            f"{base_path}.ranges[{range_index}].events[{event_index}].fixed"
                        )
                    boundaries.append(
                        GitFixBoundary(
                            evidence=evidence,
                            provider_relation_id=relation.relation_id,
                            repo_full_name=repo_full_name,
                            repo_url=repo_url,
                            fixed_sha=fixed_sha,
                            locator=locator,
                        )
                    )
    return boundaries


def _github_repo_full_name(repo_url: str) -> str | None:
    parsed = urlparse(repo_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "github.com",
        "www.github.com",
    }:
        return None
    parts = [item for item in parsed.path.split("/") if item]
    if len(parts) != 2:
        return None
    owner, repo = parts
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo:
        return None
    return f"{owner}/{repo}"


def _configured_repos(source: SourceDefinition) -> set[str]:
    value = source.discovery_method.get("repos")
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str) and item}


def _commit_sha(target: ObjectCandidate) -> str | None:
    values = target.identifiers.get("git_commit_sha")
    if not values:
        return None
    return values[0]
