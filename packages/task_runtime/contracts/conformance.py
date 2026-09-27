from __future__ import annotations

from dataclasses import dataclass

from packages.task_runtime.contracts.models import (
    TaskContract,
    TaskKind,
    effect_within_ceiling,
)


@dataclass(frozen=True)
class DelegationCheck:
    allowed: bool
    reason: str | None = None


def validate_child_contract(parent: TaskContract, child: TaskContract) -> DelegationCheck:
    ceiling = parent.delegation_ceiling
    if not ceiling.allowed:
        return DelegationCheck(False, "delegation_not_allowed")
    if child.task_kind not in ceiling.allowed_task_kinds:
        return DelegationCheck(False, "child_task_kind_not_allowed")
    if not effect_within_ceiling(child.effect_ceiling, ceiling.child_effect_ceiling):
        return DelegationCheck(False, "exceeds_parent_effect_ceiling")
    if child.delegation_ceiling.allowed and ceiling.max_depth <= 1:
        return DelegationCheck(False, "exceeds_parent_delegation_ceiling")
    if child.delegation_ceiling.allowed:
        if child.delegation_ceiling.max_depth >= ceiling.max_depth:
            return DelegationCheck(False, "exceeds_parent_delegation_ceiling")
        if not effect_within_ceiling(
            child.delegation_ceiling.child_effect_ceiling,
            ceiling.child_effect_ceiling,
        ):
            return DelegationCheck(False, "exceeds_parent_effect_ceiling")
    return DelegationCheck(True)


def canonical_role_profiles() -> dict[str, tuple[TaskKind, ...]]:
    return {
        "EnrichmentRole": (TaskKind.ENRICHMENT,),
        "InvestigationRole": (
            TaskKind.VERIFY_VERSION_FIX,
            TaskKind.RESOLVE_CONFLICT,
            TaskKind.INVESTIGATE_RELATION,
            TaskKind.INVESTIGATE_INCIDENT,
            TaskKind.WATCH_INCIDENT,
            TaskKind.ASSESS_NORMATIVE_APPLICABILITY,
            TaskKind.OBSERVE_LIVE_ASSET,
        ),
    }
