from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from packages.intelligence.normalization.cvelist_v5 import CVEListV5HotBugNormalizer
from packages.intelligence.normalization.nvd_durable import (
    ProjectedVulnerabilityCanonicalNormalizer,
)


class CVEListV5CanonicalNormalizer(ProjectedVulnerabilityCanonicalNormalizer):
    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        super().__init__(
            processor_name="cvelist-v5-canonical-normalizer",
            projection=CVEListV5HotBugNormalizer(),
            locator_for=_cvelist_locator_for,
            now=now,
        )


def _cvelist_locator_for(predicate: str) -> dict[str, object]:
    paths = {
        "status": "$.cveMetadata.state",
        "title": "$.containers.cna.title",
        "description_en": "$.containers.cna.descriptions",
        "assigner": "$.cveMetadata.assignerShortName",
        "affected_products": "$.containers.cna.affected",
        "references": "$.containers.cna.references",
        "published": "$.cveMetadata.datePublished",
        "last_modified": "$.cveMetadata.dateUpdated",
    }
    return {"kind": "jsonpath", "path": paths.get(predicate, "$")}
