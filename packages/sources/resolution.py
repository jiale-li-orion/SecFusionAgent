from __future__ import annotations

from ipaddress import ip_address
from typing import Literal, Protocol
from urllib.parse import urlparse, urlunparse

from pydantic import BaseModel, Field, JsonValue

from packages.sources.contracts import QuerySpec


class SourceResolutionRequest(BaseModel):
    query: str | None = None
    limit: int = Field(default=10, ge=1, le=50)
    candidate_urls: list[str] = Field(default_factory=list)
    cve_id: str | None = None
    ghsa_id: str | None = None
    repo_full_name: str | None = None
    object_type: (
        Literal[
            "repository",
            "issue",
            "pull_request",
            "commit",
            "release",
            "releases",
        ]
        | None
    ) = None
    issue_number: int | None = None
    pull_number: int | None = None
    commit_sha: str | None = None
    release_tag: str | None = None
    release_id: int | None = None
    context: dict[str, JsonValue] = Field(default_factory=dict)


class ProviderQueryTarget(BaseModel):
    source_id: str
    query_spec: QuerySpec
    reason: str


class DirectURLTarget(BaseModel):
    url: str
    source_role_hint: str
    source_class_hint: str
    reason: str


class SourceResolutionPlan(BaseModel):
    owner: str
    provider_queries: list[ProviderQueryTarget] = Field(default_factory=list)
    direct_urls: list[DirectURLTarget] = Field(default_factory=list)


class DynamicSourceResolver(Protocol):
    owner: str

    def resolve(self, request: SourceResolutionRequest) -> SourceResolutionPlan: ...


class PublicationResolver:
    owner = "publication_resolver"
    source_ids = (
        "crossref-search",
        "openalex-search",
        "openreview-search",
        "semantic-scholar-search",
    )

    def resolve(self, request: SourceResolutionRequest) -> SourceResolutionPlan:
        query = _required_query(request)
        return SourceResolutionPlan(
            owner=self.owner,
            provider_queries=[
                ProviderQueryTarget(
                    source_id=source_id,
                    query_spec=QuerySpec(filters={"query": query, "limit": request.limit}),
                    reason="resolve publication metadata across configured scholarly indexes",
                )
                for source_id in self.source_ids
            ],
        )


class CuratedPublicationResolver(PublicationResolver):
    owner = "curated_publication_resolver"

    def resolve(self, request: SourceResolutionRequest) -> SourceResolutionPlan:
        plan = super().resolve(request)
        plan.owner = self.owner
        plan.provider_queries = [
            target
            for target in plan.provider_queries
            if target.source_id
            in {"openreview-search", "semantic-scholar-search", "crossref-search"}
        ]
        return plan


class GitHubIncidentFollowupResolver:
    owner = "github_incident_followup_resolver"

    def resolve(self, request: SourceResolutionRequest) -> SourceResolutionPlan:
        targets: list[ProviderQueryTarget] = []
        advisory_filters: dict[str, JsonValue] = {}
        if request.cve_id:
            advisory_filters["cve_id"] = request.cve_id
        if request.ghsa_id:
            advisory_filters["ghsa_id"] = request.ghsa_id
        if advisory_filters:
            targets.append(
                ProviderQueryTarget(
                    source_id="github-global-advisories",
                    query_spec=QuerySpec(filters=advisory_filters),
                    reason=(
                        "refresh GitHub advisory state for the explicit vulnerability identifier"
                    ),
                )
            )

        if request.repo_full_name:
            filters: dict[str, JsonValue] = {
                "repo_full_name": request.repo_full_name,
                "object_type": request.object_type or "repository",
            }
            object_type = request.object_type or "repository"
            if object_type == "issue":
                filters["issue_number"] = _required_positive_int(
                    request.issue_number, "issue_number"
                )
            elif object_type == "pull_request":
                filters["pull_number"] = _required_positive_int(request.pull_number, "pull_number")
            elif object_type == "commit":
                if not request.commit_sha:
                    raise ValueError("commit follow-up requires commit_sha")
                filters["commit_sha"] = request.commit_sha
            elif object_type == "release":
                if request.release_tag:
                    filters["tag"] = request.release_tag
                elif request.release_id is not None:
                    filters["release_id"] = _required_positive_int(request.release_id, "release_id")
                else:
                    raise ValueError("release follow-up requires release_tag or release_id")
            elif object_type == "releases":
                filters["limit"] = request.limit
            targets.append(
                ProviderQueryTarget(
                    source_id="github-target-repos",
                    query_spec=QuerySpec(filters=filters),
                    reason="resolve explicit GitHub development evidence for the incident",
                )
            )

        if not targets:
            raise ValueError(
                "GitHub follow-up requires cve_id/ghsa_id and/or an explicit repository object"
            )
        return SourceResolutionPlan(owner=self.owner, provider_queries=targets)


class ExplicitURLResolver:
    def __init__(self, *, owner: str, source_role_hint: str, source_class_hint: str) -> None:
        self.owner = owner
        self._source_role_hint = source_role_hint
        self._source_class_hint = source_class_hint

    def resolve(self, request: SourceResolutionRequest) -> SourceResolutionPlan:
        if not request.candidate_urls:
            raise ValueError(f"{self.owner} requires explicit candidate_urls from investigation")
        seen: set[str] = set()
        targets: list[DirectURLTarget] = []
        for value in request.candidate_urls:
            url = _normalize_public_https_url(value)
            if url in seen:
                continue
            seen.add(url)
            targets.append(
                DirectURLTarget(
                    url=url,
                    source_role_hint=self._source_role_hint,
                    source_class_hint=self._source_class_hint,
                    reason=(
                        "normalize an explicit investigation-discovered URL; "
                        "the resolver does not decide whether to investigate it"
                    ),
                )
            )
        return SourceResolutionPlan(owner=self.owner, direct_urls=targets)


def _required_query(request: SourceResolutionRequest) -> str:
    if not request.query or not request.query.strip():
        raise ValueError("publication resolution requires a non-empty query")
    return request.query.strip()


def _required_positive_int(value: int | None, field: str) -> int:
    if value is None or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _normalize_public_https_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError("dynamic direct source URL must be public HTTPS")
    if parsed.username or parsed.password:
        raise ValueError("dynamic direct source URL must not contain userinfo")
    host = parsed.hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise ValueError("dynamic direct source URL must not target a local host")
    try:
        address = ip_address(host)
    except ValueError:
        address = None
    if address is not None and (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    ):
        raise ValueError("dynamic direct source URL must not target a non-public IP")
    netloc = host
    if parsed.port is not None:
        netloc = f"{host}:{parsed.port}"
    return urlunparse(("https", netloc, parsed.path or "/", "", parsed.query, ""))
