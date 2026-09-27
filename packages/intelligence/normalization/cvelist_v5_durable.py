from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from hashlib import sha256
from typing import Any, cast
from urllib.parse import unquote

from pydantic import JsonValue

from packages.intelligence.knowledge.contracts import ObjectCandidate, RelationCandidate
from packages.intelligence.knowledge.identity import cpe_product_canonical_key
from packages.intelligence.knowledge.vocabulary import ApplicabilityState
from packages.intelligence.normalization.cvelist_v5 import CVEListV5HotBugNormalizer
from packages.intelligence.normalization.nvd_durable import (
    ProjectedVulnerabilityCanonicalNormalizer,
)
from packages.sources.contracts import IngestEnvelope


class CVEListV5CanonicalNormalizer(ProjectedVulnerabilityCanonicalNormalizer):
    PROCESSOR_VERSION = "2"

    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        super().__init__(
            processor_name="cvelist-v5-canonical-normalizer",
            projection=CVEListV5HotBugNormalizer(),
            locator_for=_cvelist_locator_for,
            relations_for=_cvelist_relations,
            now=now,
        )


def _cvelist_locator_for(predicate: str) -> dict[str, object]:
    paths = {
        "status": "$.cveMetadata.state",
        "title": "$.containers.cna.title",
        "description_en": "$.containers.cna.descriptions",
        "assigner": "$.cveMetadata.assignerShortName",
        "affected_products": "$.containers.cna.affected",
        "references": "$.containers.cna.references",
        "published": "$.cveMetadata.datePublished",
        "last_modified": "$.cveMetadata.dateUpdated",
    }
    return {"kind": "jsonpath", "path": paths.get(predicate, "$")}


def _cvelist_relations(
    projection: dict[str, object],
    envelope: IngestEnvelope,
) -> list[RelationCandidate]:
    del projection
    containers = envelope.json_payload.get("containers")
    if not isinstance(containers, dict):
        return []
    cna = containers.get("cna")
    if not isinstance(cna, dict):
        return []
    affected = cna.get("affected")
    if not isinstance(affected, list):
        return []

    relations: list[RelationCandidate] = []
    for affected_index, raw_entry in enumerate(affected):
        if not isinstance(raw_entry, dict):
            continue
        target = _affected_target(raw_entry)
        if target is None:
            continue
        context = _product_context(raw_entry)
        if _entry_has_affected(raw_entry):
            relations.append(
                RelationCandidate(
                    relation_type=(
                        "affects-package" if target.object_type == "Package" else "affects-product"
                    ),
                    target=target,
                    qualifier={
                        "source_semantics": "cve5_affected_entry",
                        "product_context": context,
                    },
                    locator={
                        "kind": "jsonpath",
                        "path": f"$.containers.cna.affected[{affected_index}]",
                    },
                )
            )

        versions = raw_entry.get("versions")
        if isinstance(versions, list):
            for version_index, raw_rule in enumerate(versions):
                if not isinstance(raw_rule, dict):
                    continue
                raw_status = raw_rule.get("status")
                if not isinstance(raw_status, str):
                    continue
                state = _canonical_state(raw_status)
                rule_scope = _version_rule_scope(raw_rule)
                qualifier: dict[str, JsonValue] = {
                    "state": state,
                    "source_semantics": "cve5_version_rule",
                    "source_status": raw_status,
                    "scope": cast(JsonValue, {"kind": "version_rule", **rule_scope}),
                    "product_context": context,
                }
                changes = _status_changes(raw_rule.get("changes"))
                if changes:
                    qualifier["status_changes"] = changes
                relations.append(
                    RelationCandidate(
                        relation_type="applicability-status",
                        target=target,
                        qualifier=qualifier,
                        locator={
                            "kind": "jsonpath",
                            "path": (
                                f"$.containers.cna.affected[{affected_index}]"
                                f".versions[{version_index}]"
                            ),
                        },
                    )
                )

        default_raw = raw_entry.get("defaultStatus")
        default_inferred = not isinstance(default_raw, str)
        default_status = default_raw if isinstance(default_raw, str) else "unknown"
        default_qualifier: dict[str, JsonValue] = {
            "state": _canonical_state(default_status),
            "source_semantics": "cve5_default_status",
            "source_status": default_status,
            "scope": cast(JsonValue, {"kind": "default"}),
            "product_context": context,
        }
        if default_inferred:
            default_qualifier["default_inferred"] = True
        relations.append(
            RelationCandidate(
                relation_type="applicability-status",
                target=target,
                qualifier=default_qualifier,
                locator={
                    "kind": "jsonpath",
                    "path": (
                        f"$.containers.cna.affected[{affected_index}].defaultStatus"
                        if not default_inferred
                        else f"$.containers.cna.affected[{affected_index}]"
                    ),
                },
            )
        )
    return relations


def _affected_target(entry: dict[str, Any]) -> ObjectCandidate | None:
    raw_cpes = entry.get("cpes")
    if isinstance(raw_cpes, list):
        for raw_cpe in raw_cpes:
            parsed = _parse_cpe_product(raw_cpe)
            if parsed is None:
                continue
            part, vendor, product = parsed
            return ObjectCandidate(
                object_type="Product",
                canonical_key=cpe_product_canonical_key(part, vendor, product),
                properties={
                    "identity_scheme": "cpe23_product",
                    "cpe_part": part,
                    "vendor": vendor,
                    "product": product,
                    **_optional_property("package_name", entry.get("packageName")),
                },
            )

    package_name = entry.get("packageName")
    raw_vendor = entry.get("vendor")
    raw_product = entry.get("product")
    collection_url = entry.get("collectionURL")
    if isinstance(package_name, str) and package_name:
        material = "|".join(
            value.strip().lower()
            for value in (
                raw_vendor if isinstance(raw_vendor, str) else "",
                raw_product if isinstance(raw_product, str) else "",
                package_name,
                collection_url if isinstance(collection_url, str) else "",
            )
        )
        return ObjectCandidate(
            object_type="Package",
            canonical_key=f"package:cve5-sha256:{sha256(material.encode()).hexdigest()}",
            properties={
                "identity_scheme": "cve5_package",
                "package_name": package_name,
                **_optional_property("vendor", raw_vendor),
                **_optional_property("product", raw_product),
                **_optional_property("collection_url", collection_url),
            },
        )
    if isinstance(raw_product, str) and raw_product:
        vendor_value = raw_vendor if isinstance(raw_vendor, str) else ""
        material = f"{vendor_value.strip().lower()}|{raw_product.strip().lower()}"
        return ObjectCandidate(
            object_type="Product",
            canonical_key=f"product:cve5-sha256:{sha256(material.encode()).hexdigest()}",
            properties={
                "identity_scheme": "cve5_vendor_product",
                "product": raw_product,
                **_optional_property("vendor", raw_vendor),
            },
        )
    return None


def _product_context(entry: dict[str, Any]) -> JsonValue:
    context: dict[str, JsonValue] = {}
    for source_key, target_key in (
        ("vendor", "vendor"),
        ("product", "product"),
        ("packageName", "package_name"),
        ("collectionURL", "collection_url"),
    ):
        value = entry.get(source_key)
        if isinstance(value, str) and value:
            context[target_key] = value
    cpes = entry.get("cpes")
    if isinstance(cpes, list):
        normalized = [item for item in cpes if isinstance(item, str)]
        if normalized:
            context["cpes"] = cast(list[JsonValue], normalized)
    return cast(JsonValue, context)


def _version_rule_scope(rule: dict[str, Any]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for source_key, target_key in (
        ("version", "version"),
        ("versionType", "version_type"),
        ("lessThan", "less_than"),
        ("lessThanOrEqual", "less_than_or_equal"),
    ):
        value = rule.get(source_key)
        if isinstance(value, str) and value:
            result[target_key] = value
    return result


def _status_changes(value: Any) -> JsonValue | None:
    if not isinstance(value, list):
        return None
    changes: list[JsonValue] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        at = item.get("at")
        status = item.get("status")
        if isinstance(at, str) and isinstance(status, str):
            changes.append(cast(JsonValue, {"at": at, "status": status}))
    return cast(JsonValue, changes) if changes else None


def _canonical_state(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "affected":
        return ApplicabilityState.AFFECTED.value
    if normalized == "unaffected":
        return ApplicabilityState.NOT_AFFECTED.value
    return ApplicabilityState.UNKNOWN.value


def _entry_has_affected(entry: dict[str, Any]) -> bool:
    if str(entry.get("defaultStatus", "")).lower() == "affected":
        return True
    versions = entry.get("versions")
    if not isinstance(versions, list):
        return False
    for rule in versions:
        if not isinstance(rule, dict):
            continue
        if str(rule.get("status", "")).lower() == "affected":
            return True
        changes = rule.get("changes")
        if isinstance(changes, list) and any(
            isinstance(change, dict)
            and str(change.get("status", "")).lower() == "affected"
            for change in changes
        ):
            return True
    return False


def _parse_cpe_product(value: Any) -> tuple[str, str, str] | None:
    if not isinstance(value, str):
        return None
    if value.startswith("cpe:/"):
        parts = value[5:].split(":")
        if len(parts) < 3:
            return None
        part, vendor, product = parts[0], parts[1], parts[2]
    elif value.startswith("cpe:2.3:"):
        parts = value.split(":")
        if len(parts) < 5:
            return None
        part, vendor, product = parts[2], parts[3], parts[4]
    else:
        return None
    normalized = tuple(unquote(item).strip().lower() for item in (part, vendor, product))
    if any(item in {"", "*", "-"} for item in normalized):
        return None
    return cast(tuple[str, str, str], normalized)


def _optional_property(key: str, value: Any) -> dict[str, JsonValue]:
    return {key: value} if isinstance(value, str) and value else {}
