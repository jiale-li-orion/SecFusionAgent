from __future__ import annotations

from pydantic import BaseModel

from packages.intelligence.knowledge.read import KnowledgeObjectView
from packages.sources.contracts import QuerySpec


class EnrichmentJobSpec(BaseModel):
    source_id: str
    query: QuerySpec


class VulnerabilityEnrichmentPlanner:
    """Deterministic routing for first-pass vulnerability enrichment."""

    def plan(self, view: KnowledgeObjectView, cve_id: str) -> list[EnrichmentJobSpec]:
        predicates = {claim.predicate for claim in view.claims}
        jobs: list[EnrichmentJobSpec] = []
        if "known_exploited" not in predicates:
            jobs.append(
                EnrichmentJobSpec(
                    source_id="cisa-kev",
                    query=QuerySpec(filters={"cve_id": cve_id.upper()}),
                )
            )
        if not any(predicate.startswith("github_") for predicate in predicates):
            jobs.append(
                EnrichmentJobSpec(
                    source_id="github-global-advisories",
                    query=QuerySpec(filters={"cve_id": cve_id.upper()}),
                )
            )
        if not any(predicate.startswith("osv_") for predicate in predicates):
            jobs.append(
                EnrichmentJobSpec(
                    source_id="osv-vulnerabilities",
                    query=QuerySpec(filters={"cve_id": cve_id.upper()}),
                )
            )
        return jobs
