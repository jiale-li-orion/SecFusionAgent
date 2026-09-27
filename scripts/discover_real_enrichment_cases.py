from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from packages.shared.config import get_settings


def _features(advisory: dict[str, Any]) -> dict[str, bool]:
    vulnerabilities = advisory.get("vulnerabilities")
    items = vulnerabilities if isinstance(vulnerabilities, list) else []
    has_range = any(
        isinstance(item, dict)
        and isinstance(item.get("vulnerable_version_range"), str)
        and bool(item.get("vulnerable_version_range"))
        for item in items
    )
    has_fix = any(
        isinstance(item, dict)
        and (
            isinstance(item.get("first_patched_version"), str)
            or (
                isinstance(item.get("first_patched_version"), dict)
                and isinstance(item["first_patched_version"].get("identifier"), str)
            )
        )
        for item in items
    )
    cwes = advisory.get("cwes")
    has_cwe = isinstance(cwes, list) and any(
        isinstance(item, dict) and isinstance(item.get("cwe_id"), str) for item in cwes
    )
    epss = advisory.get("epss")
    has_epss = isinstance(epss, dict) and isinstance(epss.get("percentage"), (int, float))
    return {
        "has_range": has_range,
        "has_fix": has_fix,
        "has_cwe": has_cwe,
        "has_epss": has_epss,
    }


def _bucket(features: dict[str, bool]) -> str:
    if features["has_range"] and features["has_fix"]:
        return "range_and_fix"
    if features["has_range"]:
        return "range_only"
    if features["has_cwe"] and features["has_epss"]:
        return "cwe_epss"
    return "other_structured"


async def _discover_github(count: int) -> dict[str, Any]:
    settings = get_settings()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "SecFusionAgent-eval-discovery/0.1",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        response = await client.get(
            "https://api.github.com/advisories",
            params={"per_page": 100, "sort": "updated", "direction": "desc"},
        )
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError("GitHub advisory discovery response is not a list")

    candidates: list[dict[str, Any]] = []
    seen_cves: set[str] = set()
    for advisory in payload:
        if not isinstance(advisory, dict) or advisory.get("withdrawn_at") is not None:
            continue
        cve_id = advisory.get("cve_id")
        if not isinstance(cve_id, str) or not cve_id.startswith("CVE-") or cve_id in seen_cves:
            continue
        seen_cves.add(cve_id)
        features = _features(advisory)
        candidates.append(
            {
                "cve_id": cve_id,
                "ghsa_id": advisory.get("ghsa_id"),
                "severity": advisory.get("severity"),
                "updated_at": advisory.get("updated_at"),
                "bucket": _bucket(features),
                **features,
            }
        )

    quotas = {
        "range_and_fix": max(1, count // 3),
        "range_only": max(1, count // 6),
        "cwe_epss": max(1, count // 3),
        "other_structured": count,
    }
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    for bucket in ("range_and_fix", "range_only", "cwe_epss", "other_structured"):
        quota = quotas[bucket]
        for item in candidates:
            if len(selected) >= count:
                break
            if item["bucket"] != bucket or item["cve_id"] in selected_ids:
                continue
            selected.append(item)
            selected_ids.add(item["cve_id"])
            quota -= 1
            if quota <= 0:
                break
    if len(selected) < count:
        for item in candidates:
            if len(selected) >= count:
                break
            if item["cve_id"] in selected_ids:
                continue
            selected.append(item)
            selected_ids.add(item["cve_id"])

    return {
        "profile": "recent-github-structured-v1",
        "discovered_at": datetime.now(UTC).isoformat(),
        "requested_count": count,
        "selected_count": len(selected),
        "selection_policy": {
            "source": "GitHub Global Advisories latest 100 by updated desc",
            "requirements": ["cve_id", "not withdrawn"],
            "priority_buckets": [
                "range_and_fix",
                "range_only",
                "cwe_epss",
                "other_structured",
            ],
        },
        "cases": selected,
        "cves": [item["cve_id"] for item in selected],
    }


async def _discover_kev(count: int) -> dict[str, Any]:
    async with httpx.AsyncClient(
        timeout=30.0,
        headers={"User-Agent": "SecFusionAgent-eval-discovery/0.1"},
    ) as client:
        response = await client.get(
            "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
        )
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("vulnerabilities"), list):
        raise RuntimeError("CISA KEV discovery response is invalid")
    candidates = [
        item
        for item in payload["vulnerabilities"]
        if isinstance(item, dict)
        and isinstance(item.get("cveID"), str)
        and item["cveID"].startswith("CVE-")
    ]
    candidates.sort(
        key=lambda item: (
            str(item.get("dateAdded") or ""),
            str(item.get("cveID") or ""),
        ),
        reverse=True,
    )
    selected = [
        {
            "cve_id": item["cveID"],
            "date_added": item.get("dateAdded"),
            "vendor_project": item.get("vendorProject"),
            "product": item.get("product"),
            "known_ransomware_campaign_use": item.get("knownRansomwareCampaignUse"),
        }
        for item in candidates[:count]
    ]
    return {
        "profile": "recent-cisa-kev-v1",
        "discovered_at": datetime.now(UTC).isoformat(),
        "requested_count": count,
        "selected_count": len(selected),
        "selection_policy": {
            "source": "CISA KEV catalog",
            "requirements": ["cveID"],
            "ordering": "dateAdded desc, cveID desc",
            "catalog_version": payload.get("catalogVersion"),
        },
        "cases": selected,
        "cves": [item["cve_id"] for item in selected],
    }


async def _discover(count: int, profile: str) -> dict[str, Any]:
    if profile == "github-structured":
        return await _discover_github(count)
    if profile == "kev-recent":
        return await _discover_kev(count)
    raise ValueError(f"unsupported discovery profile: {profile}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover a reproducible live M3 CVE stratum")
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument(
        "--profile",
        choices=("github-structured", "kev-recent"),
        default="github-structured",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.count < 1 or args.count > 50:
        raise ValueError("count must be between 1 and 50")
    result = asyncio.run(_discover(args.count, args.profile))
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
