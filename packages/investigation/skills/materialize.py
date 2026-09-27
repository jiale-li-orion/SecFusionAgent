from __future__ import annotations

from typing import cast

from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession

from packages.investigation.skills.contracts import (
    SkillDisclosureLevel,
    SkillSelection,
    SkillVersion,
)
from packages.investigation.skills.service import SkillStore
from packages.task_runtime.context.materializer import (
    FragmentCacheClass,
    FragmentTrustClass,
    MaterializedFragment,
)


def materialize_skill_manifest(
    skill: SkillVersion,
    *,
    selection_reason: str,
) -> MaterializedFragment:
    manifest = skill.manifest
    return MaterializedFragment.build(
        kind="skill_manifest",
        source_ref=manifest.ref,
        source_revision=str(manifest.version),
        disclosure_level=SkillDisclosureLevel.MANIFEST.value,
        selection_reason=selection_reason,
        trust_class=FragmentTrustClass.PROCEDURAL,
        cache_class=FragmentCacheClass.TASK_STABLE,
        content=cast(JsonValue, manifest.model_dump(mode="json")),
    )


def materialize_skill_procedure(
    skill: SkillVersion,
    *,
    selection_reason: str,
) -> MaterializedFragment:
    return MaterializedFragment.build(
        kind="skill_procedure",
        source_ref=skill.manifest.ref,
        source_revision=str(skill.manifest.version),
        disclosure_level=SkillDisclosureLevel.PROCEDURE.value,
        selection_reason=selection_reason,
        trust_class=FragmentTrustClass.PROCEDURAL,
        cache_class=FragmentCacheClass.TASK_STABLE,
        content=cast(JsonValue, skill.procedure.model_dump(mode="json")),
    )


def materialize_skill_step(
    skill: SkillVersion,
    *,
    step_id: str,
    selection_reason: str,
) -> MaterializedFragment:
    step = next((item for item in skill.procedure.steps if item.step_id == step_id), None)
    if step is None:
        raise LookupError(f"skill step not found: {skill.manifest.ref}#{step_id}")
    content = {
        "step": step.model_dump(mode="json"),
        "evidence_expectations": skill.procedure.evidence_expectations,
        "failure_guards": skill.procedure.failure_guards,
        "fallbacks": skill.procedure.fallbacks,
        "stop_conditions": skill.procedure.stop_conditions,
    }
    return MaterializedFragment.build(
        kind="skill_step",
        source_ref=skill.manifest.ref,
        source_revision=str(skill.manifest.version),
        disclosure_level=SkillDisclosureLevel.STEP.value,
        selection_reason=selection_reason,
        trust_class=FragmentTrustClass.PROCEDURAL,
        cache_class=FragmentCacheClass.STATE_DYNAMIC,
        content=cast(JsonValue, content),
    )


def materialize_skill_provenance(
    skill: SkillVersion,
    *,
    selection_reason: str,
) -> MaterializedFragment:
    return MaterializedFragment.build(
        kind="skill_provenance",
        source_ref=skill.manifest.ref,
        source_revision=str(skill.manifest.version),
        disclosure_level=SkillDisclosureLevel.PROVENANCE.value,
        selection_reason=selection_reason,
        trust_class=FragmentTrustClass.PROCEDURAL_PROVENANCE,
        cache_class=FragmentCacheClass.EPHEMERAL,
        content=cast(JsonValue, skill.provenance.model_dump(mode="json")),
    )


async def materialize_skill_selection(
    session: AsyncSession,
    *,
    selection: SkillSelection,
    disclosure_level: SkillDisclosureLevel,
    step_id: str | None = None,
    store: SkillStore | None = None,
) -> list[MaterializedFragment]:
    if selection.selected_skill_ref is None:
        return []
    resolved_store = store or SkillStore()
    skill = await resolved_store.get(session, selection.selected_skill_ref)
    fragments = [
        materialize_skill_manifest(
            skill,
            selection_reason=selection.selection_reason,
        )
    ]
    if disclosure_level in {
        SkillDisclosureLevel.PROCEDURE,
        SkillDisclosureLevel.STEP,
        SkillDisclosureLevel.PROVENANCE,
    }:
        fragments.append(
            materialize_skill_procedure(
                skill,
                selection_reason=selection.selection_reason,
            )
        )
    if disclosure_level in {SkillDisclosureLevel.STEP, SkillDisclosureLevel.PROVENANCE}:
        if step_id is None:
            raise ValueError("step disclosure requires step_id")
        fragments.append(
            materialize_skill_step(
                skill,
                step_id=step_id,
                selection_reason=selection.selection_reason,
            )
        )
    if disclosure_level is SkillDisclosureLevel.PROVENANCE:
        fragments.append(
            materialize_skill_provenance(
                skill,
                selection_reason=selection.selection_reason,
            )
        )
    return fragments
