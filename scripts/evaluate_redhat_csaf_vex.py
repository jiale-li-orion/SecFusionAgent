from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.runtime_models import register_runtime_models
from packages.evaluation.m1_m3 import EnrichmentFactKey, EnrichmentPrediction, score_enrichment
from packages.intelligence.knowledge.identity import cve_canonical_key
from packages.intelligence.knowledge.vocabulary import EnrichmentDimension, canonical_term
from packages.intelligence.retrieval.validation import visible_at_knowledge_revision
from packages.intelligence.storage.evidence_models import EvidenceArtifactModel, ObservationModel
from packages.intelligence.storage.factory import create_artifact_store
from packages.intelligence.storage.knowledge_models import (
    EvidenceLinkModel,
    KnowledgeRevisionModel,
    ObjectModel,
    RelationModel,
)
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory

SOURCE_ID = "redhat-csaf-vex"
FORMAL_DIMENSIONS = {
    EnrichmentDimension.VERSION_APPLICABILITY,
    EnrichmentDimension.ADVISORY_REFERENCE,
}
STATUS_MAP = {
    "known_affected": "affected",
    "known_not_affected": "not_affected",
    "fixed": "fixed",
    "under_investigation": "under_investigation",
}


def _normalized(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _target_key(publisher_namespace: str, product_id: str) -> str:
    digest = sha256(f"{publisher_namespace}|{product_id}".encode()).hexdigest()
    return f"product:csaf-sha256:{digest}"


def _document_key(url: str) -> str:
    digest = sha256(url.strip().encode()).hexdigest()
    return f"document:url-sha256:{digest}"


def _fact(
    cve_id: str,
    target_key: str,
    qualifier: dict[str, Any],
) -> EnrichmentFactKey:
    term = canonical_term("relation", "applicability-status")
    if term is None:
        raise RuntimeError("applicability-status is not registered")
    return EnrichmentFactKey(
        root_object_key=f"cve:{cve_id}",
        root_object_type="Vulnerability",
        kind="relation",
        dimension=term.dimension,
        predicate_or_relation_type="applicability-status",
        normalized_value_or_target_id=target_key,
        target_object_type="Product",
        qualifier_keys=tuple(sorted(qualifier)),
        normalized_qualifier=_normalized(qualifier),
    )


def _advisory_fact(cve_id: str, url: str) -> EnrichmentFactKey:
    term = canonical_term("relation", "vendor-advisory")
    if term is None:
        raise RuntimeError("vendor-advisory is not registered")
    qualifier = {"source_semantics": "redhat_csaf_vex_document"}
    return EnrichmentFactKey(
        root_object_key=f"cve:{cve_id}",
        root_object_type="Vulnerability",
        kind="relation",
        dimension=term.dimension,
        predicate_or_relation_type="vendor-advisory",
        normalized_value_or_target_id=_document_key(url),
        target_object_type="Document",
        qualifier_keys=tuple(sorted(qualifier)),
        normalized_qualifier=_normalized(qualifier),
    )


def _publisher_namespace(payload: dict[str, Any]) -> str:
    document = payload.get("document")
    publisher = document.get("publisher") if isinstance(document, dict) else None
    namespace = publisher.get("namespace") if isinstance(publisher, dict) else None
    return namespace if isinstance(namespace, str) and namespace else "redhat-security-data"


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
            if isinstance(product, dict) and isinstance(product.get("product_id"), str):
                result[product["product_id"]] = product
            walk(branch.get("branches"))

    walk(tree.get("branches"))
    return result


def _relationship_index(tree: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(tree, dict) or not isinstance(tree.get("relationships"), list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for relation in tree["relationships"]:
        if not isinstance(relation, dict):
            continue
        full = relation.get("full_product_name")
        product_id = full.get("product_id") if isinstance(full, dict) else None
        if isinstance(product_id, str):
            result[product_id] = relation
    return result


def _snapshot(product_id: str, product: dict[str, Any] | None) -> dict[str, Any]:
    result: dict[str, Any] = {"product_id": product_id}
    if product is None:
        return result
    if isinstance(product.get("name"), str):
        result["name"] = product["name"]
    helper = product.get("product_identification_helper")
    if isinstance(helper, dict):
        for key in ("purl", "cpe"):
            if isinstance(helper.get(key), str):
                result[key] = helper[key]
    return result


def _context(
    product_id: str,
    products: dict[str, dict[str, Any]],
    relationships: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {"full_product_id": product_id}
    relation = relationships.get(product_id)
    if relation is None:
        result["product"] = _snapshot(product_id, products.get(product_id))
        return result
    if isinstance(relation.get("category"), str):
        result["relationship_category"] = relation["category"]
    full = relation.get("full_product_name")
    if isinstance(full, dict) and isinstance(full.get("name"), str):
        result["full_product_name"] = full["name"]
    component_id = relation.get("product_reference")
    platform_id = relation.get("relates_to_product_reference")
    if isinstance(component_id, str):
        result["component"] = _snapshot(component_id, products.get(component_id))
    if isinstance(platform_id, str):
        result["platform"] = _snapshot(platform_id, products.get(platform_id))
    return result


def _flags(value: Any) -> dict[str, list[str]]:
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


def _gold_for_case(cve_id: str, snapshot: dict[str, Any]) -> list[EnrichmentFactKey]:
    payload = snapshot.get("payload")
    if not isinstance(payload, dict):
        return []
    vulnerabilities = payload.get("vulnerabilities")
    if not isinstance(vulnerabilities, list):
        return []
    vulnerability = next(
        (item for item in vulnerabilities if isinstance(item, dict) and item.get("cve") == cve_id),
        None,
    )
    if not isinstance(vulnerability, dict):
        return []
    publisher_namespace = _publisher_namespace(payload)
    products = _product_index(payload.get("product_tree"))
    relationships = _relationship_index(payload.get("product_tree"))
    flags = _flags(vulnerability.get("flags"))
    status = vulnerability.get("product_status")
    if not isinstance(status, dict):
        return []
    result: list[EnrichmentFactKey] = []
    canonical_url = snapshot.get("canonical_url")
    if isinstance(canonical_url, str) and canonical_url:
        result.append(_advisory_fact(cve_id, canonical_url))
    for csaf_status, state in STATUS_MAP.items():
        ids = status.get(csaf_status)
        if not isinstance(ids, list):
            continue
        for product_id in ids:
            if not isinstance(product_id, str):
                continue
            qualifier: dict[str, Any] = {
                "state": state,
                "source_semantics": "csaf_vex",
                "csaf_status": csaf_status,
                "scope": {"kind": "csaf_product_status", "product_id": product_id},
                "product_context": _context(product_id, products, relationships),
            }
            if flags.get(product_id):
                qualifier["justification"] = flags[product_id]
            result.append(_fact(cve_id, _target_key(publisher_namespace, product_id), qualifier))
    return result


def _prediction_qualifier(relation: RelationModel) -> dict[str, Any]:
    allowed = (
        "state",
        "source_semantics",
        "csaf_status",
        "scope",
        "product_context",
        "justification",
    )
    return {key: relation.qualifier[key] for key in allowed if key in relation.qualifier}


async def _predictions_for_case(
    session: AsyncSession,
    cve_id: str,
    *,
    knowledge_revision: int,
) -> list[EnrichmentPrediction]:
    root = await session.scalar(
        select(ObjectModel).where(
            ObjectModel.object_type == "Vulnerability",
            ObjectModel.canonical_key == cve_canonical_key(cve_id),
        )
    )
    if root is None or not visible_at_knowledge_revision(
        created_revision=root.created_revision,
        superseded_revision=root.superseded_revision,
        knowledge_revision=knowledge_revision,
    ):
        return []
    object_id = root.object_id
    rows = (
        await session.execute(
            select(RelationModel, ObjectModel)
            .join(ObjectModel, ObjectModel.object_id == RelationModel.target_object_id)
            .where(
                RelationModel.source_object_id == object_id,
                RelationModel.relation_type.in_(("applicability-status", "vendor-advisory")),
                RelationModel.lifecycle == "accepted",
                RelationModel.created_revision <= knowledge_revision,
                or_(
                    RelationModel.superseded_revision.is_(None),
                    RelationModel.superseded_revision > knowledge_revision,
                ),
            )
        )
    ).all()
    result: list[EnrichmentPrediction] = []
    for relation, target in rows:
        if not visible_at_knowledge_revision(
            created_revision=target.created_revision,
            superseded_revision=target.superseded_revision,
            knowledge_revision=knowledge_revision,
        ):
            continue
        if relation.qualifier.get("source_id") != SOURCE_ID:
            continue
        evidence = (
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
        if not evidence:
            continue
        if relation.relation_type == "applicability-status":
            fact = _fact(cve_id, target.canonical_key, _prediction_qualifier(relation))
        else:
            url = target.properties.get("url")
            if not isinstance(url, str) or not url:
                continue
            fact = _advisory_fact(cve_id, url)
        result.append(
            EnrichmentPrediction(
                fact=fact,
                evidence_ref_ids=tuple(f"evidence:{row.evidence_link_id}" for row in evidence),
                evidence_correct=True,
            )
        )
    return result


async def _evidence_snapshots(cves: list[str]) -> dict[str, dict[str, Any]]:
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    store = create_artifact_store(settings)
    result: dict[str, dict[str, Any]] = {}
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
                    raise RuntimeError(f"no persisted Red Hat CSAF VEX Evidence for {cve_id}")
                observation, artifact = item
                knowledge_revision = await session.scalar(
                    select(func.max(KnowledgeRevisionModel.revision)).where(
                        KnowledgeRevisionModel.cause_observation_id == observation.observation_id
                    )
                )
                if knowledge_revision is None:
                    raise RuntimeError(
                        f"no Knowledge revision for persisted CSAF VEX Evidence {cve_id}"
                    )
                payload = json.loads(await store.get(artifact.storage_uri))
                if not isinstance(payload, dict):
                    raise RuntimeError(f"invalid persisted CSAF VEX Evidence for {cve_id}")
                result[cve_id] = {
                    "canonical_url": observation.canonical_url,
                    "external_revision": observation.external_revision,
                    "observation_id": observation.observation_id,
                    "observed_at": observation.observed_at.isoformat(),
                    "knowledge_revision": int(knowledge_revision),
                    "payload": payload,
                }
    finally:
        await engine.dispose()
    return result


def _revision(prefix: str, value: Any) -> str:
    digest = sha256(_normalized(value).encode()).hexdigest()
    return f"{prefix}:{digest}"


async def _run(cves: list[str]) -> dict[str, Any]:
    snapshots = await _evidence_snapshots(cves)
    case_gold = {cve: _gold_for_case(cve, payload) for cve, payload in snapshots.items()}
    gold = {fact for facts in case_gold.values() for fact in facts}
    if not gold:
        raise RuntimeError("Red Hat CSAF VEX benchmark has zero formal gold facts")
    prediction_knowledge_revision = max(
        int(snapshot["knowledge_revision"]) for snapshot in snapshots.values()
    )
    fetched_at = max(
        datetime.fromisoformat(str(snapshot["observed_at"]).replace("Z", "+00:00"))
        for snapshot in snapshots.values()
    ).astimezone(UTC)

    engine = create_engine()
    factory = create_session_factory(engine)
    case_predictions: dict[str, list[EnrichmentPrediction]] = {}
    try:
        async with factory() as session:
            for cve_id in cves:
                case_predictions[cve_id] = await _predictions_for_case(
                    session,
                    cve_id,
                    knowledge_revision=prediction_knowledge_revision,
                )
    finally:
        await engine.dispose()
    predictions = [item for values in case_predictions.values() for item in values]
    score = score_enrichment(gold=gold, predicted=predictions)
    valid = {item.fact for item in predictions if item.evidence_valid}
    return {
        "profile": "redhat-csaf-vex-source-specific-v2",
        "fetched_at": fetched_at.isoformat(),
        "cases": cves,
        "formal_dimensions": [
            EnrichmentDimension.VERSION_APPLICABILITY.value,
            EnrichmentDimension.ADVISORY_REFERENCE.value,
        ],
        "gold_revision": _revision(
            "csaf-vex",
            [
                item.model_dump(mode="json")
                for item in sorted(gold, key=lambda x: x.normalized_value_or_target_id)
            ],
        ),
        "provider_snapshot_revision": _revision(
            "provider-snapshot",
            {
                cve: {
                    "canonical_url": snapshot["canonical_url"],
                    "external_revision": snapshot["external_revision"],
                    "payload": snapshot["payload"],
                }
                for cve, snapshot in snapshots.items()
            },
        ),
        "prediction_knowledge_revision": prediction_knowledge_revision,
        "prediction_world_ref": f"knowledge-revision:{prediction_knowledge_revision}",
        "gold_source_mode": "frozen_snapshot_replay",
        "gold_fact_count": len(gold),
        "prediction_count": len(predictions),
        "score": score.model_dump(mode="json"),
        "case_scores": {
            cve: {
                "gold_fact_count": len(set(case_gold[cve])),
                "prediction_count": len(case_predictions[cve]),
                "score": score_enrichment(
                    gold=case_gold[cve], predicted=case_predictions[cve]
                ).model_dump(mode="json"),
            }
            for cve in cves
        },
        "missing_facts": [
            item.model_dump(mode="json")
            for item in sorted(gold - valid, key=lambda x: x.normalized_value_or_target_id)
        ],
        "extra_facts": [
            item.model_dump(mode="json")
            for item in sorted(valid - gold, key=lambda x: x.normalized_value_or_target_id)
        ],
        "status_counts": {
            state: sum(
                1 for fact in gold if json.loads(fact.normalized_qualifier).get("state") == state
            )
            for state in ("affected", "not_affected", "fixed", "under_investigation")
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Red Hat CSAF/VEX product applicability")
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
