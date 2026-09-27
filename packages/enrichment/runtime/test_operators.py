from __future__ import annotations

from packages.enrichment.runtime.operators import EnrichmentStatePlanner
from packages.enrichment.runtime.state import (
    EnrichmentDimensionState,
    EnrichmentStateSnapshot,
    EnrichmentStatus,
)
from packages.intelligence.knowledge.read import (
    ClaimView,
    KnowledgeObjectView,
    RelationTargetView,
    RelationView,
)
from packages.intelligence.knowledge.vocabulary import EnrichmentDimension


def _snapshot(**statuses: EnrichmentStatus) -> EnrichmentStateSnapshot:
    dimensions = []
    for dimension in EnrichmentDimension:
        status = statuses.get(dimension.value, EnrichmentStatus.RESOLVED)
        dimensions.append(
            EnrichmentDimensionState(
                target_object_id="vuln-1",
                target_object_type="Vulnerability",
                target_object_key="cve:CVE-2026-42424",
                requirement_id=f"enrichment-v1:Vulnerability:{dimension.value}",
                dimension=dimension,
                status=status,
                world_revision=42,
            )
        )
    return EnrichmentStateSnapshot(
        target_object_id="vuln-1",
        target_object_type="Vulnerability",
        target_object_key="cve:CVE-2026-42424",
        world_revision=42,
        dimensions=dimensions,
    )


def _view(
    *, claims: list[ClaimView] | None = None, relations: list[RelationView] | None = None
) -> KnowledgeObjectView:
    return KnowledgeObjectView(
        object_id="vuln-1",
        object_type="Vulnerability",
        canonical_key="cve:CVE-2026-42424",
        external_identifiers={"cve": ["CVE-2026-42424"]},
        claims=claims or [],
        relations=relations or [],
    )


def test_provider_plan_does_not_claim_enabled_dimension_is_resolved() -> None:
    plans = EnrichmentStatePlanner().plan(
        _snapshot(version_applicability=EnrichmentStatus.MISSING),
        _view(),
        cve_id="CVE-2026-42424",
        target_dimensions={EnrichmentDimension.VERSION_APPLICABILITY},
    )
    assert {item.operator_id for item in plans} == {
        "provider.github_advisory",
        "provider.osv",
    }
    assert all(item.directly_produces == [] for item in plans)
    assert all(item.query is not None for item in plans)


def test_exploit_state_missing_selects_only_kev_provider() -> None:
    plans = EnrichmentStatePlanner().plan(
        _snapshot(exploit_state=EnrichmentStatus.MISSING),
        _view(),
        cve_id="CVE-2026-42424",
        target_dimensions={EnrichmentDimension.EXPLOIT_STATE},
    )
    assert [item.operator_id for item in plans] == ["provider.cisa_kev"]
    assert plans[0].directly_produces == [EnrichmentDimension.EXPLOIT_STATE]


def test_fixed_point_does_not_repeat_operator_within_same_run() -> None:
    plans = EnrichmentStatePlanner().plan(
        _snapshot(product_package=EnrichmentStatus.MISSING),
        _view(),
        cve_id="CVE-2026-42424",
        target_dimensions={EnrichmentDimension.PRODUCT_PACKAGE},
        attempted_operator_ids={"provider.github_advisory", "provider.osv"},
    )
    assert plans == []


def test_github_reference_graph_requires_reference_claim() -> None:
    missing_fix = _snapshot(fix_remediation=EnrichmentStatus.MISSING)
    without = EnrichmentStatePlanner().plan(
        missing_fix,
        _view(),
        cve_id="CVE-2026-42424",
        target_dimensions={EnrichmentDimension.FIX_REMEDIATION},
        attempted_operator_ids={"provider.github_advisory", "provider.osv"},
    )
    assert without == []

    claim = ClaimView(
        claim_id="claim-ref",
        predicate="references",
        value=["https://github.com/vllm-project/vllm/commit/abc"],
        origin="source_asserted",
        created_revision=1,
    )
    with_reference = EnrichmentStatePlanner().plan(
        missing_fix,
        _view(claims=[claim]),
        cve_id="CVE-2026-42424",
        target_dimensions={EnrichmentDimension.FIX_REMEDIATION},
        attempted_operator_ids={"provider.github_advisory", "provider.osv"},
    )
    assert [item.operator_id for item in with_reference] == ["graph.github_references"]


def test_osv_fix_boundary_requires_range_metadata() -> None:
    target = RelationTargetView(
        object_id="pkg-1",
        object_type="Package",
        canonical_key="package:pypi:vllm",
    )
    relation = RelationView(
        relation_id="rel-1",
        relation_type="affects-package",
        origin="source_asserted",
        qualifier={"ranges": [{"type": "GIT", "repo": "https://github.com/vllm-project/vllm"}]},
        created_revision=1,
        target=target,
    )
    plans = EnrichmentStatePlanner().plan(
        _snapshot(fix_remediation=EnrichmentStatus.MISSING),
        _view(relations=[relation]),
        cve_id="CVE-2026-42424",
        target_dimensions={EnrichmentDimension.FIX_REMEDIATION},
        attempted_operator_ids={"provider.github_advisory", "provider.osv"},
    )
    assert [item.operator_id for item in plans] == ["graph.osv_fix_boundary"]
