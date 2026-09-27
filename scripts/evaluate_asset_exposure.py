from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from hashlib import sha256
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
    ObjectModel,
    RelationModel,
)
from packages.shared.db import create_engine, create_session_factory

SOURCE_ID = "shodan-internetdb-assets"
SOURCE_SEMANTICS = "shodan_internetdb_vulns"


def _normalized(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fact(ip: str, cve_id: str) -> EnrichmentFactKey:
    term = canonical_term("relation", "asset-potentially-affected")
    if term is None:
        raise RuntimeError("asset-potentially-affected is not registered")
    qualifier = {"source_semantics": SOURCE_SEMANTICS}
    return EnrichmentFactKey(
        root_object_key=f"internet-asset:ip:{ip}",
        root_object_type="InternetAsset",
        kind="relation",
        dimension=EnrichmentDimension.ASSET_EXPOSURE,
        predicate_or_relation_type="asset-potentially-affected",
        normalized_value_or_target_id=f"cve:{cve_id}",
        target_object_type="Vulnerability",
        qualifier_keys=tuple(sorted(qualifier)),
        normalized_qualifier=_normalized(qualifier),
    )


def _gold_revision(gold: set[EnrichmentFactKey]) -> str:
    payload = sorted(
        (item.model_dump(mode="json") for item in gold),
        key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
    )
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return f"asset-exposure:{digest}"


async def _prediction_for_relation(
    session: AsyncSession,
    *,
    relation: RelationModel,
    root: ObjectModel,
    target: ObjectModel,
) -> EnrichmentPrediction:
    rows = (
        await session.execute(
            select(EvidenceLinkModel.evidence_link_id, ObservationModel.source_id)
            .join(
                ObservationModel,
                ObservationModel.observation_id == EvidenceLinkModel.observation_id,
            )
            .where(
                EvidenceLinkModel.target_kind == "relation",
                EvidenceLinkModel.target_id == relation.relation_id,
            )
        )
    ).all()
    qualifier = {"source_semantics": relation.qualifier.get("source_semantics")}
    fact = EnrichmentFactKey(
        root_object_key=root.canonical_key,
        root_object_type=root.object_type,
        kind="relation",
        dimension=EnrichmentDimension.ASSET_EXPOSURE,
        predicate_or_relation_type=relation.relation_type,
        normalized_value_or_target_id=target.canonical_key,
        target_object_type=target.object_type,
        qualifier_keys=tuple(sorted(qualifier)),
        normalized_qualifier=_normalized(qualifier),
    )
    return EnrichmentPrediction(
        fact=fact,
        evidence_ref_ids=tuple(f"evidence:{row.evidence_link_id}" for row in rows),
        evidence_correct=bool(rows) and any(row.source_id == SOURCE_ID for row in rows),
    )


async def _run(ips: list[str]) -> dict[str, Any]:
    snapshots: dict[str, dict[str, Any]] = {}
    async with httpx.AsyncClient(
        timeout=30.0,
        headers={"User-Agent": "SecFusionAgent-asset-eval/0.1"},
    ) as client:
        for ip in ips:
            response = await client.get(f"https://internetdb.shodan.io/{ip}")
            if response.status_code == 404:
                continue
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("ip") != ip:
                raise RuntimeError(f"InternetDB returned invalid payload for {ip}")
            snapshots[ip] = payload

    gold: set[EnrichmentFactKey] = set()
    case_gold: dict[str, list[EnrichmentFactKey]] = {}
    for ip, payload in snapshots.items():
        vulns = payload.get("vulns")
        facts: list[EnrichmentFactKey] = []
        if isinstance(vulns, list):
            for raw in vulns:
                if not isinstance(raw, str):
                    continue
                cve_id = raw.strip().upper()
                if not cve_id.startswith("CVE-"):
                    continue
                facts.append(_fact(ip, cve_id))
        case_gold[ip] = facts
        gold.update(facts)
    if not gold:
        raise RuntimeError("asset exposure benchmark has zero formal gold facts")

    register_runtime_models()
    engine = create_engine()
    factory = create_session_factory(engine)
    predictions: list[EnrichmentPrediction] = []
    case_predictions: dict[str, list[EnrichmentPrediction]] = {ip: [] for ip in snapshots}
    try:
        async with factory() as session:
            for ip in snapshots:
                root = await session.scalar(
                    select(ObjectModel).where(
                        ObjectModel.object_type == "InternetAsset",
                        ObjectModel.canonical_key == f"internet-asset:ip:{ip}",
                    )
                )
                if root is None:
                    continue
                relations = list(
                    await session.scalars(
                        select(RelationModel).where(
                            RelationModel.source_object_id == root.object_id,
                            RelationModel.relation_type == "asset-potentially-affected",
                            RelationModel.lifecycle == "accepted",
                            RelationModel.superseded_revision.is_(None),
                        )
                    )
                )
                for relation in relations:
                    if relation.qualifier.get("source_semantics") != SOURCE_SEMANTICS:
                        continue
                    target = await session.get(ObjectModel, relation.target_object_id)
                    if target is None or target.object_type != "Vulnerability":
                        continue
                    prediction = await _prediction_for_relation(
                        session,
                        relation=relation,
                        root=root,
                        target=target,
                    )
                    predictions.append(prediction)
                    case_predictions[ip].append(prediction)
    finally:
        await engine.dispose()

    score = score_enrichment(gold=gold, predicted=predictions)
    case_scores: dict[str, dict[str, Any]] = {}
    for ip in snapshots:
        case_score = score_enrichment(
            gold=case_gold[ip],
            predicted=case_predictions[ip],
        )
        case_scores[ip] = {
            "gold_fact_count": len(set(case_gold[ip])),
            "prediction_count": len(case_predictions[ip]),
            "score": case_score.model_dump(mode="json"),
        }
    valid = {item.fact for item in predictions if item.evidence_valid}
    return {
        "profile": "shodan-internetdb-asset-exposure-v1",
        "fetched_at": datetime.now(UTC).isoformat(),
        "cases": ips,
        "formal_dimensions": [EnrichmentDimension.ASSET_EXPOSURE.value],
        "gold_revision": _gold_revision(gold),
        "gold_fact_count": len(gold),
        "prediction_count": len(predictions),
        "score": score.model_dump(mode="json"),
        "case_scores": case_scores,
        "missing_facts": [
            item.model_dump(mode="json")
            for item in sorted(
                gold - valid,
                key=lambda item: (item.root_object_key, item.normalized_value_or_target_id),
            )
        ],
        "extra_facts": [
            item.model_dump(mode="json")
            for item in sorted(
                valid - gold,
                key=lambda item: (item.root_object_key, item.normalized_value_or_target_id),
            )
        ],
        "snapshots": {
            ip: {
                "ports": payload.get("ports"),
                "hostnames": payload.get("hostnames"),
                "cpes": payload.get("cpes"),
                "vulns": payload.get("vulns"),
            }
            for ip, payload in snapshots.items()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate explicit Shodan InternetDB asset-vulnerability associations"
    )
    parser.add_argument("ips", nargs="+")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = asyncio.run(_run(args.ips))
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
