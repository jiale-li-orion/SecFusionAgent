from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.runtime_models import register_runtime_models
from packages.evaluation.m1_m3 import EnrichmentFactKey, EnrichmentPrediction, score_enrichment
from packages.intelligence.knowledge.identity import cpe_product_canonical_key
from packages.intelligence.knowledge.vocabulary import EnrichmentDimension, canonical_term
from packages.intelligence.storage.evidence_models import EvidenceArtifactModel, ObservationModel
from packages.intelligence.storage.factory import create_artifact_store
from packages.intelligence.storage.knowledge_models import (
    EvidenceLinkModel,
    ExternalIdentifierModel,
    ObjectModel,
    RelationModel,
)
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory

SOURCE_ID = "cve-program-cvelist-v5"
RAW_ROOT = "https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves"
CVE_RE = re.compile(r"^CVE-(\d{4})-(\d{4,})$")
FORMAL_DIMENSIONS = {
    EnrichmentDimension.PRODUCT_PACKAGE,
    EnrichmentDimension.VERSION_APPLICABILITY,
}


def _normalized(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fact(
    cve_id: str,
    relation_type: str,
    target_key: str,
    target_type: str,
    *,
    qualifier: dict[str, Any] | None = None,
) -> EnrichmentFactKey:
    term = canonical_term("relation", relation_type)
    if term is None:
        raise ValueError(f"unknown canonical relation: {relation_type}")
    formal = qualifier or {}
    return EnrichmentFactKey(
        root_object_key=f"cve:{cve_id}",
        root_object_type="Vulnerability",
        kind="relation",
        dimension=term.dimension,
        predicate_or_relation_type=relation_type,
        normalized_value_or_target_id=target_key,
        target_object_type=target_type,
        qualifier_keys=tuple(sorted(formal)),
        normalized_qualifier=_normalized(formal),
    )


def _raw_url(cve_id: str) -> str:
    match = CVE_RE.fullmatch(cve_id)
    if match is None:
        raise ValueError(f"invalid CVE id: {cve_id}")
    year, number = match.groups()
    prefix = number[:-3] or "0"
    return f"{RAW_ROOT}/{year}/{prefix}xxx/{cve_id}.json"


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


def _target(entry: dict[str, Any]) -> tuple[str, str] | None:
    cpes = entry.get("cpes")
    if isinstance(cpes, list):
        for raw in cpes:
            parsed = _parse_cpe_product(raw)
            if parsed is not None:
                return "Product", cpe_product_canonical_key(*parsed)
    package_name = entry.get("packageName")
    vendor = entry.get("vendor")
    product = entry.get("product")
    collection_url = entry.get("collectionURL")
    if isinstance(package_name, str) and package_name:
        material = "|".join(
            value.strip().lower()
            for value in (
                vendor if isinstance(vendor, str) else "",
                product if isinstance(product, str) else "",
                package_name,
                collection_url if isinstance(collection_url, str) else "",
            )
        )
        return "Package", f"package:cve5-sha256:{sha256(material.encode()).hexdigest()}"
    if isinstance(product, str) and product:
        vendor_value = vendor if isinstance(vendor, str) else ""
        material = f"{vendor_value.strip().lower()}|{product.strip().lower()}"
        return "Product", f"product:cve5-sha256:{sha256(material.encode()).hexdigest()}"
    return None


def _product_context(entry: dict[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = {}
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
        values = [item for item in cpes if isinstance(item, str)]
        if values:
            context["cpes"] = values
    return context


def _state(raw: str) -> str:
    value = raw.strip().lower()
    if value == "affected":
        return "affected"
    if value == "unaffected":
        return "not_affected"
    return "unknown"


def _scope(rule: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"kind": "version_rule"}
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


def _changes(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    return [
        {"at": item["at"], "status": item["status"]}
        for item in value
        if isinstance(item, dict)
        and isinstance(item.get("at"), str)
        and isinstance(item.get("status"), str)
    ]


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
        if any(change["status"].lower() == "affected" for change in _changes(rule.get("changes"))):
            return True
    return False


def _gold_for_case(cve_id: str, payload: dict[str, Any]) -> list[EnrichmentFactKey]:
    containers = payload.get("containers")
    cna = containers.get("cna") if isinstance(containers, dict) else None
    affected = cna.get("affected") if isinstance(cna, dict) else None
    if not isinstance(affected, list):
        return []
    result: list[EnrichmentFactKey] = []
    for entry in affected:
        if not isinstance(entry, dict):
            continue
        target = _target(entry)
        if target is None:
            continue
        target_type, target_key = target
        context = _product_context(entry)
        if _entry_has_affected(entry):
            relation_type = "affects-package" if target_type == "Package" else "affects-product"
            result.append(_fact(cve_id, relation_type, target_key, target_type))
        versions = entry.get("versions")
        if isinstance(versions, list):
            for rule in versions:
                if not isinstance(rule, dict) or not isinstance(rule.get("status"), str):
                    continue
                qualifier: dict[str, Any] = {
                    "state": _state(rule["status"]),
                    "source_semantics": "cve5_version_rule",
                    "source_status": rule["status"],
                    "scope": _scope(rule),
                    "product_context": context,
                }
                changes = _changes(rule.get("changes"))
                if changes:
                    qualifier["status_changes"] = changes
                result.append(
                    _fact(
                        cve_id,
                        "applicability-status",
                        target_key,
                        target_type,
                        qualifier=qualifier,
                    )
                )
        default_raw = entry.get("defaultStatus")
        inferred = not isinstance(default_raw, str)
        default_status = default_raw if isinstance(default_raw, str) else "unknown"
        qualifier = {
            "state": _state(default_status),
            "source_semantics": "cve5_default_status",
            "source_status": default_status,
            "scope": {"kind": "default"},
            "product_context": context,
        }
        if inferred:
            qualifier["default_inferred"] = True
        result.append(
            _fact(
                cve_id,
                "applicability-status",
                target_key,
                target_type,
                qualifier=qualifier,
            )
        )
    return result


def _prediction_qualifier(relation: RelationModel) -> dict[str, Any]:
    if relation.relation_type != "applicability-status":
        return {}
    allowed = (
        "state",
        "source_semantics",
        "source_status",
        "scope",
        "product_context",
        "status_changes",
        "default_inferred",
    )
    return {key: relation.qualifier[key] for key in allowed if key in relation.qualifier}


async def _predictions_for_case(session: AsyncSession, cve_id: str) -> list[EnrichmentPrediction]:
    object_id = await session.scalar(
        select(ExternalIdentifierModel.object_id).where(
            ExternalIdentifierModel.namespace == "cve",
            ExternalIdentifierModel.value == cve_id,
        )
    )
    if object_id is None:
        return []
    root = await session.get(ObjectModel, object_id)
    if root is None:
        return []
    rows = (
        await session.execute(
            select(RelationModel, ObjectModel)
            .join(ObjectModel, ObjectModel.object_id == RelationModel.target_object_id)
            .where(
                RelationModel.source_object_id == object_id,
                RelationModel.lifecycle == "accepted",
                RelationModel.superseded_revision.is_(None),
            )
        )
    ).all()
    predictions: list[EnrichmentPrediction] = []
    for relation, target in rows:
        term = canonical_term("relation", relation.relation_type)
        if term is None or not term.benchmarked or term.dimension not in FORMAL_DIMENSIONS:
            continue
        evidence_rows = (
            await session.execute(
                select(EvidenceLinkModel.evidence_link_id, ObservationModel.source_id)
                .join(
                    ObservationModel,
                    ObservationModel.observation_id == EvidenceLinkModel.observation_id,
                )
                .where(
                    EvidenceLinkModel.target_kind == "relation",
                    EvidenceLinkModel.target_id == relation.relation_id,
                    ObservationModel.source_id == SOURCE_ID,
                )
            )
        ).all()
        if not evidence_rows:
            continue
        fact = _fact(
            cve_id,
            relation.relation_type,
            target.canonical_key,
            target.object_type,
            qualifier=_prediction_qualifier(relation),
        )
        predictions.append(
            EnrichmentPrediction(
                fact=fact,
                evidence_ref_ids=tuple(f"evidence:{row.evidence_link_id}" for row in evidence_rows),
                evidence_correct=True,
            )
        )
    return predictions


def _gold_revision(gold: set[EnrichmentFactKey]) -> str:
    payload = sorted(
        (item.model_dump(mode="json") for item in gold),
        key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
    )
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return f"cve5-applicability:{digest}"


async def _run(cves: list[str]) -> dict[str, Any]:
    snapshots = await _fetch_live_snapshots(cves)
    return await _score_snapshots(cves, snapshots, gold_source_mode="live_snapshot")


async def _run_from_evidence(cves: list[str]) -> dict[str, Any]:
    snapshots = await _evidence_snapshots(cves)
    return await _score_snapshots(cves, snapshots, gold_source_mode="frozen_snapshot_replay")


async def _fetch_live_snapshots(cves: list[str]) -> dict[str, dict[str, Any]]:
    snapshots: dict[str, dict[str, Any]] = {}
    async with httpx.AsyncClient(
        timeout=60.0,
        headers={"User-Agent": "SecFusionAgent-cve5-eval/0.1"},
    ) as client:
        for cve_id in cves:
            response: httpx.Response | None = None
            for attempt in range(5):
                try:
                    response = await client.get(_raw_url(cve_id), follow_redirects=True)
                except httpx.TransportError:
                    if attempt == 4:
                        raise
                    response = None
                else:
                    if response.status_code != 429 and response.status_code < 500:
                        break
                    if attempt == 4:
                        response.raise_for_status()
                await asyncio.sleep(2**attempt)
            if response is None:
                raise RuntimeError(f"CVE Program retry loop produced no response for {cve_id}")
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError(f"CVE Program returned invalid record for {cve_id}")
            snapshots[cve_id] = payload
    return snapshots


async def _evidence_snapshots(cves: list[str]) -> dict[str, dict[str, Any]]:
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    store = create_artifact_store(settings)
    snapshots: dict[str, dict[str, Any]] = {}
    try:
        async with factory() as session:
            for cve_id in cves:
                row = await session.execute(
                    select(ObservationModel, EvidenceArtifactModel)
                    .join(
                        EvidenceArtifactModel,
                        EvidenceArtifactModel.observation_id == ObservationModel.observation_id,
                    )
                    .where(
                        ObservationModel.source_id == SOURCE_ID,
                        ObservationModel.external_object_id == cve_id,
                    )
                    .order_by(ObservationModel.created_at.desc())
                    .limit(1)
                )
                item = row.first()
                if item is None:
                    raise RuntimeError(f"no persisted CVE5 Evidence for {cve_id}")
                _, artifact = item
                raw = await store.get(artifact.storage_uri)
                payload = json.loads(raw)
                if not isinstance(payload, dict):
                    raise RuntimeError(f"persisted CVE5 Evidence is invalid for {cve_id}")
                snapshots[cve_id] = payload
    finally:
        await engine.dispose()
    return snapshots


async def _score_snapshots(
    cves: list[str],
    snapshots: dict[str, dict[str, Any]],
    *,
    gold_source_mode: str,
) -> dict[str, Any]:

    case_gold = {cve_id: _gold_for_case(cve_id, payload) for cve_id, payload in snapshots.items()}
    gold = {fact for facts in case_gold.values() for fact in facts}
    if not gold:
        raise RuntimeError("CVE5 applicability benchmark has zero formal gold facts")

    register_runtime_models()
    engine = create_engine()
    factory = create_session_factory(engine)
    case_predictions: dict[str, list[EnrichmentPrediction]] = {}
    try:
        async with factory() as session:
            for cve_id in cves:
                case_predictions[cve_id] = await _predictions_for_case(session, cve_id)
    finally:
        await engine.dispose()
    predictions = [item for values in case_predictions.values() for item in values]
    score = score_enrichment(gold=gold, predicted=predictions)
    case_scores: dict[str, dict[str, Any]] = {}
    for cve_id in cves:
        case_score = score_enrichment(gold=case_gold[cve_id], predicted=case_predictions[cve_id])
        case_scores[cve_id] = {
            "gold_fact_count": len(set(case_gold[cve_id])),
            "prediction_count": len(case_predictions[cve_id]),
            "score": case_score.model_dump(mode="json"),
        }
    valid = {item.fact for item in predictions if item.evidence_valid}
    snapshot_digest = sha256(
        json.dumps(snapshots, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    return {
        "profile": "cve5-applicability-source-specific-v1",
        "fetched_at": datetime.now(UTC).isoformat(),
        "cases": cves,
        "formal_dimensions": sorted(item.value for item in FORMAL_DIMENSIONS),
        "gold_revision": _gold_revision(gold),
        "provider_snapshot_revision": f"provider-snapshot:{snapshot_digest}",
        "gold_source_mode": gold_source_mode,
        "gold_fact_count": len(gold),
        "prediction_count": len(predictions),
        "score": score.model_dump(mode="json"),
        "case_scores": case_scores,
        "missing_facts": [
            item.model_dump(mode="json")
            for item in sorted(
                gold - valid,
                key=lambda x: (
                    x.root_object_key,
                    x.dimension.value,
                    x.predicate_or_relation_type,
                    x.normalized_value_or_target_id,
                    x.normalized_qualifier,
                ),
            )
        ],
        "extra_facts": [
            item.model_dump(mode="json")
            for item in sorted(
                valid - gold,
                key=lambda x: (
                    x.root_object_key,
                    x.dimension.value,
                    x.predicate_or_relation_type,
                    x.normalized_value_or_target_id,
                    x.normalized_qualifier,
                ),
            )
        ],
        "snapshot_summary": {
            cve_id: {
                "affected_entry_count": len(
                    ((payload.get("containers") or {}).get("cna") or {}).get("affected") or []
                )
            }
            for cve_id, payload in snapshots.items()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate CVE Record Format 5.x product/version applicability"
    )
    parser.add_argument("cves", nargs="+")
    parser.add_argument(
        "--from-evidence",
        action="store_true",
        help="Build independent gold from persisted raw CVE Program EvidenceArtifact bytes",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cves = [item.upper() for item in args.cves]
    report = asyncio.run(_run_from_evidence(cves) if args.from_evidence else _run(cves))
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
