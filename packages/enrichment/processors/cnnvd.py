from __future__ import annotations

from typing import Any

from packages.intelligence.knowledge.contracts import ClaimCandidate, EnrichmentCandidate
from packages.sources.contracts import IngestEnvelope
from packages.sources.errors import SourceSchemaChanged


class CNNVDMapper:
    PROCESSOR_NAME = "cnnvd-reference-enrichment"
    PROCESSOR_VERSION = "1"

    def map(self, envelope: IngestEnvelope) -> EnrichmentCandidate:
        payload = envelope.json_payload
        cve_id = payload.get("cveId")
        cnnvd_id = payload.get("cnnvdId") or payload.get("cnnvdCode")
        if not isinstance(cve_id, str) or not cve_id.startswith("CVE-"):
            raise SourceSchemaChanged("CNNVD record has no usable cveId")
        if not isinstance(cnnvd_id, str) or not cnnvd_id:
            raise SourceSchemaChanged("CNNVD record has no cnnvdId/cnnvdCode")

        claims: list[ClaimCandidate] = [
            ClaimCandidate(
                predicate="cnnvd_id",
                value=cnnvd_id,
                locator={"kind": "jsonpath", "path": "$.cnnvdId"},
            )
        ]
        for predicate, field in (
            ("cnnvd_title", "vulName"),
            ("cnnvd_publish_date", "publishDate"),
            ("cnnvd_update_time", "updateTime"),
            ("cnnvd_severity", "levelName"),
            ("cnnvd_type", "vulType"),
        ):
            value = _scalar(payload.get(field))
            if value is not None:
                claims.append(
                    ClaimCandidate(
                        predicate=predicate,
                        value=value,
                        locator={"kind": "jsonpath", "path": f"$.{field}"},
                    )
                )

        return EnrichmentCandidate(
            root_identifiers={
                "cve": [cve_id.upper()],
                "cnnvd": [cnnvd_id],
            },
            claims=claims,
            replace_predicates=[
                "cnnvd_id",
                "cnnvd_title",
                "cnnvd_publish_date",
                "cnnvd_update_time",
                "cnnvd_severity",
                "cnnvd_type",
            ],
        )


def _scalar(value: Any) -> str | int | float | bool | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
