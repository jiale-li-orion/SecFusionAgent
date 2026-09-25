from __future__ import annotations

from typing import Any

from packages.intelligence.knowledge.contracts import ClaimCandidate, EnrichmentCandidate
from packages.sources.contracts import IngestEnvelope
from packages.sources.errors import SourceSchemaChanged


class CISAKEVMapper:
    PROCESSOR_NAME = "cisa-kev-enrichment"
    PROCESSOR_VERSION = "1"

    def map(self, envelope: IngestEnvelope) -> EnrichmentCandidate:
        vulnerability = envelope.json_payload.get("vulnerability")
        if not isinstance(vulnerability, dict):
            raise SourceSchemaChanged("CISA KEV payload has no vulnerability object")
        cve_id = vulnerability.get("cveID")
        if not isinstance(cve_id, str):
            raise SourceSchemaChanged("CISA KEV vulnerability has no cveID")

        claims = [
            ClaimCandidate(
                predicate="known_exploited",
                value=True,
                locator={"kind": "jsonpath", "path": "$.vulnerability.cveID"},
            )
        ]
        for predicate, field in [
            ("kev_date_added", "dateAdded"),
            ("kev_due_date", "dueDate"),
            ("kev_required_action", "requiredAction"),
            ("kev_ransomware_campaign_use", "knownRansomwareCampaignUse"),
            ("kev_vendor_project", "vendorProject"),
            ("kev_product", "product"),
            ("kev_vulnerability_name", "vulnerabilityName"),
        ]:
            value = _json_value(vulnerability.get(field))
            if value is not None:
                claims.append(
                    ClaimCandidate(
                        predicate=predicate,
                        value=value,
                        locator={"kind": "jsonpath", "path": f"$.vulnerability.{field}"},
                    )
                )
        return EnrichmentCandidate(
            root_identifiers={"cve": [cve_id.upper()]},
            claims=claims,
            replace_predicates=[
                "known_exploited",
                "kev_date_added",
                "kev_due_date",
                "kev_required_action",
                "kev_ransomware_campaign_use",
                "kev_vendor_project",
                "kev_product",
                "kev_vulnerability_name",
            ],
        )


def _json_value(value: Any) -> str | int | float | bool | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
