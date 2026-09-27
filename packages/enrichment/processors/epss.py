from __future__ import annotations

from typing import Any

from pydantic import JsonValue

from packages.intelligence.knowledge.contracts import ClaimCandidate, EnrichmentCandidate
from packages.sources.contracts import IngestEnvelope
from packages.sources.errors import SourceSchemaChanged


class FIRSTEPSSMapper:
    PROCESSOR_NAME = "first-epss-enrichment"
    PROCESSOR_VERSION = "1"

    def map(self, envelope: IngestEnvelope) -> EnrichmentCandidate:
        record = envelope.json_payload.get("record")
        if not isinstance(record, dict):
            raise SourceSchemaChanged("FIRST EPSS payload has no record object")
        cve_id = record.get("cve")
        if not isinstance(cve_id, str) or not cve_id.startswith("CVE-"):
            raise SourceSchemaChanged("FIRST EPSS record has no CVE id")
        probability = _decimal(record.get("epss"), field="epss")
        percentile = _decimal(record.get("percentile"), field="percentile")
        date_value = record.get("date") or record.get("created")
        if not isinstance(date_value, str) or not date_value:
            raise SourceSchemaChanged("FIRST EPSS record has no score date")
        qualifier: dict[str, JsonValue] = {
            "source_semantics": "first_epss",
            "score_date": date_value,
        }
        return EnrichmentCandidate(
            root_identifiers={"cve": [cve_id.upper()]},
            claims=[
                ClaimCandidate(
                    predicate="epss_probability",
                    value=probability,
                    qualifier=qualifier,
                    locator={"kind": "jsonpath", "path": "$.record.epss"},
                ),
                ClaimCandidate(
                    predicate="epss_percentile",
                    value=percentile,
                    qualifier=qualifier,
                    locator={"kind": "jsonpath", "path": "$.record.percentile"},
                ),
            ],
            replace_predicates=["epss_probability", "epss_percentile"],
        )


def _decimal(value: Any, *, field: str) -> float:
    if isinstance(value, bool):
        raise SourceSchemaChanged(f"FIRST EPSS {field} is not numeric")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError as exc:
            raise SourceSchemaChanged(f"FIRST EPSS {field} is not numeric") from exc
    raise SourceSchemaChanged(f"FIRST EPSS {field} is not numeric")
