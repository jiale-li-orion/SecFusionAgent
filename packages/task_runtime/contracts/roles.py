from __future__ import annotations

from packages.task_runtime.contracts.models import ExecutionProfile, RoleProfile, TaskKind


def canonical_roles() -> dict[str, RoleProfile]:
    enrichment = RoleProfile(
        role_id="EnrichmentRole",
        version="1",
        accepts_task_kinds=[TaskKind.ENRICHMENT],
        state_model="M3.EnrichmentState",
        planner_profile="enrichment-v1",
        skill_scope=["enrichment"],
        default_execution_profile=ExecutionProfile.INVESTIGATE,
        delegation_rules=[{"allow_investigation": False, "allow_operator_children": True}],
    )
    investigation = RoleProfile(
        role_id="InvestigationRole",
        version="1",
        accepts_task_kinds=[
            TaskKind.VERIFY_VERSION_FIX,
            TaskKind.RESOLVE_CONFLICT,
            TaskKind.INVESTIGATE_RELATION,
            TaskKind.INVESTIGATE_INCIDENT,
            TaskKind.WATCH_INCIDENT,
            TaskKind.ASSESS_NORMATIVE_APPLICABILITY,
            TaskKind.OBSERVE_LIVE_ASSET,
        ],
        state_model="M4.InvestigationState",
        planner_profile="investigation-v1",
        skill_scope=["investigation"],
        seed_skill_refs=[],
        default_execution_profile=ExecutionProfile.INVESTIGATE,
        delegation_rules=[{"allow_enrichment": True, "allow_child_execution": True}],
    )
    return {role.role_id: role for role in (enrichment, investigation)}
