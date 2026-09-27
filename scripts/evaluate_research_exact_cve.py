from __future__ import annotations

import argparse
import asyncio
import json
import re
import xml.etree.ElementTree as ET
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

SOURCE_ID = "arxiv-ai-security"
ATOM = {"atom": "http://www.w3.org/2005/Atom"}
CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)
VERSION_RE = re.compile(r"^(?P<base>.+?)(?P<version>v\d+)?$")


def _normalized(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _base_id(arxiv_id: str) -> str:
    match = VERSION_RE.match(arxiv_id)
    return match.group("base") if match is not None else arxiv_id


def _fact(arxiv_id: str, cve_id: str) -> EnrichmentFactKey:
    term = canonical_term("relation", "discusses-vulnerability")
    if term is None:
        raise RuntimeError("discusses-vulnerability is not registered")
    return EnrichmentFactKey(
        root_object_key=f"arxiv:{_base_id(arxiv_id)}",
        root_object_type="ResearchWork",
        kind="relation",
        dimension=EnrichmentDimension.RESEARCH_PAPER,
        predicate_or_relation_type="discusses-vulnerability",
        normalized_value_or_target_id=f"cve:{cve_id}",
        target_object_type="Vulnerability",
    )


def _gold_revision(gold: set[EnrichmentFactKey], revisions: dict[str, str]) -> str:
    payload = {
        "facts": sorted(
            (item.model_dump(mode="json") for item in gold),
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
        ),
        "paper_revisions": dict(sorted(revisions.items())),
    }
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return f"research-exact-cve:{digest}"


async def _atom_gold(
    client: httpx.AsyncClient,
    requested_id: str,
) -> tuple[str, set[str], dict[str, Any]]:
    response = await client.get(
        "https://export.arxiv.org/api/query",
        params={"id_list": requested_id, "max_results": 1},
    )
    response.raise_for_status()
    root = ET.fromstring(response.text)
    entry = root.find("atom:entry", ATOM)
    if entry is None:
        raise RuntimeError(f"arXiv returned no entry for {requested_id}")
    entry_url = entry.findtext("atom:id", default="", namespaces=ATOM)
    versioned_id = entry_url.rstrip("/").split("/")[-1]
    if requested_id != versioned_id:
        raise RuntimeError(
            f"frozen arXiv revision mismatch: requested={requested_id} returned={versioned_id}"
        )
    title = entry.findtext("atom:title", default="", namespaces=ATOM)
    summary = entry.findtext("atom:summary", default="", namespaces=ATOM)
    text = f"{title}\n{summary}"
    cves = {match.group(0).upper() for match in CVE_RE.finditer(text)}
    return (
        versioned_id,
        cves,
        {"title": " ".join(title.split()), "summary": " ".join(summary.split())},
    )


async def _predictions_for_case(
    session: AsyncSession,
    arxiv_id: str,
) -> list[EnrichmentPrediction]:
    root = await session.scalar(
        select(ObjectModel).where(
            ObjectModel.object_type == "ResearchWork",
            ObjectModel.canonical_key == f"arxiv:{_base_id(arxiv_id)}",
        )
    )
    if root is None:
        return []
    rows = (
        await session.execute(
            select(RelationModel, ObjectModel)
            .join(ObjectModel, ObjectModel.object_id == RelationModel.target_object_id)
            .where(
                RelationModel.source_object_id == root.object_id,
                RelationModel.relation_type == "discusses-vulnerability",
                RelationModel.lifecycle == "accepted",
                RelationModel.superseded_revision.is_(None),
            )
        )
    ).all()
    predictions: list[EnrichmentPrediction] = []
    for relation, target in rows:
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
                )
            )
        ).all()
        predictions.append(
            EnrichmentPrediction(
                fact=EnrichmentFactKey(
                    root_object_key=root.canonical_key,
                    root_object_type=root.object_type,
                    kind="relation",
                    dimension=EnrichmentDimension.RESEARCH_PAPER,
                    predicate_or_relation_type=relation.relation_type,
                    normalized_value_or_target_id=target.canonical_key,
                    target_object_type=target.object_type,
                ),
                evidence_ref_ids=tuple(f"evidence:{row.evidence_link_id}" for row in evidence_rows),
                evidence_correct=bool(evidence_rows)
                and any(row.source_id == SOURCE_ID for row in evidence_rows),
            )
        )
    return predictions


async def _run(arxiv_ids: list[str]) -> dict[str, Any]:
    snapshots: dict[str, dict[str, Any]] = {}
    revisions: dict[str, str] = {}
    gold: set[EnrichmentFactKey] = set()
    case_gold: dict[str, list[EnrichmentFactKey]] = {}
    async with httpx.AsyncClient(
        timeout=30.0,
        headers={"User-Agent": "SecFusionAgent-research-eval/0.1"},
    ) as client:
        for requested_id in arxiv_ids:
            versioned_id, cves, snapshot = await _atom_gold(client, requested_id)
            revisions[requested_id] = versioned_id
            snapshots[requested_id] = snapshot
            facts = [_fact(requested_id, cve_id) for cve_id in sorted(cves)]
            case_gold[requested_id] = facts
            gold.update(facts)
    if not gold:
        raise RuntimeError("research exact-CVE benchmark has zero formal gold facts")

    register_runtime_models()
    engine = create_engine()
    factory = create_session_factory(engine)
    predictions: list[EnrichmentPrediction] = []
    case_predictions: dict[str, list[EnrichmentPrediction]] = {item: [] for item in arxiv_ids}
    try:
        async with factory() as session:
            for arxiv_id in arxiv_ids:
                items = await _predictions_for_case(session, arxiv_id)
                predictions.extend(items)
                case_predictions[arxiv_id].extend(items)
    finally:
        await engine.dispose()

    score = score_enrichment(gold=gold, predicted=predictions)
    valid = {item.fact for item in predictions if item.evidence_valid}
    case_scores: dict[str, dict[str, Any]] = {}
    for arxiv_id in arxiv_ids:
        case_score = score_enrichment(
            gold=case_gold[arxiv_id],
            predicted=case_predictions[arxiv_id],
        )
        case_scores[arxiv_id] = {
            "gold_fact_count": len(set(case_gold[arxiv_id])),
            "prediction_count": len(case_predictions[arxiv_id]),
            "score": case_score.model_dump(mode="json"),
        }
    return {
        "profile": "arxiv-exact-cve-v1",
        "fetched_at": datetime.now(UTC).isoformat(),
        "cases": arxiv_ids,
        "paper_revisions": revisions,
        "formal_dimensions": [EnrichmentDimension.RESEARCH_PAPER.value],
        "gold_revision": _gold_revision(gold, revisions),
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
        "snapshots": snapshots,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate exact arXiv paper-to-CVE associations against Atom metadata gold"
    )
    parser.add_argument("arxiv_ids", nargs="+")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = asyncio.run(_run(args.arxiv_ids))
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
