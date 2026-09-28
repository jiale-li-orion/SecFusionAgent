from __future__ import annotations

from hashlib import sha256
from typing import Any, cast

from pydantic import JsonValue

from packages.intelligence.knowledge.contracts import (
    EnrichmentCandidate,
    ObjectCandidate,
    RelationCandidate,
)
from packages.sources.contracts import IngestEnvelope
from packages.sources.errors import SourceSchemaChanged

_STATUS_MAP = {
    "known_affected": "affected",
    "known_not_affected": "not_affected",
    "fixed": "fixed",
    "under_investigation": "under_investigation",
}


class RedHatCSAFVEXMapper:
    PROCESSOR_NAME = "redhat-csaf-vex-enrichment"
    PROCESSOR_VERSION = "2"

    def map(self, envelope: IngestEnvelope) -> EnrichmentCandidate:
        payload = envelope.json_payload
        cve_id = envelope.external_object_id.upper()
        vulnerabilities = payload.get("vulnerabilities")
        if not isinstance(vulnerabilities, list):
            raise SourceSchemaChanged("CSAF VEX record has no vulnerabilities list")
        vulnerability_index = next(
            (
                index
                for index, item in enumerate(vulnerabilities)
                if isinstance(item, dict) and item.get("cve") == cve_id
            ),
            None,
        )
        vulnerability = (
            vulnerabilities[vulnerability_index] if vulnerability_index is not None else None
        )
        if vulnerability is None:
            raise SourceSchemaChanged("CSAF VEX record has no matching CVE")
        if vulnerability_index is None:
            raise SourceSchemaChanged("CSAF VEX matching CVE has no stable index")
        publisher_namespace = _publisher_namespace(payload)
        products = _product_index(payload.get("product_tree"))
        relationships = _relationship_index(payload.get("product_tree"))
        justifications = _flag_index(vulnerability.get("flags"))
        status = vulnerability.get("product_status")
        relations: list[RelationCandidate] = []
        advisory = _vendor_advisory_relation(
            envelope,
            vulnerability_index=vulnerability_index,
            publisher_namespace=publisher_namespace,
        )
        if advisory is not None:
            relations.append(advisory)
        if isinstance(status, dict):
            for csaf_status, canonical_state in _STATUS_MAP.items():
                product_ids = status.get(csaf_status)
                if not isinstance(product_ids, list):
                    continue
                for index, raw_product_id in enumerate(product_ids):
                    if not isinstance(raw_product_id, str) or not raw_product_id:
                        continue
                    context = _product_context(
                        raw_product_id,
                        products=products,
                        relationships=relationships,
                    )
                    qualifier: dict[str, JsonValue] = {
                        "state": canonical_state,
                        "source_semantics": "csaf_vex",
                        "csaf_status": csaf_status,
                        "scope": cast(
                            JsonValue,
                            {"kind": "csaf_product_status", "product_id": raw_product_id},
                        ),
                        "product_context": context,
                    }
                    labels = justifications.get(raw_product_id)
                    if labels:
                        qualifier["justification"] = cast(list[JsonValue], labels)
                    relations.append(
                        RelationCandidate(
                            relation_type="applicability-status",
                            target=_target_product(
                                raw_product_id,
                                publisher_namespace=publisher_namespace,
                                context=context,
                            ),
                            qualifier=qualifier,
                            locator={
                                "kind": "jsonpath",
                                "path": (
                                    f"$.vulnerabilities[{vulnerability_index}]"
                                    f".product_status.{csaf_status}[{index}]"
                                ),
                            },
                        )
                    )
        return EnrichmentCandidate(
            root_identifiers={"cve": [cve_id]},
            relations=relations,
            replace_relation_types=["applicability-status", "vendor-advisory"],
        )


def _publisher_namespace(payload: dict[str, Any]) -> str:
    document = payload.get("document")
    publisher = document.get("publisher") if isinstance(document, dict) else None
    namespace = publisher.get("namespace") if isinstance(publisher, dict) else None
    if isinstance(namespace, str) and namespace:
        return namespace
    return "redhat-security-data"


def _product_index(tree: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(tree, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}

    def walk(branches: Any) -> None:
        if not isinstance(branches, list):
            return
        for branch in branches:
            if not isinstance(branch, dict):
                continue
            product = branch.get("product")
            if isinstance(product, dict):
                product_id = product.get("product_id")
                if isinstance(product_id, str):
                    result[product_id] = product
            walk(branch.get("branches"))

    walk(tree.get("branches"))
    return result


def _relationship_index(tree: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(tree, dict):
        return {}
    relationships = tree.get("relationships")
    if not isinstance(relationships, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for relation in relationships:
        if not isinstance(relation, dict):
            continue
        full = relation.get("full_product_name")
        product_id = full.get("product_id") if isinstance(full, dict) else None
        if isinstance(product_id, str):
            result[product_id] = relation
    return result


def _flag_index(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, list):
        return {}
    result: dict[str, list[str]] = {}
    for flag in value:
        if not isinstance(flag, dict):
            continue
        label = flag.get("label")
        product_ids = flag.get("product_ids")
        if not isinstance(label, str) or not isinstance(product_ids, list):
            continue
        for product_id in product_ids:
            if isinstance(product_id, str):
                result.setdefault(product_id, []).append(label)
    return result


def _product_context(
    product_id: str,
    *,
    products: dict[str, dict[str, Any]],
    relationships: dict[str, dict[str, Any]],
) -> JsonValue:
    context: dict[str, JsonValue] = {"full_product_id": product_id}
    relation = relationships.get(product_id)
    if relation is not None:
        context["relationship_category"] = cast(JsonValue, relation.get("category"))
        full = relation.get("full_product_name")
        if isinstance(full, dict) and isinstance(full.get("name"), str):
            context["full_product_name"] = full["name"]
        component_id = relation.get("product_reference")
        platform_id = relation.get("relates_to_product_reference")
        if isinstance(component_id, str):
            context["component"] = _product_snapshot(component_id, products.get(component_id))
        if isinstance(platform_id, str):
            context["platform"] = _product_snapshot(platform_id, products.get(platform_id))
    else:
        context["product"] = _product_snapshot(product_id, products.get(product_id))
    return cast(JsonValue, context)


def _product_snapshot(product_id: str, product: dict[str, Any] | None) -> JsonValue:
    snapshot: dict[str, JsonValue] = {"product_id": product_id}
    if product is None:
        return cast(JsonValue, snapshot)
    name = product.get("name")
    if isinstance(name, str):
        snapshot["name"] = name
    helper = product.get("product_identification_helper")
    if isinstance(helper, dict):
        for key in ("purl", "cpe"):
            value = helper.get(key)
            if isinstance(value, str):
                snapshot[key] = value
    return cast(JsonValue, snapshot)


def _target_product(
    product_id: str,
    *,
    publisher_namespace: str,
    context: JsonValue,
) -> ObjectCandidate:
    digest = sha256(f"{publisher_namespace}|{product_id}".encode()).hexdigest()
    return ObjectCandidate(
        object_type="Product",
        canonical_key=f"product:csaf-sha256:{digest}",
        properties={
            "identity_scheme": "csaf_product_id",
            "publisher_namespace": publisher_namespace,
            "csaf_product_id": product_id,
            "product_context": context,
        },
    )


def _vendor_advisory_relation(
    envelope: IngestEnvelope,
    *,
    vulnerability_index: int,
    publisher_namespace: str,
) -> RelationCandidate | None:
    url = envelope.canonical_url
    if not isinstance(url, str) or not url:
        return None
    digest = sha256(url.strip().encode()).hexdigest()
    return RelationCandidate(
        relation_type="vendor-advisory",
        target=ObjectCandidate(
            object_type="Document",
            canonical_key=f"document:url-sha256:{digest}",
            properties={
                "url": url,
                "document_kind": "csaf_vex",
                "publisher_namespace": publisher_namespace,
            },
        ),
        qualifier={"source_semantics": "redhat_csaf_vex_document"},
        locator={
            "kind": "jsonpath",
            "path": f"$.vulnerabilities[{vulnerability_index}].cve",
        },
    )
