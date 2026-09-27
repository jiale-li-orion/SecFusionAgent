from __future__ import annotations

from packages.task_runtime.context.contracts import (
    ChildContextSpec,
    ContextCompatibility,
    ContextCompatibilityStatus,
    ContextDelta,
    ContextRefresh,
    ContextResultProvenance,
    ContextScalarChange,
)
from packages.task_runtime.contracts.models import ContextManifest, RoleProfile, TaskContract

_REFERENCE_FIELDS = (
    "enrichment_state_refs",
    "evidence_refs",
    "object_refs",
    "relation_refs",
    "skill_selection_refs",
    "experience_pattern_refs",
)
_AUTHORITY_FIELDS = (
    "task_contract_ref",
    "role_ref",
    "case_ref",
    "policy_context_ref",
    "capability_envelope_ref",
    "budget_ref",
)
_STATE_SCALAR_FIELDS = (
    "knowledge_revision",
    "investigation_state_ref",
    "trajectory_checkpoint_ref",
)


def derive_child_context(
    parent: ContextManifest,
    *,
    child_contract: TaskContract,
    child_role: RoleProfile,
    spec: ChildContextSpec,
) -> ContextManifest:
    if not child_role.accepts(child_contract.task_kind):
        raise ValueError(
            f"role {child_role.role_id} does not accept task kind {child_contract.task_kind.value}"
        )
    _require_subsets(parent, spec)
    return ContextManifest(
        context_id=spec.context_id,
        context_revision=1,
        parent_context_id=parent.context_id,
        task_contract_ref=f"{child_contract.task_contract_id}@{child_contract.contract_revision}",
        role_ref=f"{child_role.role_id}@{child_role.version}",
        case_ref=parent.case_ref if spec.include_case else None,
        knowledge_revision=parent.knowledge_revision,
        investigation_state_ref=(
            parent.investigation_state_ref if spec.include_investigation_state else None
        ),
        enrichment_state_refs=_stable_refs(spec.enrichment_state_refs),
        evidence_refs=_stable_refs(spec.evidence_refs),
        object_refs=_stable_refs(spec.object_refs),
        relation_refs=_stable_refs(spec.relation_refs),
        trajectory_checkpoint_ref=(
            parent.trajectory_checkpoint_ref if spec.include_trajectory_checkpoint else None
        ),
        skill_selection_refs=_stable_refs(spec.skill_selection_refs),
        experience_pattern_refs=_stable_refs(spec.experience_pattern_refs),
        policy_context_ref=spec.policy_context_ref,
        capability_envelope_ref=spec.capability_envelope_ref,
        budget_ref=spec.budget_ref,
        cache_hint=spec.cache_hint,
    )


def pin_context(
    manifest: ContextManifest,
    *,
    context_revision: int,
    knowledge_revision: int,
    investigation_state_ref: str | None = None,
) -> ContextManifest:
    """Pin mutable world/state coordinates into a new immutable manifest revision."""
    return refresh_context(
        manifest,
        ContextRefresh(
            context_revision=context_revision,
            knowledge_revision=knowledge_revision,
            investigation_state_ref=investigation_state_ref,
            cache_hint=manifest.cache_hint,
        ),
    )


def fork_context(
    manifest: ContextManifest,
    *,
    new_context_id: str,
) -> ContextManifest:
    return manifest.model_copy(
        update={
            "context_id": new_context_id,
            "context_revision": 1,
            "parent_context_id": manifest.context_id,
            "cache_hint": None,
        }
    )


def filter_context(
    manifest: ContextManifest,
    *,
    new_context_id: str,
    evidence_refs: list[str] | None = None,
    object_refs: list[str] | None = None,
    relation_refs: list[str] | None = None,
    enrichment_state_refs: list[str] | None = None,
    skill_selection_refs: list[str] | None = None,
    experience_pattern_refs: list[str] | None = None,
    keep_investigation_state: bool = True,
    keep_trajectory_checkpoint: bool = True,
) -> ContextManifest:
    selections = {
        "evidence_refs": manifest.evidence_refs if evidence_refs is None else evidence_refs,
        "object_refs": manifest.object_refs if object_refs is None else object_refs,
        "relation_refs": manifest.relation_refs if relation_refs is None else relation_refs,
        "enrichment_state_refs": (
            manifest.enrichment_state_refs
            if enrichment_state_refs is None
            else enrichment_state_refs
        ),
        "skill_selection_refs": (
            manifest.skill_selection_refs if skill_selection_refs is None else skill_selection_refs
        ),
        "experience_pattern_refs": (
            manifest.experience_pattern_refs
            if experience_pattern_refs is None
            else experience_pattern_refs
        ),
    }
    for field, selected in selections.items():
        _require_subset(field, selected, getattr(manifest, field))
    return manifest.model_copy(
        update={
            "context_id": new_context_id,
            "context_revision": 1,
            "parent_context_id": manifest.context_id,
            **{field: _stable_refs(values) for field, values in selections.items()},
            "investigation_state_ref": (
                manifest.investigation_state_ref if keep_investigation_state else None
            ),
            "trajectory_checkpoint_ref": (
                manifest.trajectory_checkpoint_ref if keep_trajectory_checkpoint else None
            ),
            "cache_hint": None,
        }
    )


def refresh_context(manifest: ContextManifest, refresh: ContextRefresh) -> ContextManifest:
    if refresh.context_revision <= manifest.context_revision:
        raise ValueError("refreshed context revision must advance")
    knowledge_revision = (
        manifest.knowledge_revision
        if refresh.knowledge_revision is None
        else refresh.knowledge_revision
    )
    if (
        manifest.knowledge_revision is not None
        and knowledge_revision is not None
        and knowledge_revision < manifest.knowledge_revision
    ):
        raise ValueError("knowledge_revision cannot move backwards during refresh")
    return manifest.model_copy(
        update={
            "context_revision": refresh.context_revision,
            "knowledge_revision": knowledge_revision,
            "investigation_state_ref": (
                refresh.investigation_state_ref
                if refresh.investigation_state_ref is not None
                else manifest.investigation_state_ref
            ),
            "evidence_refs": _union_refs(manifest.evidence_refs, refresh.add_evidence_refs),
            "object_refs": _union_refs(manifest.object_refs, refresh.add_object_refs),
            "relation_refs": _union_refs(manifest.relation_refs, refresh.add_relation_refs),
            "enrichment_state_refs": _union_refs(
                manifest.enrichment_state_refs,
                refresh.add_enrichment_state_refs,
            ),
            "skill_selection_refs": _union_refs(
                manifest.skill_selection_refs,
                refresh.add_skill_selection_refs,
            ),
            "experience_pattern_refs": _union_refs(
                manifest.experience_pattern_refs,
                refresh.add_experience_pattern_refs,
            ),
            "cache_hint": refresh.cache_hint,
        }
    )


def diff_contexts(base: ContextManifest, current: ContextManifest) -> ContextDelta:
    scalar_changes: list[ContextScalarChange] = []
    for field in (*_AUTHORITY_FIELDS, *_STATE_SCALAR_FIELDS):
        before = getattr(base, field)
        after = getattr(current, field)
        if before != after:
            scalar_changes.append(ContextScalarChange(field=field, before=before, after=after))
    added: dict[str, list[str]] = {}
    removed: dict[str, list[str]] = {}
    for field in _REFERENCE_FIELDS:
        before = set(getattr(base, field))
        after = set(getattr(current, field))
        field_added = sorted(after - before)
        field_removed = sorted(before - after)
        if field_added:
            added[field] = field_added
        if field_removed:
            removed[field] = field_removed
    return ContextDelta(
        base_ref=_context_ref(base),
        current_ref=_context_ref(current),
        scalar_changes=scalar_changes,
        added_refs=added,
        removed_refs=removed,
    )


def merge_contexts(
    left: ContextManifest,
    right: ContextManifest,
    *,
    context_id: str,
    context_revision: int,
) -> ContextManifest:
    for field in (*_AUTHORITY_FIELDS, *_STATE_SCALAR_FIELDS):
        if getattr(left, field) != getattr(right, field):
            raise ValueError(f"cannot merge contexts with different {field}")
    if context_revision < 1:
        raise ValueError("context_revision must be positive")
    return left.model_copy(
        update={
            "context_id": context_id,
            "context_revision": context_revision,
            "parent_context_id": left.context_id,
            **{
                field: _union_refs(getattr(left, field), getattr(right, field))
                for field in _REFERENCE_FIELDS
            },
            "cache_hint": None,
        }
    )


class ContextRevisionGate:
    def evaluate(
        self,
        *,
        base: ContextManifest,
        current: ContextManifest,
        result: ContextResultProvenance,
    ) -> ContextCompatibility:
        delta = diff_contexts(base, current)
        reasons: list[str] = []
        if result.based_on_context_id != base.context_id:
            return ContextCompatibility(
                status=ContextCompatibilityStatus.CONFLICT,
                reasons=["result_context_id_mismatch"],
                delta=delta,
            )
        if result.based_on_context_revision != base.context_revision:
            return ContextCompatibility(
                status=ContextCompatibilityStatus.CONFLICT,
                reasons=["result_context_revision_mismatch"],
                delta=delta,
            )
        if current.context_id != base.context_id:
            return ContextCompatibility(
                status=ContextCompatibilityStatus.CONFLICT,
                reasons=["current_context_lineage_changed"],
                delta=delta,
            )
        if current.context_revision < base.context_revision:
            return ContextCompatibility(
                status=ContextCompatibilityStatus.CONFLICT,
                reasons=["current_context_revision_regressed"],
                delta=delta,
            )
        if current.context_revision == base.context_revision and not delta.is_empty:
            return ContextCompatibility(
                status=ContextCompatibilityStatus.CONFLICT,
                reasons=["immutable_revision_content_mismatch"],
                delta=delta,
            )
        if current.context_revision == base.context_revision:
            return ContextCompatibility(
                status=ContextCompatibilityStatus.VALID,
                reasons=[],
                delta=delta,
            )

        scalar_map = {change.field: change for change in delta.scalar_changes}
        authority_changed = sorted(set(scalar_map) & set(_AUTHORITY_FIELDS))
        if authority_changed:
            return ContextCompatibility(
                status=ContextCompatibilityStatus.CONFLICT,
                reasons=[f"authority_context_changed:{field}" for field in authority_changed],
                delta=delta,
            )

        dependencies = result.dependencies
        if dependencies.knowledge_revision and "knowledge_revision" in scalar_map:
            reasons.append("knowledge_revision_changed")
        if dependencies.investigation_state_ref and "investigation_state_ref" in scalar_map:
            reasons.append("investigation_state_changed")
        if dependencies.trajectory_checkpoint_ref and "trajectory_checkpoint_ref" in scalar_map:
            reasons.append("trajectory_checkpoint_changed")
        for field in _REFERENCE_FIELDS:
            depended = set(getattr(dependencies, field))
            removed = set(delta.removed_refs.get(field, []))
            changed = sorted(depended & removed)
            if changed:
                reasons.append(f"dependency_removed:{field}:{changed[0]}")
        if reasons:
            return ContextCompatibility(
                status=ContextCompatibilityStatus.STALE,
                reasons=reasons,
                delta=delta,
            )
        if delta.is_empty:
            return ContextCompatibility(
                status=ContextCompatibilityStatus.VALID,
                reasons=["revision_changed_without_semantic_delta"],
                delta=delta,
            )
        return ContextCompatibility(
            status=ContextCompatibilityStatus.REBASE_REQUIRED,
            reasons=["context_advanced_without_invalidating_dependencies"],
            delta=delta,
        )


def _require_subsets(parent: ContextManifest, spec: ChildContextSpec) -> None:
    for field in _REFERENCE_FIELDS:
        _require_subset(field, getattr(spec, field), getattr(parent, field))


def _require_subset(field: str, selected: list[str], available: list[str]) -> None:
    extras = sorted(set(selected) - set(available))
    if extras:
        raise ValueError(f"context selection expands parent {field}: {extras[0]}")


def _stable_refs(values: list[str]) -> list[str]:
    return sorted(set(values))


def _union_refs(left: list[str], right: list[str]) -> list[str]:
    return sorted(set(left) | set(right))


def _context_ref(manifest: ContextManifest) -> str:
    return f"{manifest.context_id}@{manifest.context_revision}"
