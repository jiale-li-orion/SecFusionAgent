from __future__ import annotations

from packages.enrichment.assets.service import map_asset_observation
from packages.intelligence.knowledge.contracts import (
    EnrichmentCandidate,
    ObjectCandidate,
    RelationCandidate,
)
from packages.intelligence.knowledge.identity import canonical_cve_id, cve_canonical_key
from packages.sources.contracts import IngestEnvelope


class ShodanInternetDBAssetMapper:
    """Map explicit host-level InternetDB vulnerability assertions into canonical Knowledge."""

    PROCESSOR_NAME = "shodan-internetdb-asset-enrichment"
    PROCESSOR_VERSION = "1"

    def map(self, envelope: IngestEnvelope) -> EnrichmentCandidate:
        asset = map_asset_observation(envelope)
        raw_vulns = envelope.json_payload.get("vulns")
        items = raw_vulns if isinstance(raw_vulns, list) else []
        relations: list[RelationCandidate] = []
        seen: set[str] = set()
        for index, raw in enumerate(items):
            if not isinstance(raw, str):
                continue
            try:
                cve_id = canonical_cve_id(raw)
            except ValueError:
                continue
            if cve_id in seen:
                continue
            seen.add(cve_id)
            relations.append(
                RelationCandidate(
                    relation_type="asset-potentially-affected",
                    target=ObjectCandidate(
                        object_type="Vulnerability",
                        canonical_key=cve_canonical_key(cve_id),
                        properties={"display_name": cve_id},
                        identifiers={"cve": [cve_id]},
                    ),
                    qualifier={"source_semantics": "shodan_internetdb_vulns"},
                    locator={"kind": "jsonpath", "path": f"$.vulns[{index}]"},
                )
            )
        return EnrichmentCandidate(
            root_object=ObjectCandidate(
                object_type="InternetAsset",
                canonical_key=f"internet-asset:ip:{asset.ip}",
                properties={"ip": asset.ip},
                identifiers={"internet_ip": [asset.ip]},
            ),
            relations=relations,
            replace_relation_types=["asset-potentially-affected"],
        )
