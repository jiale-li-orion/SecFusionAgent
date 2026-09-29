from __future__ import annotations

import json
from typing import Any


def render_claim_fact(
    subject_key: str,
    predicate: str,
    value: object,
    *,
    qualifier: dict[str, object] | None = None,
) -> str:
    base = f"{subject_key} {predicate} = {_render(value)}"
    semantics = compact_claim_semantics(predicate, qualifier or {})
    if not semantics:
        return base
    return f"{base} semantics={_render(semantics)}"


def compact_claim_semantics(
    predicate: str,
    qualifier: dict[str, object],
) -> dict[str, object]:
    """Preserve qualifier fields only when they are part of the claim's semantic identity."""

    result: dict[str, object] = {}
    if qualifier.get("vocabulary_scope") == "source_specific":
        source_id = qualifier.get("source_id")
        if source_id not in (None, ""):
            result["source_id"] = source_id
    if predicate not in {"epss_probability", "epss_percentile"}:
        return result
    source_semantics = qualifier.get("source_semantics")
    if source_semantics not in (None, ""):
        result["source_semantics"] = source_semantics
    elif "source_id" not in result:
        source_id = qualifier.get("source_id")
        if source_id not in (None, ""):
            result["source_id"] = source_id
    score_date = qualifier.get("score_date")
    if score_date not in (None, ""):
        result["score_date"] = score_date
    return result


def render_relation_fact(
    source_key: str,
    relation_type: str,
    target_key: str,
    *,
    qualifier: dict[str, object],
    target_properties: dict[str, object] | None = None,
) -> str:
    semantics = compact_relation_semantics(
        qualifier,
        target_properties=target_properties or {},
    )
    base = f"{source_key} {relation_type} {target_key}"
    if not semantics:
        return base
    return f"{base} semantics={_render(semantics)}"


def compact_relation_semantics(
    qualifier: dict[str, object],
    *,
    target_properties: dict[str, object],
) -> dict[str, object]:
    """Keep relation meaning while dropping provenance-only and bulky snapshot payloads."""

    result: dict[str, object] = {}
    for key in (
        "state",
        "source_semantics",
        "source_status",
        "csaf_status",
        "version_range",
        "platform",
        "scope",
        "justification",
    ):
        value = qualifier.get(key)
        if value not in (None, {}, []):
            result[key] = value

    product_context = qualifier.get("product_context")
    if isinstance(product_context, dict):
        compact = _compact_product_context(product_context)
        if compact:
            result["product_context"] = compact

    configuration = qualifier.get("configuration")
    if isinstance(configuration, dict):
        compact_configuration = _compact_configuration(configuration)
        if compact_configuration:
            result["configuration"] = compact_configuration

    target_context = _compact_target_context(target_properties)
    if target_context and qualifier.get("source_semantics") != "csaf_vex":
        result["target_context"] = target_context
    return result


def _compact_product_context(value: dict[str, Any]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key in ("relationship_category",):
        item = value.get(key)
        if item not in (None, ""):
            result[key] = item
    for key in ("component", "platform"):
        item = value.get(key)
        if not isinstance(item, dict):
            continue
        compact = {
            nested_key: item[nested_key]
            for nested_key in ("product_id", "name", "purl", "cpe")
            if item.get(nested_key) not in (None, "")
        }
        if compact:
            result[key] = compact
    return result


def _compact_configuration(value: dict[str, Any]) -> dict[str, object]:
    return {
        key: value[key]
        for key in (
            "root_index",
            "root_operator",
            "root_negate",
            "node_path",
            "node_operator",
            "node_negate",
            "match_criteria_id",
            "match_index",
        )
        if value.get(key) not in (None, "", [], {})
    }


def _compact_target_context(value: dict[str, Any]) -> dict[str, object]:
    return {
        key: value[key]
        for key in (
            "display_name",
            "name",
            "vendor",
            "product",
            "package",
            "version",
            "csaf_product_id",
            "identity_scheme",
        )
        if value.get(key) not in (None, "")
    }


def _render(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
