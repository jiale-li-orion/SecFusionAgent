from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.runtime_models import register_runtime_models
from packages.evaluation.m1_m3 import (
    EnrichmentFactKey,
    EnrichmentPrediction,
    EnrichmentScore,
    score_enrichment,
)
from packages.intelligence.knowledge.vocabulary import EnrichmentDimension, canonical_term
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    EvidenceLinkModel,
    ExternalIdentifierModel,
    ObjectModel,
    RelationModel,
)
from packages.shared.db import create_engine, create_session_factory

DEFAULT_CVES = (
    "CVE-2025-47828",
    "CVE-2024-13980",
    "CVE-2024-13981",
    "CVE-2024-13984",
    "CVE-2024-13985",
)
FORMAL_DIMENSIONS = {
    EnrichmentDimension.SEVERITY,
    EnrichmentDimension.WEAKNESS,
    EnrichmentDimension.PRODUCT_PACKAGE,
    EnrichmentDimension.FIX_REMEDIATION,
    EnrichmentDimension.EXPLOIT_STATE,
    EnrichmentDimension.EXPLOIT_LIKELIHOOD,
}


def _json_normalized(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _claim_fact(root_key: str, predicate: str, value: Any) -> EnrichmentFactKey:
    term = canonical_term("claim", predicate)
    if term is None:
        raise ValueError(f"unknown canonical claim: {predicate}")
    return EnrichmentFactKey(
        root_object_key=root_key,
        root_object_type="Vulnerability",
        kind="claim",
        dimension=term.dimension,
        predicate_or_relation_type=predicate,
        normalized_value_or_target_id=_json_normalized(value),
    )


def _relation_fact(
    root_key: str,
    relation_type: str,
    target_key: str,
    target_type: str,
) -> EnrichmentFactKey:
    term = canonical_term("relation", relation_type)
    if term is None:
        raise ValueError(f"unknown canonical relation: {relation_type}")
    return EnrichmentFactKey(
        root_object_key=root_key,
        root_object_type="Vulnerability",
        kind="relation",
        dimension=term.dimension,
        predicate_or_relation_type=relation_type,
        normalized_value_or_target_id=target_key,
        target_object_type=target_type,
    )


def _nvd_primary_metric(cve: dict[str, Any]) -> dict[str, Any] | None:
    metrics = cve.get("metrics")
    if not isinstance(metrics, dict):
        return None
    for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        entries = metrics.get(key)
        if not isinstance(entries, list) or not entries:
            continue
        primary = next(
            (item for item in entries if isinstance(item, dict) and item.get("type") == "Primary"),
            entries[0],
        )
        if not isinstance(primary, dict):
            continue
        data = primary.get("cvssData")
        if isinstance(data, dict):
            return data
    return None


def _nvd_cwes(cve: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for weakness in cve.get("weaknesses", []):
        if not isinstance(weakness, dict):
            continue
        for item in weakness.get("description", []):
            if not isinstance(item, dict) or item.get("lang") != "en":
                continue
            value = item.get("value")
            if isinstance(value, str) and value.startswith("CWE-") and value not in result:
                result.append(value)
    return result


def _github_cwes(advisory: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for item in advisory.get("cwes", []):
        if not isinstance(item, dict):
            continue
        value = item.get("cwe_id")
        if isinstance(value, str) and value.startswith("CWE-") and value not in result:
            result.append(value)
    return result


def _first_patched_version(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, dict):
        identifier = value.get("identifier")
        if isinstance(identifier, str) and identifier:
            return identifier
    return None


async def _fetch_gold_snapshot(cves: list[str]) -> dict[str, Any]:
    headers = {"Accept": "application/json", "User-Agent": "SecFusionAgent-eval/0.1"}
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        kev_response = await client.get(
            "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
        )
        kev_response.raise_for_status()
        kev_payload = kev_response.json()
        kev_ids = {
            item.get("cveID")
            for item in kev_payload.get("vulnerabilities", [])
            if isinstance(item, dict)
        }

        cases: dict[str, Any] = {}
        for cve_id in cves:
            nvd_response = await client.get(
                "https://services.nvd.nist.gov/rest/json/cves/2.0",
                params={"cveId": cve_id},
            )
            nvd_response.raise_for_status()
            nvd_payload = nvd_response.json()
            vulnerabilities = nvd_payload.get("vulnerabilities", [])
            if not vulnerabilities or not isinstance(vulnerabilities[0], dict):
                raise RuntimeError(f"NVD returned no vulnerability for {cve_id}")
            cve = vulnerabilities[0].get("cve")
            if not isinstance(cve, dict):
                raise RuntimeError(f"NVD returned invalid vulnerability for {cve_id}")

            github_response = await client.get(
                "https://api.github.com/advisories",
                params={"cve_id": cve_id},
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "SecFusionAgent-eval/0.1",
                },
            )
            github_response.raise_for_status()
            github_payload = github_response.json()
            if not isinstance(github_payload, list):
                raise RuntimeError(f"GitHub returned invalid advisory list for {cve_id}")

            osv_response = await client.get(f"https://api.osv.dev/v1/vulns/{cve_id}")
            osv_payload = osv_response.json() if osv_response.status_code == 200 else None

            cases[cve_id] = {
                "nvd": cve,
                "github": github_payload,
                "osv": osv_payload,
                "known_exploited": cve_id in kev_ids,
            }
        return {
            "fetched_at": datetime.now(UTC).isoformat(),
            "cisa_catalog_version": kev_payload.get("catalogVersion"),
            "cases": cases,
        }


def _gold_from_snapshot(
    snapshot: dict[str, Any],
) -> tuple[list[EnrichmentFactKey], dict[EnrichmentFactKey, set[str]], dict[str, Any]]:
    gold: list[EnrichmentFactKey] = []
    support: dict[EnrichmentFactKey, set[str]] = defaultdict(set)
    diagnostics: dict[str, Any] = {
        "weakness_cwe_gold": 0,
        "github_first_patched_version_gold": 0,
        "github_vulnerable_range_gold": 0,
        "github_epss_gold": 0,
        "advisory_gold": 0,
        "per_case": {},
    }

    for cve_id, source_data in snapshot["cases"].items():
        root_key = f"cve:{cve_id}"
        cve = source_data["nvd"]
        case_diag: dict[str, Any] = {
            "cwes": _nvd_cwes(cve),
            "first_patched_versions": [],
            "vulnerable_ranges": [],
            "epss": [],
            "github_advisories": [],
        }
        metric = _nvd_primary_metric(cve)
        if metric is not None:
            fields = (
                ("cvss_score", metric.get("baseScore")),
                ("cvss_severity", metric.get("baseSeverity")),
                ("cvss_vector", metric.get("vectorString")),
                ("cvss_version", metric.get("version")),
            )
            for predicate, value in fields:
                if value is None:
                    continue
                fact = _claim_fact(root_key, predicate, value)
                gold.append(fact)
                support[fact].add("nvd-cves-2")

        diagnostics["weakness_cwe_gold"] += len(case_diag["cwes"])
        for cwe_id in case_diag["cwes"]:
            fact = _relation_fact(
                root_key,
                "has-weakness",
                f"weakness:{cwe_id}",
                "Weakness",
            )
            gold.append(fact)
            support[fact].add("nvd-cves-2")

        seen_packages: set[str] = set()
        for advisory in source_data["github"]:
            if not isinstance(advisory, dict):
                continue
            ghsa_id = advisory.get("ghsa_id")
            if isinstance(ghsa_id, str):
                case_diag["github_advisories"].append(ghsa_id)
                diagnostics["advisory_gold"] += 1
            for cwe_id in _github_cwes(advisory):
                fact = _relation_fact(
                    root_key,
                    "has-weakness",
                    f"weakness:{cwe_id}",
                    "Weakness",
                )
                gold.append(fact)
                support[fact].add("github-global-advisories")
            epss = advisory.get("epss")
            if isinstance(epss, dict):
                percentage = epss.get("percentage")
                percentile = epss.get("percentile")
                if isinstance(percentage, (int, float)) and isinstance(percentile, (int, float)):
                    case_diag["epss"].append(
                        {"probability": float(percentage), "percentile": float(percentile)}
                    )
                    diagnostics["github_epss_gold"] += 2
                    probability_fact = _claim_fact(
                        root_key,
                        "epss_probability",
                        float(percentage),
                    )
                    percentile_fact = _claim_fact(
                        root_key,
                        "epss_percentile",
                        float(percentile),
                    )
                    gold.extend((probability_fact, percentile_fact))
                    support[probability_fact].add("github-global-advisories")
                    support[percentile_fact].add("github-global-advisories")
            for vulnerability in advisory.get("vulnerabilities", []):
                if not isinstance(vulnerability, dict):
                    continue
                package = vulnerability.get("package")
                if isinstance(package, dict):
                    ecosystem = package.get("ecosystem")
                    name = package.get("name")
                    if isinstance(ecosystem, str) and isinstance(name, str):
                        target_key = f"package:{ecosystem.lower()}:{name.lower()}"
                        if target_key not in seen_packages:
                            fact = _relation_fact(
                                root_key,
                                "affects-package",
                                target_key,
                                "Package",
                            )
                            gold.append(fact)
                            support[fact].add("github-global-advisories")
                            seen_packages.add(target_key)
                vulnerable_range = vulnerability.get("vulnerable_version_range")
                if isinstance(vulnerable_range, str) and vulnerable_range:
                    case_diag["vulnerable_ranges"].append(vulnerable_range)
                    diagnostics["github_vulnerable_range_gold"] += 1
                patched = _first_patched_version(vulnerability.get("first_patched_version"))
                if patched:
                    case_diag["first_patched_versions"].append(patched)
                    diagnostics["github_first_patched_version_gold"] += 1
                    if isinstance(package, dict):
                        ecosystem = package.get("ecosystem")
                        name = package.get("name")
                        if isinstance(ecosystem, str) and isinstance(name, str):
                            fact = _relation_fact(
                                root_key,
                                "fixed-version",
                                (
                                    f"software-version:{ecosystem.lower()}:"
                                    f"{name.lower()}:{patched}"
                                ),
                                "SoftwareVersion",
                            )
                            gold.append(fact)
                            support[fact].add("github-global-advisories")

        if source_data["known_exploited"] is True:
            fact = _claim_fact(root_key, "known_exploited", True)
            gold.append(fact)
            support[fact].add("cisa-kev")

        diagnostics["per_case"][cve_id] = case_diag

    return gold, support, diagnostics


async def _current_predictions(
    session: AsyncSession,
    cves: list[str],
    gold_support: dict[EnrichmentFactKey, set[str]],
) -> list[EnrichmentPrediction]:
    predictions: list[EnrichmentPrediction] = []
    for cve_id in cves:
        object_id = await session.scalar(
            select(ExternalIdentifierModel.object_id).where(
                ExternalIdentifierModel.namespace == "cve",
                ExternalIdentifierModel.value == cve_id,
            )
        )
        if object_id is None:
            continue
        root = await session.get(ObjectModel, object_id)
        if root is None:
            continue

        claims = list(
            await session.scalars(
                select(ClaimModel).where(
                    ClaimModel.subject_id == object_id,
                    ClaimModel.lifecycle == "accepted",
                    ClaimModel.superseded_revision.is_(None),
                )
            )
        )
        for claim in claims:
            term = canonical_term("claim", claim.predicate)
            if term is None or not term.benchmarked or term.dimension not in FORMAL_DIMENSIONS:
                continue
            fact = _claim_fact(root.canonical_key, claim.predicate, claim.value)
            predictions.append(
                await _prediction_for_target(
                    session,
                    fact=fact,
                    target_kind="claim",
                    target_id=claim.claim_id,
                    gold_support=gold_support,
                )
            )

        relations = (
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
        for relation, target in relations:
            term = canonical_term("relation", relation.relation_type)
            if term is None or not term.benchmarked or term.dimension not in FORMAL_DIMENSIONS:
                continue
            if term.required_qualifier_keys:
                continue
            fact = _relation_fact(
                root.canonical_key,
                relation.relation_type,
                target.canonical_key,
                target.object_type,
            )
            predictions.append(
                await _prediction_for_target(
                    session,
                    fact=fact,
                    target_kind="relation",
                    target_id=relation.relation_id,
                    gold_support=gold_support,
                )
            )
    return predictions


async def _prediction_for_target(
    session: AsyncSession,
    *,
    fact: EnrichmentFactKey,
    target_kind: str,
    target_id: str,
    gold_support: dict[EnrichmentFactKey, set[str]],
) -> EnrichmentPrediction:
    rows = (
        await session.execute(
            select(EvidenceLinkModel.evidence_link_id, ObservationModel.source_id)
            .join(
                ObservationModel,
                ObservationModel.observation_id == EvidenceLinkModel.observation_id,
            )
            .where(
                EvidenceLinkModel.target_kind == target_kind,
                EvidenceLinkModel.target_id == target_id,
            )
        )
    ).all()
    evidence_refs = tuple(f"evidence:{row.evidence_link_id}" for row in rows)
    expected_sources = gold_support.get(fact)
    evidence_correct = bool(rows) and (
        expected_sources is None or any(row.source_id in expected_sources for row in rows)
    )
    return EnrichmentPrediction(
        fact=fact,
        evidence_ref_ids=evidence_refs,
        evidence_correct=evidence_correct,
    )


def _dimension_summary(score: EnrichmentScore) -> dict[str, Any]:
    return {
        item.dimension.value: {
            "tp": item.true_positive,
            "fp": item.false_positive,
            "fn": item.false_negative,
            "precision": item.precision,
            "recall": item.recall,
        }
        for item in score.dimensions
    }


def _gold_revision(gold: list[EnrichmentFactKey]) -> str:
    payload = sorted(
        (item.model_dump(mode="json") for item in set(gold)),
        key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
    )
    digest = sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    return f"real-structured:{digest}"


def _case_scores(
    cves: list[str],
    gold: list[EnrichmentFactKey],
    predicted: list[EnrichmentPrediction],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for cve_id in cves:
        root_key = f"cve:{cve_id}"
        case_gold = [item for item in gold if item.root_object_key == root_key]
        case_predicted = [item for item in predicted if item.fact.root_object_key == root_key]
        score = score_enrichment(gold=case_gold, predicted=case_predicted)
        result[cve_id] = {
            "gold_fact_count": len(set(case_gold)),
            "prediction_count": len(case_predicted),
            "score": score.model_dump(mode="json"),
            "dimension_summary": _dimension_summary(score),
        }
    return result


async def _run(cves: list[str]) -> dict[str, Any]:
    snapshot = await _fetch_gold_snapshot(cves)
    gold, support, diagnostics = _gold_from_snapshot(snapshot)

    register_runtime_models()
    engine = create_engine()
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            predicted = await _current_predictions(session, cves, support)
    finally:
        await engine.dispose()

    score = score_enrichment(gold=gold, predicted=predicted)
    gold_set = set(gold)
    valid_prediction_set = {item.fact for item in predicted if item.evidence_valid}
    missing = sorted(
        gold_set - valid_prediction_set,
        key=lambda item: (
            item.root_object_key,
            item.dimension.value,
            item.predicate_or_relation_type,
            item.normalized_value_or_target_id,
        ),
    )
    extras = sorted(
        valid_prediction_set - gold_set,
        key=lambda item: (
            item.root_object_key,
            item.dimension.value,
            item.predicate_or_relation_type,
            item.normalized_value_or_target_id,
        ),
    )
    report = {
        "profile": "real-structured-v1",
        "gold_revision": _gold_revision(gold),
        "fetched_at": snapshot["fetched_at"],
        "cisa_catalog_version": snapshot["cisa_catalog_version"],
        "cases": cves,
        "formal_dimensions": sorted(item.value for item in FORMAL_DIMENSIONS),
        "gold_fact_count": len(gold_set),
        "gold_facts": [
            item.model_dump(mode="json")
            for item in sorted(
                gold_set,
                key=lambda item: (
                    item.root_object_key,
                    item.dimension.value,
                    item.predicate_or_relation_type,
                    item.normalized_value_or_target_id,
                ),
            )
        ],
        "prediction_count": len(predicted),
        "valid_prediction_count": len(valid_prediction_set),
        "score": score.model_dump(mode="json"),
        "dimension_summary": _dimension_summary(score),
        "case_scores": _case_scores(cves, gold, predicted),
        "missing_facts": [item.model_dump(mode="json") for item in missing],
        "extra_facts": [item.model_dump(mode="json") for item in extras],
        "diagnostics_not_in_formal_score": diagnostics,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate canonical enrichment on live structured provider gold"
    )
    parser.add_argument("cves", nargs="*", default=list(DEFAULT_CVES))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = asyncio.run(_run([item.upper() for item in args.cves]))
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
