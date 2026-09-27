from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

from packages.enrichment.graph.fix_boundary import DeterministicFixBoundaryService
from packages.enrichment.graph.github_references import GitHubReferenceGraphService
from packages.enrichment.planner import EnrichmentJobSpec
from packages.enrichment.runtime.operators import (
    EnrichmentOperatorKind,
    EnrichmentOperatorPlan,
)
from packages.enrichment.runtime.state import (
    EnrichmentAttemptStatus,
    EnrichmentSemanticOutcome,
)
from packages.enrichment.service import VulnerabilityEnrichmentService
from packages.intelligence.knowledge.vocabulary import EnrichmentDimension
from packages.intelligence.normalization.canonical import NormalizationResult
from packages.sources.errors import (
    SourceAuthFailed,
    SourceError,
    SourceFetchFailed,
    SourceRateLimited,
    SourceSchemaChanged,
)


class EnrichmentOperatorExecution(BaseModel):
    operator_id: str
    status: EnrichmentAttemptStatus
    semantic_outcomes: dict[EnrichmentDimension, EnrichmentSemanticOutcome] = Field(
        default_factory=dict
    )
    blocked_reason: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    output_refs: list[str] = Field(default_factory=list)


class EnrichmentOperatorExecutor(Protocol):
    async def execute(
        self,
        plan: EnrichmentOperatorPlan,
        *,
        cve_id: str,
        parent_run_id: str,
    ) -> EnrichmentOperatorExecution: ...


class DefaultEnrichmentOperatorExecutor:
    def __init__(
        self,
        provider_enrichment: VulnerabilityEnrichmentService,
        github_references: GitHubReferenceGraphService,
        fix_boundary: DeterministicFixBoundaryService,
    ) -> None:
        self._provider_enrichment = provider_enrichment
        self._github_references = github_references
        self._fix_boundary = fix_boundary

    async def execute(
        self,
        plan: EnrichmentOperatorPlan,
        *,
        cve_id: str,
        parent_run_id: str,
    ) -> EnrichmentOperatorExecution:
        try:
            results = await self._execute(plan, cve_id=cve_id, parent_run_id=parent_run_id)
        except (SourceFetchFailed, SourceRateLimited, SourceAuthFailed) as exc:
            return EnrichmentOperatorExecution(
                operator_id=plan.operator_id,
                status=EnrichmentAttemptStatus.BLOCKED,
                blocked_reason=type(exc).__name__,
            )
        except SourceSchemaChanged as exc:
            return EnrichmentOperatorExecution(
                operator_id=plan.operator_id,
                status=EnrichmentAttemptStatus.FAILED,
                blocked_reason=f"{type(exc).__name__}:{str(exc)[:512]}",
            )
        except SourceError as exc:
            return EnrichmentOperatorExecution(
                operator_id=plan.operator_id,
                status=EnrichmentAttemptStatus.FAILED,
                blocked_reason=f"{type(exc).__name__}:{str(exc)[:512]}",
            )

        semantic: dict[EnrichmentDimension, EnrichmentSemanticOutcome] = {}
        for dimension in plan.directly_produces:
            if results:
                semantic[dimension] = EnrichmentSemanticOutcome.RESOLVED
            elif plan.operator_id == "provider.cisa_kev":
                # Absence from KEV is not proof that exploitation cannot exist.
                semantic[dimension] = EnrichmentSemanticOutcome.UNKNOWN
            else:
                semantic[dimension] = EnrichmentSemanticOutcome.NO_CHANGE
        return EnrichmentOperatorExecution(
            operator_id=plan.operator_id,
            status=EnrichmentAttemptStatus.SUCCEEDED,
            semantic_outcomes=semantic,
            evidence_refs=sorted({f"observation:{item.observation_id}" for item in results}),
            output_refs=sorted(
                {
                    f"knowledge-revision:{item.knowledge_revision}"
                    for item in results
                    if item.knowledge_revision is not None
                }
            ),
        )

    async def _execute(
        self,
        plan: EnrichmentOperatorPlan,
        *,
        cve_id: str,
        parent_run_id: str,
    ) -> list[NormalizationResult]:
        if plan.kind is EnrichmentOperatorKind.PROVIDER_QUERY:
            if plan.source_id is None or plan.query is None:
                raise ValueError("provider enrichment operator requires source_id and query")
            return await self._provider_enrichment.execute_job(
                cve_id,
                EnrichmentJobSpec(
                    source_id=plan.source_id,
                    query=plan.query,
                    operator_id=plan.operator_id,
                    relevant_dimensions=list(plan.relevant_dimensions),
                ),
                parent_run_id=parent_run_id,
            )
        if plan.operator_id == "graph.github_references":
            return await self._github_references.enrich_cve(cve_id, parent_run_id=parent_run_id)
        if plan.operator_id == "graph.osv_fix_boundary":
            return await self._fix_boundary.enrich_cve(cve_id, parent_run_id=parent_run_id)
        raise ValueError(f"unsupported enrichment operator: {plan.operator_id}")
