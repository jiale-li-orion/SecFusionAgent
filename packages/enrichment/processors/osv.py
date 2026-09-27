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
    PROCESSOR_VERSION = "2"

    def map(self, envelope: IngestEnvelope) -> EnrichmentCandidate:
        payload = envelope.json_payload
        vulnerability_id = payload.get("id")
        if not isinstance(vulnerability_id, str):
            raise SourceSchemaChanged("OSV payload has no id")
        identifiers: dict[str, list[str]] = {"osv": [vulnerability_id]}
        if vulnerability_id.startswith("CVE-"):
            identifiers.setdefault("cve", []).append(vulnerability_id.upper())
        elif vulnerability_id.startswith("GHSA-"):
            identifiers.setdefault("ghsa", []).append(vulnerability_id)
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
                applicability = _applicability_relation(item, index)
                if applicability is not None:
                    relations.append(applicability)
                relations.extend(_fixed_version_relations(item, index))
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
            replace_relation_types=["affects-package", "applicability-status", "fixed-version"],
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


def _applicability_relation(value: Any, index: int) -> RelationCandidate | None:
    package_target = _package_target(value)
    if package_target is None:
        return None
    qualifier: dict[str, Any] = {
        "state": "affected",
        "source_semantics": "osv_range",
    }
    if isinstance(value, dict):
        ranges = value.get("ranges")
        versions = value.get("versions")
        if isinstance(ranges, list):
            qualifier["ranges"] = ranges
        if isinstance(versions, list):
            qualifier["versions"] = versions
    return RelationCandidate(
        relation_type="applicability-status",
        target=package_target,
        qualifier=qualifier,
        locator={"kind": "jsonpath", "path": f"$.affected[{index}]"},
    )


def _fixed_version_relations(value: Any, index: int) -> list[RelationCandidate]:
    if not isinstance(value, dict):
        return []
    package = value.get("package")
    if not isinstance(package, dict):
        return []
    name = package.get("name")
    ecosystem = package.get("ecosystem")
    if not isinstance(name, str) or not isinstance(ecosystem, str):
        return []
    ranges = value.get("ranges")
    if not isinstance(ranges, list):
        return []
    result: list[RelationCandidate] = []
    seen: set[str] = set()
    for range_index, range_item in enumerate(ranges):
        if not isinstance(range_item, dict):
            continue
        range_type = range_item.get("type")
        if range_type not in {"ECOSYSTEM", "SEMVER"}:
            continue
        events = range_item.get("events")
        if not isinstance(events, list):
            continue
        for event_index, event in enumerate(events):
            if not isinstance(event, dict):
                continue
            fixed = event.get("fixed")
            if not isinstance(fixed, str) or not fixed or fixed in seen:
                continue
            seen.add(fixed)
            ecosystem_key = ecosystem.lower()
            name_key = name.lower()
            result.append(
                RelationCandidate(
                    relation_type="fixed-version",
                    target=ObjectCandidate(
                        object_type="SoftwareVersion",
                        canonical_key=(f"software-version:{ecosystem_key}:{name_key}:{fixed}"),
                        properties={
                            "version": fixed,
                            "package_name": name,
                            "ecosystem": ecosystem,
                        },
                        identifiers={"package_version": [f"{ecosystem_key}:{name_key}@{fixed}"]},
                    ),
                    qualifier={
                        "ecosystem": ecosystem,
                        "package_name": name,
                        "range_type": range_type,
                    },
                    locator={
                        "kind": "jsonpath",
                        "path": (
                            f"$.affected[{index}].ranges[{range_index}].events[{event_index}].fixed"
                        ),
                    },
                )
            )
    return result


def _package_target(value: Any) -> ObjectCandidate | None:
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
    return ObjectCandidate(
        object_type="Package",
        canonical_key=f"package:{ecosystem.lower()}:{name.lower()}",
        properties={"name": name, "ecosystem": ecosystem},
        identifiers=identifiers,
    )


def _json_value(value: Any) -> str | int | float | bool | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
