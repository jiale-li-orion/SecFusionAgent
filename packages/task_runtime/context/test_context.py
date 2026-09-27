from __future__ import annotations

import pytest

from packages.task_runtime.context.contracts import (
    ChildContextSpec,
    ContextCompatibilityStatus,
    ContextDependencySet,
    ContextRefresh,
    ContextResultProvenance,
)
from packages.task_runtime.context.service import (
    ContextRevisionGate,
    derive_child_context,
    diff_contexts,
    filter_context,
    fork_context,
    merge_contexts,
    pin_context,
    refresh_context,
)
from packages.task_runtime.contracts.models import (
    CancellationSemantics,
    ContextManifest,
    DelegationCeiling,
    EffectCeiling,
    TaskContract,
    TaskKind,
)
from packages.task_runtime.contracts.roles import canonical_roles


def _contract(
    *,
    task_id: str,
    kind: TaskKind,
) -> TaskContract:
    return TaskContract(
        task_contract_id=task_id,
        contract_revision=1,
        principal="user:alice",
        task_kind=kind,
        target_resources=["object:vuln-1"],
        desired_state={"goal": "test"},
        evidence_contract={},
        output_contract={},
        temporal_contract={"scope": "current"},
        effect_ceiling=EffectCeiling.INTERNAL_STATE,
        delegation_ceiling=DelegationCeiling(),
        completion_predicate={"type": "test"},
        cancellation_semantics=CancellationSemantics.CANCELLABLE,
        policy_revision="policy-v1",
    )


def _parent() -> ContextManifest:
    return ContextManifest(
        context_id="context-parent",
        context_revision=3,
        task_contract_ref="parent-task@1",
        role_ref="InvestigationRole@1",
        case_ref="case-1",
        knowledge_revision=42,
        investigation_state_ref="case:case-1@7",
        enrichment_state_refs=["enrichment:vuln-1:severity", "enrichment:vuln-1:fix"],
        evidence_refs=["evidence:e1", "evidence:e2"],
        object_refs=["object:vuln-1", "object:package-1"],
        relation_refs=["relation:r1", "relation:r2"],
        trajectory_checkpoint_ref="trajectory:t1@5",
        skill_selection_refs=["skill:verify-fix@1", "skill:corroborate@1"],
        experience_pattern_refs=["experience:fix@2"],
        policy_context_ref="policy-context:v1",
        capability_envelope_ref="capability:parent:v1",
        budget_ref="budget:parent",
        cache_hint="cache:parent",
    )


def _provenance(
    base: ContextManifest,
    *,
    dependencies: ContextDependencySet | None = None,
) -> ContextResultProvenance:
    return ContextResultProvenance(
        based_on_context_id=base.context_id,
        based_on_context_revision=base.context_revision,
        dependencies=dependencies or ContextDependencySet(),
    )


def test_child_context_inherits_only_explicit_minimum_scope() -> None:
    parent = _parent()
    child_contract = _contract(task_id="child-enrichment", kind=TaskKind.ENRICHMENT)
    child = derive_child_context(
        parent,
        child_contract=child_contract,
        child_role=canonical_roles()["EnrichmentRole"],
        spec=ChildContextSpec(
            context_id="context-child",
            policy_context_ref="policy-context:child-v1",
            capability_envelope_ref="capability:child-v1",
            budget_ref="budget:child",
            include_case=True,
            evidence_refs=["evidence:e1"],
            object_refs=["object:vuln-1"],
        ),
    )
    assert child.parent_context_id == parent.context_id
    assert child.context_revision == 1
    assert child.task_contract_ref == "child-enrichment@1"
    assert child.role_ref == "EnrichmentRole@1"
    assert child.case_ref == "case-1"
    assert child.knowledge_revision == 42
    assert child.evidence_refs == ["evidence:e1"]
    assert child.object_refs == ["object:vuln-1"]
    assert child.relation_refs == []
    assert child.enrichment_state_refs == []
    assert child.investigation_state_ref is None
    assert child.trajectory_checkpoint_ref is None
    assert child.policy_context_ref == "policy-context:child-v1"
    assert child.capability_envelope_ref == "capability:child-v1"
    assert child.budget_ref == "budget:child"


def test_child_context_cannot_expand_parent_reference_scope() -> None:
    parent = _parent()
    with pytest.raises(ValueError, match="expands parent evidence_refs"):
        derive_child_context(
            parent,
            child_contract=_contract(task_id="child", kind=TaskKind.ENRICHMENT),
            child_role=canonical_roles()["EnrichmentRole"],
            spec=ChildContextSpec(
                context_id="context-child",
                policy_context_ref="policy:child",
                capability_envelope_ref="capability:child",
                budget_ref="budget:child",
                evidence_refs=["evidence:not-in-parent"],
            ),
        )


def test_child_context_requires_role_acceptance() -> None:
    with pytest.raises(ValueError, match="does not accept task kind"):
        derive_child_context(
            _parent(),
            child_contract=_contract(task_id="wrong-role", kind=TaskKind.ENRICHMENT),
            child_role=canonical_roles()["InvestigationRole"],
            spec=ChildContextSpec(
                context_id="context-child",
                policy_context_ref="policy:child",
                capability_envelope_ref="capability:child",
                budget_ref="budget:child",
            ),
        )


def test_filter_and_fork_preserve_references_without_summary_handoff() -> None:
    parent = _parent()
    filtered = filter_context(
        parent,
        new_context_id="context-filtered",
        evidence_refs=["evidence:e2"],
        object_refs=["object:vuln-1"],
        relation_refs=[],
        keep_investigation_state=False,
        keep_trajectory_checkpoint=False,
    )
    assert filtered.parent_context_id == parent.context_id
    assert filtered.evidence_refs == ["evidence:e2"]
    assert filtered.object_refs == ["object:vuln-1"]
    assert filtered.relation_refs == []
    assert filtered.investigation_state_ref is None
    assert filtered.trajectory_checkpoint_ref is None
    assert filtered.cache_hint is None

    forked = fork_context(parent, new_context_id="context-fork")
    assert forked.parent_context_id == parent.context_id
    assert forked.context_revision == 1
    assert forked.evidence_refs == parent.evidence_refs
    assert forked.cache_hint is None


def test_refresh_and_pin_advance_world_coordinates_without_regression() -> None:
    parent = _parent()
    refreshed = refresh_context(
        parent,
        ContextRefresh(
            context_revision=4,
            knowledge_revision=43,
            investigation_state_ref="case:case-1@8",
            add_evidence_refs=["evidence:e3"],
            add_object_refs=["object:release-1"],
        ),
    )
    assert refreshed.context_revision == 4
    assert refreshed.knowledge_revision == 43
    assert refreshed.investigation_state_ref == "case:case-1@8"
    assert refreshed.evidence_refs == ["evidence:e1", "evidence:e2", "evidence:e3"]
    assert refreshed.object_refs == ["object:package-1", "object:release-1", "object:vuln-1"]

    pinned = pin_context(
        refreshed,
        context_revision=5,
        knowledge_revision=44,
        investigation_state_ref="case:case-1@9",
    )
    assert pinned.context_revision == 5
    assert pinned.knowledge_revision == 44
    assert pinned.investigation_state_ref == "case:case-1@9"

    with pytest.raises(ValueError, match="cannot move backwards"):
        refresh_context(
            parent,
            ContextRefresh(context_revision=4, knowledge_revision=41),
        )


def test_diff_and_merge_are_reference_preserving_and_fail_on_world_mismatch() -> None:
    parent = _parent()
    left = refresh_context(
        parent,
        ContextRefresh(context_revision=4, add_evidence_refs=["evidence:left"]),
    )
    right = refresh_context(
        parent,
        ContextRefresh(context_revision=5, add_object_refs=["object:right"]),
    )
    delta = diff_contexts(parent, left)
    assert delta.added_refs == {"evidence_refs": ["evidence:left"]}
    assert delta.removed_refs == {}
    assert delta.scalar_changes == []

    merged = merge_contexts(
        left,
        right,
        context_id="context-merged",
        context_revision=1,
    )
    assert merged.evidence_refs == ["evidence:e1", "evidence:e2", "evidence:left"]
    assert merged.object_refs == ["object:package-1", "object:right", "object:vuln-1"]

    different_world = right.model_copy(update={"knowledge_revision": 99})
    with pytest.raises(ValueError, match="different knowledge_revision"):
        merge_contexts(
            left,
            different_world,
            context_id="invalid-merge",
            context_revision=1,
        )


def test_context_revision_gate_accepts_same_or_cache_only_revision() -> None:
    base = _parent()
    gate = ContextRevisionGate()
    same = gate.evaluate(base=base, current=base, result=_provenance(base))
    assert same.status is ContextCompatibilityStatus.VALID

    cache_only = base.model_copy(update={"context_revision": 4, "cache_hint": "cache:new"})
    result = gate.evaluate(base=base, current=cache_only, result=_provenance(base))
    assert result.status is ContextCompatibilityStatus.VALID
    assert result.reasons == ["revision_changed_without_semantic_delta"]


def test_context_revision_gate_requires_rebase_for_unrelated_new_refs() -> None:
    base = _parent()
    current = refresh_context(
        base,
        ContextRefresh(context_revision=4, add_evidence_refs=["evidence:new"]),
    )
    result = ContextRevisionGate().evaluate(
        base=base,
        current=current,
        result=_provenance(
            base,
            dependencies=ContextDependencySet(
                knowledge_revision=False,
                investigation_state_ref=False,
                evidence_refs=["evidence:e1"],
            ),
        ),
    )
    assert result.status is ContextCompatibilityStatus.REBASE_REQUIRED


def test_context_revision_gate_marks_removed_dependency_or_world_change_stale() -> None:
    base = _parent()
    current = base.model_copy(
        update={
            "context_revision": 4,
            "knowledge_revision": 43,
            "evidence_refs": ["evidence:e2"],
        }
    )
    result = ContextRevisionGate().evaluate(
        base=base,
        current=current,
        result=_provenance(
            base,
            dependencies=ContextDependencySet(evidence_refs=["evidence:e1"]),
        ),
    )
    assert result.status is ContextCompatibilityStatus.STALE
    assert "knowledge_revision_changed" in result.reasons
    assert any(reason.startswith("dependency_removed:evidence_refs") for reason in result.reasons)


def test_context_revision_gate_marks_authority_change_conflict() -> None:
    base = _parent()
    current = base.model_copy(
        update={"context_revision": 4, "policy_context_ref": "policy-context:v2"}
    )
    result = ContextRevisionGate().evaluate(
        base=base,
        current=current,
        result=_provenance(base),
    )
    assert result.status is ContextCompatibilityStatus.CONFLICT
    assert result.reasons == ["authority_context_changed:policy_context_ref"]


def test_same_revision_with_mutated_content_is_conflict() -> None:
    base = _parent()
    mutated = base.model_copy(update={"evidence_refs": ["evidence:e2"]})
    result = ContextRevisionGate().evaluate(
        base=base,
        current=mutated,
        result=_provenance(base),
    )
    assert result.status is ContextCompatibilityStatus.CONFLICT
    assert result.reasons == ["immutable_revision_content_mismatch"]
