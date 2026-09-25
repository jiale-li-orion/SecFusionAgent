from __future__ import annotations

from typing import Any

from pydantic import JsonValue

from packages.sources.contracts import IngestEnvelope
from packages.sources.errors import SourceSchemaChanged


class NVDHotBugNormalizer:
    def projection(self, envelope: IngestEnvelope) -> dict[str, JsonValue]:
        cve = envelope.json_payload.get("cve")
        if not isinstance(cve, dict):
            raise SourceSchemaChanged("NVD payload has no cve object")
        cve_id = cve.get("id")
        if not isinstance(cve_id, str):
            raise SourceSchemaChanged("NVD cve.id is missing")
        score, severity, vector = _cvss(cve.get("metrics"))
        return {
            "cve_id": cve_id,
            "status": _json_scalar(cve.get("vulnStatus")),
            "description_en": _english_description(cve.get("descriptions")),
            "cvss_score": score,
            "cvss_severity": severity,
            "cvss_vector": vector,
            "cwes": _cwes(cve.get("weaknesses")),
            "references": _references(cve.get("references")),
            "published": _json_scalar(cve.get("published")),
            "last_modified": _json_scalar(cve.get("lastModified")),
        }


def _cvss(metrics: Any) -> tuple[float | None, str | None, str | None]:
    if not isinstance(metrics, dict):
        return None, None, None
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
        if not isinstance(data, dict):
            continue
        score = data.get("baseScore")
        severity = data.get("baseSeverity") or primary.get("baseSeverity")
        vector = data.get("vectorString")
        return (
            float(score) if isinstance(score, (int, float)) else None,
            severity if isinstance(severity, str) else None,
            vector if isinstance(vector, str) else None,
        )
    return None, None, None


def _english_description(value: Any) -> str | None:
    if not isinstance(value, list):
        return None
    for item in value:
        if isinstance(item, dict) and item.get("lang") == "en":
            text = item.get("value")
            return text if isinstance(text, str) else None
    return None


def _cwes(value: Any) -> list[JsonValue]:
    result: list[JsonValue] = []
    if not isinstance(value, list):
        return result
    for weakness in value:
        if not isinstance(weakness, dict):
            continue
        descriptions = weakness.get("description")
        if not isinstance(descriptions, list):
            continue
        for item in descriptions:
            if not isinstance(item, dict):
                continue
            cwe = item.get("value")
            if isinstance(cwe, str) and cwe.startswith("CWE-") and cwe not in result:
                result.append(cwe)
    return result


def _references(value: Any) -> list[JsonValue]:
    result: list[JsonValue] = []
    if not isinstance(value, list):
        return result
    for item in value:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if isinstance(url, str):
            result.append(url)
    return result


def _json_scalar(value: Any) -> JsonValue:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
