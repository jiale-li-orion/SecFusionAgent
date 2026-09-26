from __future__ import annotations

from typing import Any

from pydantic import JsonValue

from packages.sources.contracts import IngestEnvelope
from packages.sources.errors import SourceSchemaChanged


class CVEListV5HotBugNormalizer:
    def projection(self, envelope: IngestEnvelope) -> dict[str, JsonValue]:
        payload = envelope.json_payload
        metadata = payload.get("cveMetadata")
        containers = payload.get("containers")
        if not isinstance(metadata, dict) or not isinstance(containers, dict):
            raise SourceSchemaChanged("cvelistV5 payload is missing metadata/containers")
        cve_id = metadata.get("cveId")
        if not isinstance(cve_id, str):
            raise SourceSchemaChanged("cvelistV5 cveMetadata.cveId is missing")
        cna = containers.get("cna")
        cna_obj = cna if isinstance(cna, dict) else {}
        return {
            "cve_id": cve_id,
            "status": _scalar(metadata.get("state")),
            "title": _scalar(cna_obj.get("title")),
            "description_en": _english_description(cna_obj.get("descriptions")),
            "assigner": _scalar(metadata.get("assignerShortName")),
            "affected_products": _affected_products(cna_obj.get("affected")),
            "references": _references(cna_obj.get("references")),
            "published": _scalar(metadata.get("datePublished")),
            "last_modified": _scalar(metadata.get("dateUpdated")),
        }


def _english_description(value: Any) -> str | None:
    if not isinstance(value, list):
        return None
    for item in value:
        if not isinstance(item, dict):
            continue
        if str(item.get("lang", "")).lower().startswith("en"):
            text = item.get("value")
            return text if isinstance(text, str) else None
    return None


def _affected_products(value: Any) -> list[JsonValue]:
    result: list[JsonValue] = []
    if not isinstance(value, list):
        return result
    for item in value:
        if not isinstance(item, dict):
            continue
        vendor = item.get("vendor")
        product = item.get("product") or item.get("packageName")
        if isinstance(product, str):
            label = f"{vendor}/{product}" if isinstance(vendor, str) and vendor else product
            if label not in result:
                result.append(label)
    return result


def _references(value: Any) -> list[JsonValue]:
    result: list[JsonValue] = []
    if not isinstance(value, list):
        return result
    for item in value:
        if isinstance(item, dict) and isinstance(item.get("url"), str):
            result.append(item["url"])
    return result


def _scalar(value: Any) -> JsonValue:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
