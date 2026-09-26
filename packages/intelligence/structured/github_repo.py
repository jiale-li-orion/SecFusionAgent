from __future__ import annotations

from typing import Any

from pydantic import JsonValue

from packages.intelligence.knowledge.contracts import (
    ClaimCandidate,
    EnrichmentCandidate,
    ObjectCandidate,
    RelationCandidate,
)
from packages.sources.contracts import IngestEnvelope
from packages.sources.errors import SourceSchemaChanged


class GitHubRepoMapper:
    PROCESSOR_NAME = "github-structured-normalizer"
    PROCESSOR_VERSION = "2"

    def map(self, envelope: IngestEnvelope) -> EnrichmentCandidate:
        object_type = envelope.request_metadata.get("object_type", "repository")
        if object_type == "repository":
            return _map_repository(envelope.json_payload)
        repo_full_name = envelope.request_metadata.get("repo_full_name")
        if not isinstance(repo_full_name, str) or not repo_full_name:
            raise SourceSchemaChanged("GitHub development object has no repo_full_name metadata")
        if object_type == "issue":
            return _map_issue(repo_full_name, envelope.json_payload)
        if object_type == "pull_request":
            return _map_pull_request(repo_full_name, envelope.json_payload)
        if object_type == "commit":
            return _map_commit(repo_full_name, envelope.json_payload)
        if object_type == "release":
            return _map_release(repo_full_name, envelope.json_payload)
        raise SourceSchemaChanged(f"unsupported GitHub structured object_type={object_type!r}")


def _map_repository(payload: dict[str, Any]) -> EnrichmentCandidate:
    full_name = payload.get("full_name")
    if not isinstance(full_name, str) or not full_name:
        raise SourceSchemaChanged("GitHub repo payload has no full_name")
    provider_id = payload.get("id")
    identifiers: dict[str, list[str]] = {"github_repo": [full_name]}
    if isinstance(provider_id, int):
        identifiers["github_repo_id"] = [str(provider_id)]
    node_id = payload.get("node_id")
    if isinstance(node_id, str) and node_id:
        identifiers["github_node_id"] = [node_id]

    owner = payload.get("owner")
    owner_login = owner.get("login") if isinstance(owner, dict) else None
    properties: dict[str, JsonValue] = {
        "full_name": full_name,
        "name": payload.get("name") if isinstance(payload.get("name"), str) else full_name,
    }
    if isinstance(owner_login, str):
        properties["owner"] = owner_login
    html_url = payload.get("html_url")
    if isinstance(html_url, str):
        properties["html_url"] = html_url

    claims: list[ClaimCandidate] = []
    for predicate, field in [
        ("github_default_branch", "default_branch"),
        ("github_archived", "archived"),
        ("github_visibility", "visibility"),
        ("github_stargazers_count", "stargazers_count"),
        ("github_forks_count", "forks_count"),
        ("github_open_issues_count", "open_issues_count"),
        ("github_language", "language"),
        ("github_created_at", "created_at"),
        ("github_updated_at", "updated_at"),
        ("github_pushed_at", "pushed_at"),
    ]:
        value = _json_scalar(payload.get(field))
        if value is not None:
            claims.append(_claim(predicate, value, f"$.{field}"))
    license_data = payload.get("license")
    if isinstance(license_data, dict):
        spdx = license_data.get("spdx_id")
        if isinstance(spdx, str) and spdx:
            claims.append(_claim("github_license_spdx", spdx, "$.license.spdx_id"))
    return EnrichmentCandidate(
        root_object=ObjectCandidate(
            object_type="Repo",
            canonical_key=_repo_key(full_name),
            properties=properties,
            identifiers=identifiers,
        ),
        claims=claims,
        replace_predicates=[item.predicate for item in claims]
        + (
            ["github_license_spdx"]
            if not any(c.predicate == "github_license_spdx" for c in claims)
            else []
        ),
    )


def _map_issue(full_name: str, payload: dict[str, Any]) -> EnrichmentCandidate:
    number = _required_int(payload, "number", "issue")
    issue_id = payload.get("id")
    identifiers = {"github_issue": [f"{full_name}#{number}"]}
    if isinstance(issue_id, int):
        identifiers["github_issue_id"] = [str(issue_id)]
    node_id = payload.get("node_id")
    if isinstance(node_id, str) and node_id:
        identifiers["github_node_id"] = [node_id]
    root = ObjectCandidate(
        object_type="Issue",
        canonical_key=f"github:{full_name.lower()}:issue:{number}",
        properties=_common_numbered_properties(full_name, number, payload),
        identifiers=identifiers,
    )
    claims = _common_issue_claims(payload)
    return EnrichmentCandidate(
        root_object=root,
        claims=claims,
        relations=[_belongs_to_repo(full_name)],
        replace_predicates=[item.predicate for item in claims],
        replace_relation_types=["belongs-to-repo"],
    )


def _map_pull_request(full_name: str, payload: dict[str, Any]) -> EnrichmentCandidate:
    number = _required_int(payload, "number", "pull request")
    pull_id = payload.get("id")
    identifiers = {"github_pull_request": [f"{full_name}#{number}"]}
    if isinstance(pull_id, int):
        identifiers["github_pull_request_id"] = [str(pull_id)]
    node_id = payload.get("node_id")
    if isinstance(node_id, str) and node_id:
        identifiers["github_node_id"] = [node_id]
    root = ObjectCandidate(
        object_type="PullRequest",
        canonical_key=f"github:{full_name.lower()}:pull:{number}",
        properties=_common_numbered_properties(full_name, number, payload),
        identifiers=identifiers,
    )
    claims = _common_issue_claims(payload)
    for predicate, field in [
        ("github_merged", "merged"),
        ("github_merged_at", "merged_at"),
        ("github_mergeable_state", "mergeable_state"),
    ]:
        value = _json_scalar(payload.get(field))
        if value is not None:
            claims.append(_claim(predicate, value, f"$.{field}"))
    relations = [_belongs_to_repo(full_name)]
    merge_sha = payload.get("merge_commit_sha")
    if isinstance(merge_sha, str) and merge_sha:
        relations.append(
            RelationCandidate(
                relation_type="merged-as",
                target=_commit_object(full_name, merge_sha),
                locator={"kind": "jsonpath", "path": "$.merge_commit_sha"},
            )
        )
    head = payload.get("head")
    if isinstance(head, dict):
        head_sha = head.get("sha")
        if isinstance(head_sha, str) and head_sha:
            relations.append(
                RelationCandidate(
                    relation_type="head-commit",
                    target=_commit_object(full_name, head_sha),
                    locator={"kind": "jsonpath", "path": "$.head.sha"},
                )
            )
    return EnrichmentCandidate(
        root_object=root,
        claims=claims,
        relations=relations,
        replace_predicates=[item.predicate for item in claims],
        replace_relation_types=["belongs-to-repo", "merged-as", "head-commit"],
    )


def _map_commit(full_name: str, payload: dict[str, Any]) -> EnrichmentCandidate:
    sha = payload.get("sha")
    if not isinstance(sha, str) or not sha:
        raise SourceSchemaChanged("GitHub commit payload has no sha")
    properties: dict[str, JsonValue] = {"sha": sha}
    html_url = payload.get("html_url")
    if isinstance(html_url, str):
        properties["html_url"] = html_url
    root = _commit_object(full_name, sha, properties=properties)
    claims: list[ClaimCandidate] = []
    commit = payload.get("commit")
    if isinstance(commit, dict):
        message = commit.get("message")
        if isinstance(message, str):
            claims.append(_claim("github_commit_message", message, "$.commit.message"))
        for actor, prefix in (("author", "author"), ("committer", "committer")):
            value = commit.get(actor)
            if isinstance(value, dict):
                name = value.get("name")
                date = value.get("date")
                if isinstance(name, str):
                    claims.append(
                        _claim(f"github_commit_{prefix}_name", name, f"$.commit.{actor}.name")
                    )
                if isinstance(date, str):
                    claims.append(
                        _claim(f"github_commit_{prefix}_date", date, f"$.commit.{actor}.date")
                    )
    relations = [_belongs_to_repo(full_name)]
    parents = payload.get("parents")
    if isinstance(parents, list):
        for index, parent in enumerate(parents):
            if not isinstance(parent, dict):
                continue
            parent_sha = parent.get("sha")
            if isinstance(parent_sha, str) and parent_sha:
                relations.append(
                    RelationCandidate(
                        relation_type="has-parent-commit",
                        target=_commit_object(full_name, parent_sha),
                        locator={"kind": "jsonpath", "path": f"$.parents[{index}].sha"},
                    )
                )
    return EnrichmentCandidate(
        root_object=root,
        claims=claims,
        relations=relations,
        replace_predicates=[item.predicate for item in claims],
        replace_relation_types=["belongs-to-repo", "has-parent-commit"],
    )


def _map_release(full_name: str, payload: dict[str, Any]) -> EnrichmentCandidate:
    release_id = _required_int(payload, "id", "release")
    tag_name = payload.get("tag_name")
    if not isinstance(tag_name, str) or not tag_name:
        raise SourceSchemaChanged("GitHub release payload has no tag_name")
    identifiers: dict[str, list[str]] = {
        "github_release_id": [str(release_id)],
        "github_release_tag": [f"{full_name}@{tag_name}"],
    }
    node_id = payload.get("node_id")
    if isinstance(node_id, str) and node_id:
        identifiers["github_node_id"] = [node_id]
    properties: dict[str, JsonValue] = {
        "repo_full_name": full_name,
        "tag_name": tag_name,
    }
    html_url = payload.get("html_url")
    if isinstance(html_url, str):
        properties["html_url"] = html_url
    root = ObjectCandidate(
        object_type="Release",
        canonical_key=f"github:{full_name.lower()}:release:{release_id}",
        properties=properties,
        identifiers=identifiers,
    )
    claims: list[ClaimCandidate] = []
    for predicate, field in [
        ("github_release_tag", "tag_name"),
        ("github_release_name", "name"),
        ("github_release_target_commitish", "target_commitish"),
        ("github_release_draft", "draft"),
        ("github_release_prerelease", "prerelease"),
        ("github_release_created_at", "created_at"),
        ("github_release_published_at", "published_at"),
    ]:
        value = _json_scalar(payload.get(field))
        if value is not None:
            claims.append(_claim(predicate, value, f"$.{field}"))
    return EnrichmentCandidate(
        root_object=root,
        claims=claims,
        relations=[_belongs_to_repo(full_name)],
        replace_predicates=[item.predicate for item in claims],
        replace_relation_types=["belongs-to-repo"],
    )


def _common_numbered_properties(
    full_name: str,
    number: int,
    payload: dict[str, Any],
) -> dict[str, JsonValue]:
    properties: dict[str, JsonValue] = {"repo_full_name": full_name, "number": number}
    title = payload.get("title")
    if isinstance(title, str):
        properties["title"] = title
    html_url = payload.get("html_url")
    if isinstance(html_url, str):
        properties["html_url"] = html_url
    return properties


def _common_issue_claims(payload: dict[str, Any]) -> list[ClaimCandidate]:
    claims: list[ClaimCandidate] = []
    for predicate, field in [
        ("github_title", "title"),
        ("github_state", "state"),
        ("github_created_at", "created_at"),
        ("github_updated_at", "updated_at"),
        ("github_closed_at", "closed_at"),
    ]:
        value = _json_scalar(payload.get(field))
        if value is not None:
            claims.append(_claim(predicate, value, f"$.{field}"))
    return claims


def _repo_object(full_name: str) -> ObjectCandidate:
    return ObjectCandidate(
        object_type="Repo",
        canonical_key=_repo_key(full_name),
        properties={"full_name": full_name},
        identifiers={"github_repo": [full_name]},
    )


def _commit_object(
    full_name: str,
    sha: str,
    *,
    properties: dict[str, JsonValue] | None = None,
) -> ObjectCandidate:
    base_properties: dict[str, JsonValue] = {"sha": sha}
    if properties:
        base_properties.update(properties)
    return ObjectCandidate(
        object_type="Commit",
        canonical_key=f"git:commit:{sha.lower()}",
        properties=base_properties,
        identifiers={"git_commit_sha": [sha]},
    )


def _belongs_to_repo(full_name: str) -> RelationCandidate:
    return RelationCandidate(
        relation_type="belongs-to-repo",
        target=_repo_object(full_name),
        locator={"kind": "request_metadata", "path": "$.repo_full_name"},
    )


def _repo_key(full_name: str) -> str:
    return f"github:{full_name.lower()}"


def _claim(predicate: str, value: JsonValue, path: str) -> ClaimCandidate:
    return ClaimCandidate(
        predicate=predicate,
        value=value,
        locator={"kind": "jsonpath", "path": path},
    )


def _required_int(payload: dict[str, Any], field: str, label: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int):
        raise SourceSchemaChanged(f"GitHub {label} payload has no numeric {field}")
    return value


def _json_scalar(value: Any) -> JsonValue | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return None
