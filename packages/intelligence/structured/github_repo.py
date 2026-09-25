from __future__ import annotations

from typing import Any

from pydantic import JsonValue

from packages.intelligence.knowledge.contracts import (
    ClaimCandidate,
    EnrichmentCandidate,
    ObjectCandidate,
)
from packages.sources.contracts import IngestEnvelope
from packages.sources.errors import SourceSchemaChanged


class GitHubRepoMapper:
    PROCESSOR_NAME = "github-repo-normalizer"
    PROCESSOR_VERSION = "1"

    def map(self, envelope: IngestEnvelope) -> EnrichmentCandidate:
        payload = envelope.json_payload
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
                claims.append(
                    ClaimCandidate(
                        predicate=predicate,
                        value=value,
                        locator={"kind": "jsonpath", "path": f"$.{field}"},
                    )
                )
        license_data = payload.get("license")
        if isinstance(license_data, dict):
            spdx = license_data.get("spdx_id")
            if isinstance(spdx, str) and spdx:
                claims.append(
                    ClaimCandidate(
                        predicate="github_license_spdx",
                        value=spdx,
                        locator={"kind": "jsonpath", "path": "$.license.spdx_id"},
                    )
                )
        return EnrichmentCandidate(
            root_object=ObjectCandidate(
                object_type="Repo",
                canonical_key=f"github:{full_name.lower()}",
                properties=properties,
                identifiers=identifiers,
            ),
            claims=claims,
            replace_predicates=[
                "github_default_branch",
                "github_archived",
                "github_visibility",
                "github_stargazers_count",
                "github_forks_count",
                "github_open_issues_count",
                "github_language",
                "github_created_at",
                "github_updated_at",
                "github_pushed_at",
                "github_license_spdx",
            ],
        )


def _json_scalar(value: Any) -> JsonValue | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return None
