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
    PROCESSOR_VERSION = "4"

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

        epss = payload.get("epss")
        if isinstance(epss, dict):
            probability = epss.get("percentage")
            percentile = epss.get("percentile")
            if isinstance(probability, (int, float)) and not isinstance(probability, bool):
                claims.append(
                    ClaimCandidate(
                        predicate="epss_probability",
                        value=float(probability),
                        locator={"kind": "jsonpath", "path": "$.epss.percentage"},
                    )
                )
            if isinstance(percentile, (int, float)) and not isinstance(percentile, bool):
                claims.append(
                    ClaimCandidate(
                        predicate="epss_percentile",
                        value=float(percentile),
                        locator={"kind": "jsonpath", "path": "$.epss.percentile"},
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
        relations.append(_advisory_relation(payload, ghsa_id))
        vulnerabilities = payload.get("vulnerabilities")
        if isinstance(vulnerabilities, list):
            for index, item in enumerate(vulnerabilities):
                relation = _package_relation(item, index)
                if relation is not None:
                    relations.append(relation)
                applicability = _applicability_relation(item, index)
                if applicability is not None:
                    relations.append(applicability)
                fixed = _fixed_version_relation(item, index)
                if fixed is not None:
                    relations.append(fixed)
        if isinstance(cwes, list):
            relations.extend(_weakness_relations(cwes))
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
                "epss_probability",
                "epss_percentile",
            ],
            replace_relation_types=[
                "affects-package",
                "applicability-status",
                "fixed-version",
                "has-weakness",
                "described-by",
            ],
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
    patched = _first_patched_version(value.get("first_patched_version"))
    if patched is not None:
        qualifier["first_patched_version"] = patched
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


def _applicability_relation(value: Any, index: int) -> RelationCandidate | None:
    if not isinstance(value, dict):
        return None
    package = value.get("package")
    vulnerable_range = value.get("vulnerable_version_range")
    if not isinstance(package, dict) or not isinstance(vulnerable_range, str):
        return None
    ecosystem = package.get("ecosystem")
    name = package.get("name")
    if not isinstance(ecosystem, str) or not isinstance(name, str):
        return None
    return RelationCandidate(
        relation_type="applicability-status",
        target=ObjectCandidate(
            object_type="Package",
            canonical_key=f"package:{ecosystem.lower()}:{name.lower()}",
            properties={"name": name, "ecosystem": ecosystem},
        ),
        qualifier={
            "state": "affected",
            "source_semantics": "github_advisory_range",
            "version_range": vulnerable_range,
        },
        locator={
            "kind": "jsonpath",
            "path": f"$.vulnerabilities[{index}].vulnerable_version_range",
        },
    )


def _advisory_relation(payload: dict[str, Any], ghsa_id: str) -> RelationCandidate:
    properties: dict[str, JsonValue] = {
        "document_kind": "github_advisory",
        "ghsa_id": ghsa_id,
    }
    html_url = payload.get("html_url")
    if isinstance(html_url, str) and html_url:
        properties["url"] = html_url
    return RelationCandidate(
        relation_type="described-by",
        target=ObjectCandidate(
            object_type="Document",
            canonical_key=f"document:github-advisory:{ghsa_id.lower()}",
            properties=properties,
        ),
        locator={"kind": "jsonpath", "path": "$.ghsa_id"},
    )


def _fixed_version_relation(value: Any, index: int) -> RelationCandidate | None:
    if not isinstance(value, dict):
        return None
    package = value.get("package")
    if not isinstance(package, dict):
        return None
    ecosystem = package.get("ecosystem")
    name = package.get("name")
    patched = _first_patched_version(value.get("first_patched_version"))
    if (
        not isinstance(ecosystem, str)
        or not isinstance(name, str)
        or patched is None
    ):
        return None
    ecosystem_key = ecosystem.lower()
    name_key = name.lower()
    return RelationCandidate(
        relation_type="fixed-version",
        target=ObjectCandidate(
            object_type="SoftwareVersion",
            canonical_key=f"software-version:{ecosystem_key}:{name_key}:{patched}",
            properties={
                "version": patched,
                "package_name": name,
                "ecosystem": ecosystem,
            },
            identifiers={
                "package_version": [f"{ecosystem_key}:{name_key}@{patched}"]
            },
        ),
        qualifier={"ecosystem": ecosystem, "package_name": name},
        locator={
            "kind": "jsonpath",
            "path": f"$.vulnerabilities[{index}].first_patched_version",
        },
    )


def _weakness_relations(cwes: list[Any]) -> list[RelationCandidate]:
    result: list[RelationCandidate] = []
    seen: set[str] = set()
    for index, item in enumerate(cwes):
        if not isinstance(item, dict):
            continue
        value = item.get("cwe_id")
        if not isinstance(value, str) or not value.startswith("CWE-"):
            continue
        cwe_id = value.upper()
        if cwe_id in seen:
            continue
        seen.add(cwe_id)
        properties: dict[str, JsonValue] = {"cwe_id": cwe_id}
        name = item.get("name")
        if isinstance(name, str):
            properties["name"] = name
        result.append(
            RelationCandidate(
                relation_type="has-weakness",
                target=ObjectCandidate(
                    object_type="Weakness",
                    canonical_key=f"weakness:{cwe_id}",
                    properties=properties,
                    identifiers={"cwe": [cwe_id]},
                ),
                locator={"kind": "jsonpath", "path": f"$.cwes[{index}]"},
            )
        )
    return result


def _first_patched_version(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, dict):
        identifier = value.get("identifier")
        if isinstance(identifier, str) and identifier:
            return identifier
    return None


def _json_value(value: Any) -> str | int | float | bool | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
