from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5


def canonical_cve_id(value: str) -> str:
    normalized = value.strip().upper()
    if not normalized.startswith("CVE-"):
        raise ValueError(f"not a CVE identifier: {value!r}")
    return normalized


def cve_canonical_key(cve_id: str) -> str:
    return f"cve:{canonical_cve_id(cve_id)}"


def vulnerability_cve_object_id(cve_id: str) -> str:
    normalized = canonical_cve_id(cve_id)
    return str(uuid5(NAMESPACE_URL, f"secfusion:object:vulnerability:cve:{normalized}"))


def stable_object_id(object_type: str, canonical_key: str) -> str:
    if object_type == "Vulnerability" and canonical_key.lower().startswith("cve:"):
        return vulnerability_cve_object_id(canonical_key.split(":", 1)[1])
    return str(uuid5(NAMESPACE_URL, f"secfusion:object:{object_type}:{canonical_key}"))
