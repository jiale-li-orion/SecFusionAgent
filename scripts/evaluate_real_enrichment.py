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
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory

DEFAULT_CVES = (
    "CVE-2025-47828",
    "CVE-2024-13980",
    "CVE-2024-13981",
    "CVE-2024-13984",
    "CVE-2024-13985",
)
PROVIDER_SNAPSHOT_SCHEMA = "real-structured-provider-snapshot-v1"
FORMAL_DIMENSIONS = {
    EnrichmentDimension.SEVERITY,
    EnrichmentDimension.WEAKNESS,
    EnrichmentDimension.PRODUCT_PACKAGE,
    EnrichmentDimension.VERSION_APPLICABILITY,
    EnrichmentDimension.FIX_REMEDIATION,
    EnrichmentDimension.EXPLOIT_STATE,
    EnrichmentDimension.EXPLOIT_LIKELIHOOD,
    EnrichmentDimension.ADVISORY_REFERENCE,
}


def _json_normalized(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _claim_fact(
    root_key: str,
    predicate: str,
    value: Any,
    *,
    qualifier: dict[str, Any] | None = None,
    temporal_scope: str = "current",
) -> EnrichmentFactKey:
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
        qualifier_keys=tuple(sorted((qualifier or {}).keys())),
        normalized_qualifier=_json_normalized(qualifier or {}),
        temporal_scope=temporal_scope,
    )


def _relation_fact(
    root_key: str,
    relation_type: str,
    target_key: str,
    target_type: str,
    qualifier: dict[str, Any] | None = None,
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
        qualifier_keys=tuple(sorted((qualifier or {}).keys())),
        normalized_qualifier=_json_normalized(qualifier or {}),
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


def _osv_applicability_qualifier(affected: dict[str, Any]) -> dict[str, Any]:
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


def _osv_fixed_versions(affected: dict[str, Any]) -> list[str]:
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


def _osv_has_package_affected(payload: dict[str, Any]) -> bool:
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


def _osv_ghsa_aliases(payload: dict[str, Any]) -> list[str]:
    aliases = payload.get("aliases")
    if not isinstance(aliases, list):
        return []
    return [item for item in aliases if isinstance(item, str) and item.startswith("GHSA-")]


def _nvd_exploit_urls(cve: dict[str, Any]) -> list[str]:
    result: list[str] = []
    references = cve.get("references")
    if not isinstance(references, list):
        return result
    for item in references:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        tags = item.get("tags")
        if (
            isinstance(url, str)
            and isinstance(tags, list)
            and "Exploit" in tags
            and url not in result
        ):
            result.append(url)
    return result


def _exploit_artifact_key(url: str) -> str:
    digest = sha256(url.strip().encode()).hexdigest()
    return f"exploit-artifact:url-sha256:{digest}"


def _nvd_cpe_applicability(cve: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    configurations = cve.get("configurations")
    if not isinstance(configurations, list):
        return []
    result: list[tuple[str, dict[str, Any]]] = []
    for root_index, root in enumerate(configurations):
        if not isinstance(root, dict):
            continue
        nodes = root.get("nodes")
        if not isinstance(nodes, list):
            continue
        for node_path, node in _walk_nvd_nodes(nodes):
            matches = node.get("cpeMatch")
            if not isinstance(matches, list):
                continue
            for match_index, match in enumerate(matches):
                if not isinstance(match, dict) or match.get("vulnerable") is not True:
                    continue
                criteria = match.get("criteria")
                identity = _cpe23_product_identity(criteria)
                if identity is None:
                    continue
                part, vendor, product = identity
                qualifier: dict[str, Any] = {
                    "state": "affected",
                    "source_semantics": "nvd_cpe",
                    "platform": criteria,
                    "configuration": {
                        "root_index": root_index,
                        "root_operator": root.get("operator"),
                        "root_negate": bool(root.get("negate", False)),
                        "node_path": node_path,
                        "node_operator": node.get("operator"),
                        "node_negate": bool(node.get("negate", False)),
                        "match_index": match_index,
                        "match_criteria_id": match.get("matchCriteriaId"),
                        "root_snapshot": root,
                    },
                }
                version_range = _nvd_cpe_version_range(match)
                if version_range:
                    qualifier["version_range"] = version_range
                result.append((_cpe_product_key(part, vendor, product), qualifier))
    return result


def _walk_nvd_nodes(
    nodes: list[Any],
    prefix: tuple[int, ...] = (),
) -> list[tuple[list[int], dict[str, Any]]]:
    result: list[tuple[list[int], dict[str, Any]]] = []
    for index, raw_node in enumerate(nodes):
        if not isinstance(raw_node, dict):
            continue
        path = [*prefix, index]
        result.append((path, raw_node))
        children = raw_node.get("nodes")
        if isinstance(children, list):
            result.extend(_walk_nvd_nodes(children, tuple(path)))
    return result


def _nvd_cpe_version_range(match: dict[str, Any]) -> dict[str, str]:
    fields = (
        "versionStartIncluding",
        "versionStartExcluding",
        "versionEndIncluding",
        "versionEndExcluding",
    )
    return {
        field: value
        for field in fields
        if isinstance((value := match.get(field)), str) and value
    }


def _cpe23_product_identity(criteria: Any) -> tuple[str, str, str] | None:
    if not isinstance(criteria, str) or not criteria.startswith("cpe:2.3:"):
        return None
    parts = _split_cpe23(criteria)
    if len(parts) < 5:
        return None
    part, vendor, product = parts[2], parts[3], parts[4]
    if any(value in {"", "*", "-"} for value in (part, vendor, product)):
        return None
    return part.lower(), vendor.lower(), product.lower()


def _split_cpe23(value: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    escaped = False
    for char in value:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == ":":
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    if escaped:
        current.append("\\")
    parts.append("".join(current))
    return parts


def _cpe_product_key(part: str, vendor: str, product: str) -> str:
    digest = sha256(f"{part}|{vendor}|{product}".encode()).hexdigest()
    return f"product:cpe23-sha256:{digest}"


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
    settings = get_settings()
    headers = {"Accept": "application/json", "User-Agent": "SecFusionAgent-eval/0.1"}
    github_headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "SecFusionAgent-eval/0.1",
    }
    if settings.github_token:
        github_headers["Authorization"] = f"Bearer {settings.github_token}"
    nvd_headers = dict(headers)
    if settings.nvd_api_key:
        nvd_headers["apiKey"] = settings.nvd_api_key
    nvd_interval_seconds = 0.7 if settings.nvd_api_key else 6.5
    next_nvd_request_at = 0.0

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
            loop = asyncio.get_running_loop()
            nvd_response: httpx.Response | None = None
            for attempt in range(6):
                wait_seconds = max(0.0, next_nvd_request_at - loop.time())
                if wait_seconds:
                    await asyncio.sleep(wait_seconds)
                next_nvd_request_at = loop.time() + nvd_interval_seconds
                try:
                    nvd_response = await client.get(
                        "https://services.nvd.nist.gov/rest/json/cves/2.0",
                        params={"cveId": cve_id},
                        headers=nvd_headers,
                    )
                except httpx.TransportError:
                    if attempt == 5:
                        raise
                    nvd_response = None
                else:
                    if nvd_response.status_code not in {403, 429} and not (
                        500 <= nvd_response.status_code < 600
                    ):
                        break
                    if attempt == 5:
                        nvd_response.raise_for_status()
                next_nvd_request_at = max(
                    next_nvd_request_at,
                    loop.time() + nvd_interval_seconds,
                )
            if nvd_response is None:
                raise RuntimeError("NVD request retry loop produced no response")
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
                headers=github_headers,
            )
            github_response.raise_for_status()
            github_payload = github_response.json()
            if not isinstance(github_payload, list):
                raise RuntimeError(f"GitHub returned invalid advisory list for {cve_id}")

            osv_payloads: list[dict[str, Any]] = []
            osv_response = await client.get(f"https://api.osv.dev/v1/vulns/{cve_id}")
            if osv_response.status_code == 200:
                osv_payload = osv_response.json()
                if not isinstance(osv_payload, dict):
                    raise RuntimeError(f"OSV returned invalid payload for {cve_id}")
                osv_payloads.append(osv_payload)
                if not _osv_has_package_affected(osv_payload):
                    seen_ids = {osv_payload.get("id")}
                    for alias in _osv_ghsa_aliases(osv_payload):
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
                        osv_payloads.append(alias_payload)

            epss_response = await client.get(
                "https://api.first.org/data/v1/epss",
                params={"cve": cve_id},
            )
            epss_response.raise_for_status()
            epss_payload = epss_response.json()
            epss_record = None
            if isinstance(epss_payload, dict) and isinstance(epss_payload.get("data"), list):
                epss_record = next(
                    (
                        item
                        for item in epss_payload["data"]
                        if isinstance(item, dict) and item.get("cve") == cve_id
                    ),
                    None,
                )

            cases[cve_id] = {
                "nvd": cve,
                "github": github_payload,
                "osv": osv_payloads,
                "first_epss": epss_record,
                "known_exploited": cve_id in kev_ids,
            }
        return {
            "snapshot_schema": PROVIDER_SNAPSHOT_SCHEMA,
            "fetched_at": datetime.now(UTC).isoformat(),
            "cisa_catalog_version": kev_payload.get("catalogVersion"),
            "cases": cases,
        }


def _provider_snapshot_revision(snapshot: dict[str, Any]) -> str:
    payload = json.dumps(
        snapshot,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return f"provider-snapshot:{sha256(payload).hexdigest()}"


def _validate_provider_snapshot(snapshot: dict[str, Any], cves: list[str]) -> None:
    if snapshot.get("snapshot_schema") != PROVIDER_SNAPSHOT_SCHEMA:
        raise ValueError(
            f"unsupported provider snapshot schema: {snapshot.get('snapshot_schema')!r}"
        )
    fetched_at = snapshot.get("fetched_at")
    if not isinstance(fetched_at, str) or not fetched_at:
        raise ValueError("provider snapshot fetched_at is missing")
    cases = snapshot.get("cases")
    if not isinstance(cases, dict):
        raise ValueError("provider snapshot cases must be an object")
    expected = [item.upper() for item in cves]
    actual = list(cases)
    if set(actual) != set(expected) or len(actual) != len(expected):
        raise ValueError(
            "provider snapshot case set does not match requested CVEs: "
            f"expected={expected} actual={actual}"
        )
    for cve_id in expected:
        case = cases.get(cve_id)
        if not isinstance(case, dict):
            raise ValueError(f"provider snapshot case is invalid: {cve_id}")
        if not isinstance(case.get("nvd"), dict):
            raise ValueError(f"provider snapshot NVD record is missing: {cve_id}")
        if not isinstance(case.get("github"), list):
            raise ValueError(f"provider snapshot GitHub records are invalid: {cve_id}")
        if not isinstance(case.get("osv"), list):
            raise ValueError(f"provider snapshot OSV records are invalid: {cve_id}")
        if not isinstance(case.get("known_exploited"), bool):
            raise ValueError(f"provider snapshot KEV state is invalid: {cve_id}")
        first_epss = case.get("first_epss")
        if first_epss is not None and not isinstance(first_epss, dict):
            raise ValueError(f"provider snapshot FIRST EPSS record is invalid: {cve_id}")


def _load_provider_snapshot(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("provider snapshot root must be an object")
    return payload


def _write_provider_snapshot(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _gold_from_snapshot(
    snapshot: dict[str, Any],
) -> tuple[list[EnrichmentFactKey], dict[EnrichmentFactKey, set[str]], dict[str, Any]]:
    gold: list[EnrichmentFactKey] = []
    support: dict[EnrichmentFactKey, set[str]] = defaultdict(set)
    diagnostics: dict[str, Any] = {
        "weakness_cwe_gold": 0,
        "nvd_poc_gold": 0,
        "nvd_cpe_applicability_gold": 0,
        "first_epss_gold": 0,
        "github_first_patched_version_gold": 0,
        "github_vulnerable_range_gold": 0,
        "github_epss_gold": 0,
        "advisory_gold": 0,
        "osv_applicability_gold": 0,
        "osv_fixed_version_gold": 0,
        "per_case": {},
    }

    for cve_id, source_data in snapshot["cases"].items():
        root_key = f"cve:{cve_id}"
        cve = source_data["nvd"]
        case_diag: dict[str, Any] = {
            "cwes": _nvd_cwes(cve),
            "nvd_exploit_urls": _nvd_exploit_urls(cve),
            "nvd_cpe_applicability": [],
            "first_patched_versions": [],
            "vulnerable_ranges": [],
            "epss": [],
            "first_epss": None,
            "github_advisories": [],
            "osv_affected_packages": [],
            "osv_fixed_versions": [],
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

        first_epss = source_data.get("first_epss")
        if isinstance(first_epss, dict):
            probability = _float_value(first_epss.get("epss"))
            percentile = _float_value(first_epss.get("percentile"))
            score_date = first_epss.get("date") or first_epss.get("created")
            if (
                probability is not None
                and percentile is not None
                and isinstance(score_date, str)
                and score_date
            ):
                qualifier = {
                    "source_semantics": "first_epss",
                    "score_date": score_date,
                }
                case_diag["first_epss"] = {
                    "probability": probability,
                    "percentile": percentile,
                    "score_date": score_date,
                }
                probability_fact = _claim_fact(
                    root_key,
                    "epss_probability",
                    probability,
                    qualifier=qualifier,
                    temporal_scope=score_date,
                )
                percentile_fact = _claim_fact(
                    root_key,
                    "epss_percentile",
                    percentile,
                    qualifier=qualifier,
                    temporal_scope=score_date,
                )
                gold.extend((probability_fact, percentile_fact))
                support[probability_fact].add("first-epss")
                support[percentile_fact].add("first-epss")
                diagnostics["first_epss_gold"] += 2

        nvd_cpe_facts = _nvd_cpe_applicability(cve)
        diagnostics["nvd_cpe_applicability_gold"] += len(nvd_cpe_facts)
        for target_key, qualifier in nvd_cpe_facts:
            case_diag["nvd_cpe_applicability"].append(
                {
                    "target_key": target_key,
                    "qualifier": qualifier,
                }
            )
            fact = _relation_fact(
                root_key,
                "applicability-status",
                target_key,
                "Product",
                qualifier=qualifier,
            )
            gold.append(fact)
            support[fact].add("nvd-cves-2")

        diagnostics["nvd_poc_gold"] += len(case_diag["nvd_exploit_urls"])
        for url in case_diag["nvd_exploit_urls"]:
            fact = _relation_fact(
                root_key,
                "has-poc",
                _exploit_artifact_key(url),
                "ExploitArtifact",
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
                fact = _relation_fact(
                    root_key,
                    "described-by",
                    f"document:github-advisory:{ghsa_id.lower()}",
                    "Document",
                )
                gold.append(fact)
                support[fact].add("github-global-advisories")
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
                    if isinstance(package, dict):
                        ecosystem = package.get("ecosystem")
                        name = package.get("name")
                        if isinstance(ecosystem, str) and isinstance(name, str):
                            fact = _relation_fact(
                                root_key,
                                "applicability-status",
                                f"package:{ecosystem.lower()}:{name.lower()}",
                                "Package",
                                qualifier={
                                    "state": "affected",
                                    "source_semantics": "github_advisory_range",
                                    "version_range": vulnerable_range,
                                },
                            )
                            gold.append(fact)
                            support[fact].add("github-global-advisories")
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
                                (f"software-version:{ecosystem.lower()}:{name.lower()}:{patched}"),
                                "SoftwareVersion",
                            )
                            gold.append(fact)
                            support[fact].add("github-global-advisories")

        osv_raw = source_data.get("osv")
        osv_payloads = (
            [osv_raw]
            if isinstance(osv_raw, dict)
            else [item for item in osv_raw if isinstance(item, dict)]
            if isinstance(osv_raw, list)
            else []
        )
        for osv_payload in osv_payloads:
            affected_items = osv_payload.get("affected")
            if isinstance(affected_items, list):
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
                    case_diag["osv_affected_packages"].append(package_key)
                    package_fact = _relation_fact(
                        root_key,
                        "affects-package",
                        package_key,
                        "Package",
                    )
                    gold.append(package_fact)
                    support[package_fact].add("osv-vulnerabilities")

                    applicability_fact = _relation_fact(
                        root_key,
                        "applicability-status",
                        package_key,
                        "Package",
                        qualifier=_osv_applicability_qualifier(affected),
                    )
                    gold.append(applicability_fact)
                    support[applicability_fact].add("osv-vulnerabilities")
                    diagnostics["osv_applicability_gold"] += 1

                    for fixed in _osv_fixed_versions(affected):
                        case_diag["osv_fixed_versions"].append(fixed)
                        fixed_fact = _relation_fact(
                            root_key,
                            "fixed-version",
                            (f"software-version:{ecosystem.lower()}:{name.lower()}:{fixed}"),
                            "SoftwareVersion",
                        )
                        gold.append(fixed_fact)
                        support[fixed_fact].add("osv-vulnerabilities")
                        diagnostics["osv_fixed_version_gold"] += 1

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
            qualifier = _benchmark_claim_qualifier(claim.predicate, claim.qualifier)
            temporal_scope = "current"
            score_date = qualifier.get("score_date")
            if isinstance(score_date, str) and score_date:
                temporal_scope = score_date
            fact = _claim_fact(
                root.canonical_key,
                claim.predicate,
                claim.value,
                qualifier=qualifier,
                temporal_scope=temporal_scope,
            )
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
            qualifier = _benchmark_relation_qualifier(
                relation.relation_type,
                relation.qualifier,
            )
            fact = _relation_fact(
                root.canonical_key,
                relation.relation_type,
                target.canonical_key,
                target.object_type,
                qualifier=qualifier,
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


def _benchmark_claim_qualifier(
    predicate: str,
    qualifier: dict[str, Any],
) -> dict[str, Any]:
    if predicate not in {"epss_probability", "epss_percentile"}:
        return {}
    if qualifier.get("source_semantics") != "first_epss":
        return {}
    return {
        key: qualifier[key]
        for key in ("source_semantics", "score_date")
        if key in qualifier
    }


def _benchmark_relation_qualifier(
    relation_type: str,
    qualifier: dict[str, Any],
) -> dict[str, Any]:
    if relation_type != "applicability-status":
        return {}
    allowed = (
        "state",
        "source_semantics",
        "version_range",
        "ranges",
        "versions",
        "platform",
        "configuration",
        "justification",
    )
    return {key: qualifier[key] for key in allowed if key in qualifier}


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


async def _evaluate_snapshot(
    cves: list[str],
    snapshot: dict[str, Any],
    *,
    gold_source_mode: str,
) -> dict[str, Any]:
    _validate_provider_snapshot(snapshot, cves)
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
        "provider_snapshot_schema": PROVIDER_SNAPSHOT_SCHEMA,
        "provider_snapshot_revision": _provider_snapshot_revision(snapshot),
        "gold_source_mode": gold_source_mode,
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
        "structured_diagnostics": diagnostics,
    }
    return report


async def _run(
    cves: list[str],
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if snapshot is None:
        snapshot = await _fetch_gold_snapshot(cves)
        source_mode = "live_snapshot"
    else:
        source_mode = "frozen_snapshot_replay"
    return await _evaluate_snapshot(cves, snapshot, gold_source_mode=source_mode)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate canonical enrichment on live or frozen structured provider gold"
    )
    parser.add_argument("cves", nargs="*")
    parser.add_argument("--snapshot-input", type=Path)
    parser.add_argument("--snapshot-output", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.snapshot_input is not None and args.snapshot_output is not None:
        raise ValueError("--snapshot-input and --snapshot-output are mutually exclusive")

    if args.snapshot_input is not None:
        snapshot = _load_provider_snapshot(args.snapshot_input)
        raw_cases = snapshot.get("cases")
        if not isinstance(raw_cases, dict):
            raise ValueError("provider snapshot cases must be an object")
        cves = [item.upper() for item in args.cves] if args.cves else list(raw_cases)
        _validate_provider_snapshot(snapshot, cves)
        report = asyncio.run(
            _evaluate_snapshot(
                cves,
                snapshot,
                gold_source_mode="frozen_snapshot_replay",
            )
        )
    else:
        cves = [item.upper() for item in args.cves] if args.cves else list(DEFAULT_CVES)
        snapshot = asyncio.run(_fetch_gold_snapshot(cves))
        _validate_provider_snapshot(snapshot, cves)
        if args.snapshot_output is not None:
            _write_provider_snapshot(args.snapshot_output, snapshot)
        report = asyncio.run(
            _evaluate_snapshot(cves, snapshot, gold_source_mode="live_snapshot")
        )
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
