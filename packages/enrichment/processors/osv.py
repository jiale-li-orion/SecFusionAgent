from __future__ import annotations

from typing import Any

from packages.intelligence.knowledge.contracts import (
    ClaimCandidate,
    EnrichmentCandidate,
    ObjectCandidate,
    RelationCandidate,
)
from packages.sources.contracts import IngestEnvelope
from packages.sources.errors import SourceSchemaChanged


class OSVMapper:
    PROCESSOR_NAME = "osv-enrichment"
    PROCESSOR_VERSION = "1"

    def map(self, envelope: IngestEnvelope) -> EnrichmentCandidate:
        payload = envelope.json_payload
        vulnerability_id = payload.get("id")
        if not isinstance(vulnerability_id, str):
            raise SourceSchemaChanged("OSV payload has no id")
        identifiers: dict[str, list[str]] = {"osv": [vulnerability_id]}
        aliases = payload.get("aliases")
        if isinstance(aliases, list):
            for alias in aliases:
                if not isinstance(alias, str):
                    continue
                if alias.startswith("CVE-"):
                    identifiers.setdefault("cve", []).append(alias.upper())
                elif alias.startswith("GHSA-"):
                    identifiers.setdefault("ghsa", []).append(alias)

        claims: list[ClaimCandidate] = []
        for predicate, field in [
            ("osv_summary", "summary"),
            ("osv_details", "details"),
            ("osv_modified", "modified"),
            ("osv_published", "published"),
            ("osv_withdrawn", "withdrawn"),
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

        relations: list[RelationCandidate] = []
        affected = payload.get("affected")
        if isinstance(affected, list):
            for index, item in enumerate(affected):
                relation = _affected_relation(item, index)
                if relation is not None:
                    relations.append(relation)
        return EnrichmentCandidate(
            root_identifiers=identifiers,
            claims=claims,
            relations=relations,
            replace_predicates=[
                "osv_summary",
                "osv_details",
                "osv_modified",
                "osv_published",
                "osv_withdrawn",
            ],
            replace_relation_types=["affects-package"],
        )


def _affected_relation(value: Any, index: int) -> RelationCandidate | None:
    if not isinstance(value, dict):
        return None
    package = value.get("package")
    if not isinstance(package, dict):
        return None
    name = package.get("name")
    ecosystem = package.get("ecosystem")
    if not isinstance(name, str) or not isinstance(ecosystem, str):
        return None
    purl = package.get("purl")
    identifiers = {"purl": [purl]} if isinstance(purl, str) else {}
    qualifier: dict[str, Any] = {"ecosystem": ecosystem}
    versions = value.get("versions")
    ranges = value.get("ranges")
    if isinstance(versions, list):
        qualifier["versions"] = versions
    if isinstance(ranges, list):
        qualifier["ranges"] = ranges
    return RelationCandidate(
        relation_type="affects-package",
        target=ObjectCandidate(
            object_type="Package",
            canonical_key=f"package:{ecosystem.lower()}:{name.lower()}",
            properties={"name": name, "ecosystem": ecosystem},
            identifiers=identifiers,
        ),
        qualifier=qualifier,
        locator={"kind": "jsonpath", "path": f"$.affected[{index}]"},
    )


def _json_value(value: Any) -> str | int | float | bool | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
