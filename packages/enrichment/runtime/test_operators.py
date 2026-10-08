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
        "provider.redhat_csaf_vex",
    }
    direct = {item.operator_id: item.directly_produces for item in plans}
    assert direct["provider.github_advisory"] == []
    assert direct["provider.osv"] == []
    assert direct["provider.redhat_csaf_vex"] == [EnrichmentDimension.VERSION_APPLICABILITY]
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


def test_explicit_refresh_queries_conflict_and_unknown_once_without_changing_default() -> None:
    planner = EnrichmentStatePlanner()
    snapshot = _snapshot(
        exploit_state=EnrichmentStatus.UNKNOWN, product_package=EnrichmentStatus.CONFLICT
    )
    target = {EnrichmentDimension.EXPLOIT_STATE, EnrichmentDimension.PRODUCT_PACKAGE}
    assert planner.plan(snapshot, _view(), cve_id="CVE-2026-42424", target_dimensions=target) == []
    plans = planner.plan(
        snapshot,
        _view(),
        cve_id="CVE-2026-42424",
        target_dimensions=target,
        refresh_dimensions=target,
    )
    operators = {item.operator_id for item in plans}
    assert operators == {"provider.cisa_kev", "provider.github_advisory", "provider.osv"}
    assert (
        planner.plan(
            snapshot,
            _view(),
            cve_id="CVE-2026-42424",
            target_dimensions=target,
            refresh_dimensions=target,
            attempted_operator_ids=operators,
        )
        == []
    )


def test_github_reference_graph_supplements_when_new_reference_is_not_bridged() -> None:
    claim = ClaimView(
        claim_id="claim-ref",
        predicate="references",
        value=[
            "https://github.com/vllm-project/vllm/pull/43426",
            "https://github.com/vllm-project/vllm/commit/abcdef1234567",
        ],
        origin="source_asserted",
        created_revision=1,
    )
    target = RelationTargetView(
        object_id="pr-43426",
        object_type="PullRequest",
        canonical_key="github:vllm-project/vllm:pull:43426",
    )
    existing = RelationView(
        relation_id="reference-rel",
        relation_type="references-development-object",
        origin="deterministic_derived",
        qualifier={
            "reference_kind": "pull_request",
            "reference_url": "https://github.com/vllm-project/vllm/pull/43426",
        },
        created_revision=2,
        target=target,
    )
    plans = EnrichmentStatePlanner().plan(
        _snapshot(fix_remediation=EnrichmentStatus.RESOLVED),
        _view(claims=[claim], relations=[existing]),
        cve_id="CVE-2026-48746",
        target_dimensions={EnrichmentDimension.FIX_REMEDIATION},
    )
    assert [item.operator_id for item in plans] == ["graph.github_references"]


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


def test_github_reference_graph_supplements_resolved_fix_dimension() -> None:
    claim = ClaimView(
        claim_id="claim-ref",
        predicate="github_references",
        value=["https://github.com/vllm-project/vllm/pull/43426"],
        origin="source_asserted",
        created_revision=1,
    )
    plans = EnrichmentStatePlanner().plan(
        _snapshot(fix_remediation=EnrichmentStatus.RESOLVED),
        _view(claims=[claim]),
        cve_id="CVE-2026-48746",
        target_dimensions={EnrichmentDimension.FIX_REMEDIATION},
    )
    assert [item.operator_id for item in plans] == ["graph.github_references"]
    assert plans[0].relevant_dimensions == [EnrichmentDimension.FIX_REMEDIATION]
    assert plans[0].directly_produces == []
    assert plans[0].reason == "supplement:fix_remediation"


def test_osv_fix_boundary_does_not_plan_for_non_git_ranges() -> None:
    target = RelationTargetView(
        object_id="pkg-1",
        object_type="Package",
        canonical_key="package:pypi:vllm",
    )
    relation = RelationView(
        relation_id="rel-1",
        relation_type="affects-package",
        origin="source_asserted",
        qualifier={"ranges": [{"type": "SEMVER", "events": [{"fixed": "0.22.0"}]}]},
        created_revision=1,
        target=target,
    )
    plans = EnrichmentStatePlanner().plan(
        _snapshot(fix_remediation=EnrichmentStatus.RESOLVED),
        _view(relations=[relation]),
        cve_id="CVE-2026-48746",
        target_dimensions={EnrichmentDimension.FIX_REMEDIATION},
    )
    assert plans == []


def test_github_reference_graph_does_not_repeat_when_bridge_exists() -> None:
    claim = ClaimView(
        claim_id="claim-ref",
        predicate="references",
        value=["https://github.com/vllm-project/vllm/pull/43426"],
        origin="source_asserted",
        created_revision=1,
    )
    target = RelationTargetView(
        object_id="pr-43426",
        object_type="PullRequest",
        canonical_key="github:vllm-project/vllm:pull:43426",
    )
    existing = RelationView(
        relation_id="reference-rel",
        relation_type="references-development-object",
        origin="deterministic_derived",
        qualifier={
            "reference_kind": "pull_request",
            "reference_url": "https://github.com/vllm-project/vllm/pull/43426",
        },
        created_revision=2,
        target=target,
    )
    plans = EnrichmentStatePlanner().plan(
        _snapshot(fix_remediation=EnrichmentStatus.RESOLVED),
        _view(claims=[claim], relations=[existing]),
        cve_id="CVE-2026-48746",
        target_dimensions={EnrichmentDimension.FIX_REMEDIATION},
    )
    assert plans == []


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


def test_osv_fix_boundary_supplements_resolved_fix_dimension() -> None:
    target = RelationTargetView(
        object_id="pkg-1",
        object_type="Package",
        canonical_key="package:pypi:vllm",
    )
    relation = RelationView(
        relation_id="rel-1",
        relation_type="affects-package",
        origin="source_asserted",
        qualifier={
            "ranges": [
                {
                    "type": "GIT",
                    "repo": "https://github.com/vllm-project/vllm",
                    "events": [{"fixed": "2b94d1c0"}],
                }
            ]
        },
        created_revision=1,
        target=target,
    )
    plans = EnrichmentStatePlanner().plan(
        _snapshot(fix_remediation=EnrichmentStatus.RESOLVED),
        _view(relations=[relation]),
        cve_id="CVE-2026-42424",
        target_dimensions={EnrichmentDimension.FIX_REMEDIATION},
    )
    assert [item.operator_id for item in plans] == ["graph.osv_fix_boundary"]
    assert plans[0].directly_produces == []
    assert plans[0].reason == "supplement:fix_remediation"
