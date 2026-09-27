from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.runtime_models import register_runtime_models
from packages.evaluation.m1_m3 import EnrichmentFactKey, EnrichmentPrediction, score_enrichment
from packages.intelligence.knowledge.vocabulary import EnrichmentDimension, canonical_term
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import (
    EvidenceLinkModel,
    ExternalIdentifierModel,
    ObjectModel,
    RelationModel,
)
from packages.shared.db import create_engine, create_session_factory

FORMAL_DIMENSIONS = {
    EnrichmentDimension.PRODUCT_PACKAGE,
    EnrichmentDimension.VERSION_APPLICABILITY,
    EnrichmentDimension.FIX_REMEDIATION,
}


def _normalized(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _relation_fact(
    root_key: str,
    relation_type: str,
    target_key: str,
    target_type: str,
    *,
    qualifier: dict[str, Any] | None = None,
) -> EnrichmentFactKey:
    term = canonical_term("relation", relation_type)
    if term is None:
        raise ValueError(f"unknown canonical relation: {relation_type}")
    formal_qualifier = qualifier or {}
    return EnrichmentFactKey(
        root_object_key=root_key,
        root_object_type="Vulnerability",
        kind="relation",
        dimension=term.dimension,
        predicate_or_relation_type=relation_type,
        normalized_value_or_target_id=target_key,
        target_object_type=target_type,
        qualifier_keys=tuple(sorted(formal_qualifier)),
        normalized_qualifier=_normalized(formal_qualifier),
    )


def _applicability_qualifier(affected: dict[str, Any]) -> dict[str, Any]:
    qualifier: dict[str, Any] = {
        "state": "affected",
        "source_semantics": "osv_range",
    }
    ranges = affected.get("ranges")
    versions = affected.get("versions")
    if isinstance(ranges, list):
        qualifier["ranges"] = ranges
    if isinstance(versions, list):
        qualifier["versions"] = versions
    return qualifier


def _fixed_versions(affected: dict[str, Any]) -> list[str]:
    result: list[str] = []
    ranges = affected.get("ranges")
    if not isinstance(ranges, list):
        return result
    for range_item in ranges:
        if not isinstance(range_item, dict) or range_item.get("type") not in {
            "ECOSYSTEM",
            "SEMVER",
        }:
            continue
        events = range_item.get("events")
        if not isinstance(events, list):
            continue
        for event in events:
            if not isinstance(event, dict):
                continue
            fixed = event.get("fixed")
            if isinstance(fixed, str) and fixed and fixed not in result:
                result.append(fixed)
    return result


def _has_package_affected(payload: dict[str, Any]) -> bool:
    affected = payload.get("affected")
    if not isinstance(affected, list):
        return False
    return any(
        isinstance(item, dict)
        and isinstance(item.get("package"), dict)
        and isinstance(item["package"].get("name"), str)
        and isinstance(item["package"].get("ecosystem"), str)
        for item in affected
    )


def _ghsa_aliases(payload: dict[str, Any]) -> list[str]:
    aliases = payload.get("aliases")
    if not isinstance(aliases, list):
        return []
    return [item for item in aliases if isinstance(item, str) and item.startswith("GHSA-")]


def _gold_for_case(cve_id: str, payload: dict[str, Any]) -> list[EnrichmentFactKey]:
    root_key = f"cve:{cve_id}"
    result: list[EnrichmentFactKey] = []
    affected_items = payload.get("affected")
    if not isinstance(affected_items, list):
        return result
    for affected in affected_items:
        if not isinstance(affected, dict):
            continue
        package = affected.get("package")
        if not isinstance(package, dict):
            continue
        ecosystem = package.get("ecosystem")
        name = package.get("name")
        if not isinstance(ecosystem, str) or not isinstance(name, str):
            continue
        package_key = f"package:{ecosystem.lower()}:{name.lower()}"
        result.append(_relation_fact(root_key, "affects-package", package_key, "Package"))
        result.append(
            _relation_fact(
                root_key,
                "applicability-status",
                package_key,
                "Package",
                qualifier=_applicability_qualifier(affected),
            )
        )
        for fixed in _fixed_versions(affected):
            result.append(
                _relation_fact(
                    root_key,
                    "fixed-version",
                    f"software-version:{ecosystem.lower()}:{name.lower()}:{fixed}",
                    "SoftwareVersion",
                )
            )
    return result


def _prediction_qualifier(relation: RelationModel) -> dict[str, Any]:
    if relation.relation_type != "applicability-status":
        return {}
    allowed = ("state", "source_semantics", "ranges", "versions")
    return {key: relation.qualifier[key] for key in allowed if key in relation.qualifier}


async def _predictions_for_case(
    session: AsyncSession,
    cve_id: str,
) -> list[EnrichmentPrediction]:
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
                    ObservationModel.source_id == "osv-vulnerabilities",
                )
            )
        ).all()
        if not evidence_rows:
            continue
        fact = _relation_fact(
            root.canonical_key,
            relation.relation_type,
            target.canonical_key,
            target.object_type,
            qualifier=_prediction_qualifier(relation),
        )
        predictions.append(
            EnrichmentPrediction(
                fact=fact,
                evidence_ref_ids=tuple(
                    f"evidence:{item.evidence_link_id}" for item in evidence_rows
                ),
                evidence_correct=True,
            )
        )
    return predictions


async def _run(cves: list[str]) -> dict[str, Any]:
    snapshots: dict[str, list[dict[str, Any]]] = {}
    unavailable: list[str] = []
    async with httpx.AsyncClient(
        timeout=30.0,
        headers={"User-Agent": "SecFusionAgent-osv-eval/0.1"},
    ) as client:
        for cve_id in cves:
            response = await client.get(f"https://api.osv.dev/v1/vulns/{cve_id}")
            if response.status_code == 404:
                unavailable.append(cve_id)
                continue
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError(f"OSV returned invalid payload for {cve_id}")
            payloads = [payload]
            if not _has_package_affected(payload):
                seen_ids = {payload.get("id")}
                for alias in _ghsa_aliases(payload):
                    alias_response = await client.get(f"https://api.osv.dev/v1/vulns/{alias}")
                    if alias_response.status_code == 404:
                        continue
                    alias_response.raise_for_status()
                    alias_payload = alias_response.json()
                    if not isinstance(alias_payload, dict):
                        raise RuntimeError(f"OSV returned invalid payload for {alias}")
                    if alias_payload.get("id") in seen_ids:
                        continue
                    seen_ids.add(alias_payload.get("id"))
                    payloads.append(alias_payload)
            snapshots[cve_id] = payloads

    gold: list[EnrichmentFactKey] = []
    for cve_id, payloads in snapshots.items():
        for payload in payloads:
            gold.extend(_gold_for_case(cve_id, payload))
    if not set(gold):
        raise RuntimeError(
            "OSV source-specific benchmark has zero formal gold facts; "
            "the selected records are not applicability-evaluable"
        )

    register_runtime_models()
    engine = create_engine()
    factory = create_session_factory(engine)
    try:
        predicted: list[EnrichmentPrediction] = []
        async with factory() as session:
            for cve_id in snapshots:
                predicted.extend(await _predictions_for_case(session, cve_id))
    finally:
        await engine.dispose()

    score = score_enrichment(gold=gold, predicted=predicted)
    return {
        "profile": "osv-source-specific-v1",
        "fetched_at": datetime.now(UTC).isoformat(),
        "requested_cases": cves,
        "evaluable_cases": list(snapshots),
        "unavailable_cases": unavailable,
        "gold_fact_count": len(set(gold)),
        "prediction_count": len(predicted),
        "score": score.model_dump(mode="json"),
        "dimension_summary": {
            item.dimension.value: item.model_dump(mode="json") for item in score.dimensions
        },
        "missing_facts": [
            item.model_dump(mode="json")
            for item in sorted(
                set(gold) - {p.fact for p in predicted if p.evidence_valid},
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
                {p.fact for p in predicted if p.evidence_valid} - set(gold),
                key=lambda x: (
                    x.root_object_key,
                    x.dimension.value,
                    x.predicate_or_relation_type,
                    x.normalized_value_or_target_id,
                    x.normalized_qualifier,
                ),
            )
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate OSV structured package/applicability/fixed-version normalization"
    )
    parser.add_argument("cves", nargs="+")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = asyncio.run(_run([item.upper() for item in args.cves]))
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
