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
    ClaimModel,
    EvidenceLinkModel,
    ExternalIdentifierModel,
    ObjectModel,
)
from packages.shared.db import create_engine, create_session_factory

FORMAL_DIMENSIONS = {EnrichmentDimension.EXPLOIT_LIKELIHOOD}


def _normalized(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _claim_fact(
    root_key: str,
    predicate: str,
    value: float,
    *,
    score_date: str,
) -> EnrichmentFactKey:
    term = canonical_term("claim", predicate)
    if term is None:
        raise ValueError(f"unknown canonical claim: {predicate}")
    qualifier = {
        "source_semantics": "first_epss",
        "score_date": score_date,
    }
    return EnrichmentFactKey(
        root_object_key=root_key,
        root_object_type="Vulnerability",
        kind="claim",
        dimension=term.dimension,
        predicate_or_relation_type=predicate,
        normalized_value_or_target_id=_normalized(value),
        qualifier_keys=tuple(sorted(qualifier)),
        normalized_qualifier=_normalized(qualifier),
        temporal_scope=score_date,
    )


def _float_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _gold_for_record(cve_id: str, record: dict[str, Any]) -> list[EnrichmentFactKey]:
    probability = _float_value(record.get("epss"))
    percentile = _float_value(record.get("percentile"))
    score_date = record.get("date") or record.get("created")
    if (
        probability is None
        or percentile is None
        or not isinstance(score_date, str)
        or not score_date
    ):
        return []
    root_key = f"cve:{cve_id}"
    return [
        _claim_fact(root_key, "epss_probability", probability, score_date=score_date),
        _claim_fact(root_key, "epss_percentile", percentile, score_date=score_date),
    ]


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
    claims = list(
        await session.scalars(
            select(ClaimModel).where(
                ClaimModel.subject_id == object_id,
                ClaimModel.lifecycle == "accepted",
                ClaimModel.superseded_revision.is_(None),
            )
        )
    )
    predictions: list[EnrichmentPrediction] = []
    for claim in claims:
        term = canonical_term("claim", claim.predicate)
        if term is None or not term.benchmarked or term.dimension not in FORMAL_DIMENSIONS:
            continue
        if claim.qualifier.get("source_id") != "first-epss":
            continue
        if claim.qualifier.get("source_semantics") != "first_epss":
            continue
        score_date = claim.qualifier.get("score_date")
        if not isinstance(score_date, str) or not score_date:
            continue
        value = _float_value(claim.value)
        if value is None:
            continue
        evidence_rows = (
            await session.execute(
                select(EvidenceLinkModel.evidence_link_id, ObservationModel.source_id)
                .join(
                    ObservationModel,
                    ObservationModel.observation_id == EvidenceLinkModel.observation_id,
                )
                .where(
                    EvidenceLinkModel.target_kind == "claim",
                    EvidenceLinkModel.target_id == claim.claim_id,
                    ObservationModel.source_id == "first-epss",
                )
            )
        ).all()
        if not evidence_rows:
            continue
        predictions.append(
            EnrichmentPrediction(
                fact=_claim_fact(
                    root.canonical_key,
                    claim.predicate,
                    value,
                    score_date=score_date,
                ),
                evidence_ref_ids=tuple(f"evidence:{row.evidence_link_id}" for row in evidence_rows),
                evidence_correct=True,
            )
        )
    return predictions


async def _run(cves: list[str]) -> dict[str, Any]:
    snapshots: dict[str, dict[str, Any]] = {}
    unavailable: list[str] = []
    async with httpx.AsyncClient(
        timeout=30.0,
        headers={"User-Agent": "SecFusionAgent-first-epss-eval/0.1"},
    ) as client:
        for cve_id in cves:
            response = await client.get(
                "https://api.first.org/data/v1/epss",
                params={"cve": cve_id},
            )
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(data, list):
                raise RuntimeError(f"FIRST EPSS returned invalid payload for {cve_id}")
            record = next(
                (item for item in data if isinstance(item, dict) and item.get("cve") == cve_id),
                None,
            )
            if record is None:
                unavailable.append(cve_id)
                continue
            snapshots[cve_id] = record

    gold = [
        fact for cve_id, record in snapshots.items() for fact in _gold_for_record(cve_id, record)
    ]
    if not set(gold):
        raise RuntimeError("FIRST EPSS benchmark has zero formal gold facts")

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
    valid = {item.fact for item in predicted if item.evidence_valid}
    return {
        "profile": "first-epss-source-specific-v1",
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
                set(gold) - valid,
                key=lambda x: (
                    x.root_object_key,
                    x.predicate_or_relation_type,
                    x.temporal_scope,
                ),
            )
        ],
        "extra_facts": [
            item.model_dump(mode="json")
            for item in sorted(
                valid - set(gold),
                key=lambda x: (
                    x.root_object_key,
                    x.predicate_or_relation_type,
                    x.temporal_scope,
                ),
            )
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate FIRST EPSS point-in-time normalization with independent live gold"
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
