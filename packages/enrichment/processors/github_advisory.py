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


class GitHubAdvisoryMapper:
    PROCESSOR_NAME = "github-advisory-enrichment"
    PROCESSOR_VERSION = "1"

    def map(self, envelope: IngestEnvelope) -> EnrichmentCandidate:
        payload = envelope.json_payload
        ghsa_id = payload.get("ghsa_id")
        if not isinstance(ghsa_id, str):
            raise SourceSchemaChanged("GitHub advisory has no ghsa_id")
        identifiers: dict[str, list[str]] = {"ghsa": [ghsa_id]}
        cve_id = payload.get("cve_id")
        if isinstance(cve_id, str) and cve_id:
            identifiers["cve"] = [cve_id.upper()]

        claims: list[ClaimCandidate] = []
        for predicate, field in [
            ("github_severity", "severity"),
            ("github_summary", "summary"),
            ("github_description", "description"),
            ("github_published_at", "published_at"),
            ("github_updated_at", "updated_at"),
            ("github_withdrawn_at", "withdrawn_at"),
        ]:
            value = _json_value(payload.get(field))
            if value is not None:
                claims.append(
                    ClaimCandidate(
                        predicate=predicate,
                        value=value,
                        locator={"kind": "jsonpath", "path": f"$.{field}"},
                    )
                )

        cwes = payload.get("cwes")
        if isinstance(cwes, list):
            values: list[JsonValue] = [
                item.get("cwe_id")
                for item in cwes
                if isinstance(item, dict) and isinstance(item.get("cwe_id"), str)
            ]
            if values:
                claims.append(
                    ClaimCandidate(
                        predicate="github_cwes",
                        value=values,
                        locator={"kind": "jsonpath", "path": "$.cwes"},
                    )
                )

        references = payload.get("references")
        if isinstance(references, list):
            urls: list[JsonValue] = [item for item in references if isinstance(item, str)]
            if urls:
                claims.append(
                    ClaimCandidate(
                        predicate="github_references",
                        value=urls,
                        locator={"kind": "jsonpath", "path": "$.references"},
                    )
                )

        relations: list[RelationCandidate] = []
        vulnerabilities = payload.get("vulnerabilities")
        if isinstance(vulnerabilities, list):
            for index, item in enumerate(vulnerabilities):
                relation = _package_relation(item, index)
                if relation is not None:
                    relations.append(relation)
        return EnrichmentCandidate(
            root_identifiers=identifiers,
            claims=claims,
            relations=relations,
            replace_predicates=[
                "github_severity",
                "github_summary",
                "github_description",
                "github_published_at",
                "github_updated_at",
                "github_withdrawn_at",
                "github_cwes",
                "github_references",
            ],
            replace_relation_types=["affects-package"],
        )


def _package_relation(value: Any, index: int) -> RelationCandidate | None:
    if not isinstance(value, dict):
        return None
    package = value.get("package")
    if not isinstance(package, dict):
        return None
    ecosystem = package.get("ecosystem")
    name = package.get("name")
    if not isinstance(ecosystem, str) or not isinstance(name, str):
        return None
    qualifier: dict[str, Any] = {"ecosystem": ecosystem}
    vulnerable_range = value.get("vulnerable_version_range")
    if isinstance(vulnerable_range, str):
        qualifier["vulnerable_version_range"] = vulnerable_range
    patched = value.get("first_patched_version")
    if isinstance(patched, dict) and isinstance(patched.get("identifier"), str):
        qualifier["first_patched_version"] = patched["identifier"]
    return RelationCandidate(
        relation_type="affects-package",
        target=ObjectCandidate(
            object_type="Package",
            canonical_key=f"package:{ecosystem.lower()}:{name.lower()}",
            properties={"name": name, "ecosystem": ecosystem},
        ),
        qualifier=qualifier,
        locator={"kind": "jsonpath", "path": f"$.vulnerabilities[{index}]"},
    )


def _json_value(value: Any) -> str | int | float | bool | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
