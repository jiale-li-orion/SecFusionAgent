from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from packages.enrichment.runtime.state import EnrichmentStateSnapshot, EnrichmentStatus
from packages.intelligence.knowledge.read import KnowledgeObjectView
from packages.intelligence.knowledge.vocabulary import EnrichmentDimension
from packages.sources.contracts import QuerySpec


class EnrichmentOperatorKind(StrEnum):
    PROVIDER_QUERY = "provider_query"
    DETERMINISTIC_SERVICE = "deterministic_service"


class EnrichmentOperatorSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    operator_id: str
    kind: EnrichmentOperatorKind
    produces: tuple[EnrichmentDimension, ...] = ()
    enables: tuple[EnrichmentDimension, ...] = ()
    source_id: str | None = None
    prerequisite_terms: tuple[str, ...] = ()
    cost_class: str = "low"

    @property
    def relevant_dimensions(self) -> frozenset[EnrichmentDimension]:
        return frozenset((*self.produces, *self.enables))


class EnrichmentOperatorPlan(BaseModel):
    operator_id: str
    kind: EnrichmentOperatorKind
    source_id: str | None = None
    query: QuerySpec | None = None
    relevant_dimensions: list[EnrichmentDimension] = Field(default_factory=list)
    directly_produces: list[EnrichmentDimension] = Field(default_factory=list)
    reason: str


_OPERATOR_SPECS: tuple[EnrichmentOperatorSpec, ...] = (
    EnrichmentOperatorSpec(
        operator_id="provider.cisa_kev",
        kind=EnrichmentOperatorKind.PROVIDER_QUERY,
        source_id="cisa-kev",
        produces=(EnrichmentDimension.EXPLOIT_STATE,),
    ),
    EnrichmentOperatorSpec(
        operator_id="provider.first_epss",
        kind=EnrichmentOperatorKind.PROVIDER_QUERY,
        source_id="first-epss",
        produces=(EnrichmentDimension.EXPLOIT_LIKELIHOOD,),
    ),
    EnrichmentOperatorSpec(
        operator_id="provider.github_advisory",
        kind=EnrichmentOperatorKind.PROVIDER_QUERY,
        source_id="github-global-advisories",
        produces=(EnrichmentDimension.PRODUCT_PACKAGE,),
        enables=(
            EnrichmentDimension.WEAKNESS,
            EnrichmentDimension.VERSION_APPLICABILITY,
            EnrichmentDimension.FIX_REMEDIATION,
            EnrichmentDimension.ADVISORY_REFERENCE,
        ),
    ),
    EnrichmentOperatorSpec(
        operator_id="provider.redhat_csaf_vex",
        kind=EnrichmentOperatorKind.PROVIDER_QUERY,
        source_id="redhat-csaf-vex",
        produces=(EnrichmentDimension.VERSION_APPLICABILITY,),
    ),
    EnrichmentOperatorSpec(
        operator_id="provider.osv",
        kind=EnrichmentOperatorKind.PROVIDER_QUERY,
        source_id="osv-vulnerabilities",
        produces=(EnrichmentDimension.PRODUCT_PACKAGE,),
        enables=(
            EnrichmentDimension.VERSION_APPLICABILITY,
            EnrichmentDimension.FIX_REMEDIATION,
        ),
    ),
    EnrichmentOperatorSpec(
        operator_id="graph.github_references",
        kind=EnrichmentOperatorKind.DETERMINISTIC_SERVICE,
        produces=(EnrichmentDimension.FIX_REMEDIATION,),
        prerequisite_terms=("references", "github_references"),
    ),
    EnrichmentOperatorSpec(
        operator_id="graph.osv_fix_boundary",
        kind=EnrichmentOperatorKind.DETERMINISTIC_SERVICE,
        produces=(EnrichmentDimension.FIX_REMEDIATION,),
        prerequisite_terms=("affects-package",),
    ),
)


def enrichment_operator_registry() -> dict[str, EnrichmentOperatorSpec]:
    return {item.operator_id: item for item in _OPERATOR_SPECS}


class EnrichmentStatePlanner:
    def plan(
        self,
        snapshot: EnrichmentStateSnapshot,
        view: KnowledgeObjectView,
        *,
        cve_id: str,
        target_dimensions: set[EnrichmentDimension] | None = None,
        attempted_operator_ids: set[str] | None = None,
    ) -> list[EnrichmentOperatorPlan]:
        target = target_dimensions or set(EnrichmentDimension)
        attempted = attempted_operator_ids or set()
        missing = {
            state.dimension
            for state in snapshot.dimensions
            if state.dimension in target and state.status is EnrichmentStatus.MISSING
        }
        if not missing:
            return []

        plans: list[EnrichmentOperatorPlan] = []
        for spec in _OPERATOR_SPECS:
            if spec.operator_id in attempted:
                continue
            relevant = sorted(missing & set(spec.relevant_dimensions), key=lambda item: item.value)
            if not relevant:
                continue
            if not _prerequisites_met(spec, view):
                continue
            query = None
            if spec.kind is EnrichmentOperatorKind.PROVIDER_QUERY:
                query = QuerySpec(filters={"cve_id": cve_id.upper()})
            plans.append(
                EnrichmentOperatorPlan(
                    operator_id=spec.operator_id,
                    kind=spec.kind,
                    source_id=spec.source_id,
                    query=query,
                    relevant_dimensions=relevant,
                    directly_produces=[
                        dimension for dimension in relevant if dimension in spec.produces
                    ],
                    reason=_plan_reason(spec, relevant),
                )
            )
        return plans


def _prerequisites_met(spec: EnrichmentOperatorSpec, view: KnowledgeObjectView) -> bool:
    if not spec.prerequisite_terms:
        return True
    predicates = {claim.predicate for claim in view.claims}
    relation_types = {relation.relation_type for relation in view.relations}
    available = predicates | relation_types
    if spec.operator_id == "graph.osv_fix_boundary":
        return any(
            relation.relation_type == "affects-package"
            and isinstance(relation.qualifier.get("ranges"), list)
            for relation in view.relations
        )
    return bool(set(spec.prerequisite_terms) & available)


def _plan_reason(
    spec: EnrichmentOperatorSpec,
    relevant: list[EnrichmentDimension],
) -> str:
    mode = "produce_or_enable" if spec.enables else "produce"
    dimensions = ",".join(item.value for item in relevant)
    return f"{mode}:{dimensions}"
