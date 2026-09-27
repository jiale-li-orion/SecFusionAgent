from __future__ import annotations

import json
from fnmatch import fnmatchcase
from hashlib import sha256

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from packages.investigation.skills.contracts import (
    SkillDisclosureLevel,
    SkillManifest,
    SkillSelection,
    SkillStatus,
)
from packages.investigation.skills.service import SkillStore
from packages.investigation.state.contracts import EvidenceNeed
from packages.task_runtime.contracts.models import RoleProfile, TaskContract


class SkillResolutionContext(BaseModel):
    task_run_id: str
    object_types: list[str] = Field(default_factory=list)
    visible_capability_classes: list[str] = Field(default_factory=list)
    available_inputs: list[str] = Field(default_factory=list)
    satisfied_conditions: list[str] = Field(default_factory=list)
    state_signature: str
    capability_view_revision: str


class SkillResolver:
    def __init__(self, store: SkillStore | None = None) -> None:
        self._store = store or SkillStore()

    async def resolve(
        self,
        session: AsyncSession,
        *,
        task: TaskContract,
        role: RoleProfile,
        context: SkillResolutionContext,
        evidence_need: EvidenceNeed | None = None,
        statuses: set[SkillStatus] | None = None,
    ) -> SkillSelection:
        manifests = await self._store.search_manifests(
            session,
            namespaces=set(role.skill_scope),
            statuses=statuses,
        )
        ranked: list[tuple[int, str, SkillManifest, list[str]]] = []
        seed_refs = set(role.seed_skill_refs)
        for manifest in manifests:
            matched, score, reasons = _match_manifest(
                manifest,
                task=task,
                evidence_need=evidence_need,
                object_types=set(context.object_types),
                visible_capability_classes=set(context.visible_capability_classes),
                available_inputs=set(context.available_inputs),
                satisfied_conditions=set(context.satisfied_conditions),
            )
            if not matched:
                continue
            if manifest.ref in seed_refs:
                score += 100
                reasons.append("role_seed_skill")
            ranked.append((score, manifest.ref, manifest, reasons))

        ranked.sort(key=lambda item: (-item[0], item[1]))
        candidates = [manifest.ref for _, _, manifest, _ in ranked]
        selected = candidates[0] if candidates else None
        reason = ";".join(ranked[0][3]) if ranked else "no_applicable_validated_skill"
        selection_id = _selection_id(
            task_run_id=context.task_run_id,
            candidate_skill_refs=candidates,
            selected_skill_ref=selected,
            state_signature=context.state_signature,
            capability_view_revision=context.capability_view_revision,
        )
        return SkillSelection(
            selection_id=selection_id,
            task_run_id=context.task_run_id,
            candidate_skill_refs=candidates,
            selected_skill_ref=selected,
            disclosure_level=SkillDisclosureLevel.MANIFEST,
            selection_reason=reason,
            state_signature=context.state_signature,
            capability_view_revision=context.capability_view_revision,
        )


def _match_manifest(
    manifest: SkillManifest,
    *,
    task: TaskContract,
    evidence_need: EvidenceNeed | None,
    object_types: set[str],
    visible_capability_classes: set[str],
    available_inputs: set[str],
    satisfied_conditions: set[str],
) -> tuple[bool, int, list[str]]:
    reasons: list[str] = []
    score = 0

    task_matches = [
        pattern for pattern in manifest.task_patterns if fnmatchcase(task.task_kind.value, pattern)
    ]
    if not task_matches:
        return False, 0, []
    score += 20
    reasons.append("task_pattern_match")
    if task.task_kind.value in task_matches:
        score += 5

    if manifest.evidence_need_patterns:
        if evidence_need is None:
            return False, 0, []
        values = {
            evidence_need.purpose,
            evidence_need.proposition_or_question,
        }
        matched_need = any(
            fnmatchcase(value, pattern)
            for pattern in manifest.evidence_need_patterns
            for value in values
        )
        if not matched_need:
            return False, 0, []
        score += 20
        reasons.append("evidence_need_pattern_match")

    if manifest.applicable_object_types:
        if not object_types.intersection(manifest.applicable_object_types):
            return False, 0, []
        score += 10
        reasons.append("object_type_match")

    if not set(manifest.required_inputs).issubset(available_inputs):
        return False, 0, []
    if manifest.required_inputs:
        score += 5
        reasons.append("required_inputs_available")

    if not set(manifest.required_capability_classes).issubset(visible_capability_classes):
        return False, 0, []
    if manifest.required_capability_classes:
        score += 10
        reasons.append("required_capabilities_visible")

    if not set(manifest.applicability_conditions).issubset(satisfied_conditions):
        return False, 0, []
    if manifest.applicability_conditions:
        score += 5
        reasons.append("applicability_conditions_satisfied")

    return True, score, reasons


def _selection_id(
    *,
    task_run_id: str,
    candidate_skill_refs: list[str],
    selected_skill_ref: str | None,
    state_signature: str,
    capability_view_revision: str,
) -> str:
    digest = sha256(
        json.dumps(
            {
                "task_run_id": task_run_id,
                "candidate_skill_refs": candidate_skill_refs,
                "selected_skill_ref": selected_skill_ref,
                "state_signature": state_signature,
                "capability_view_revision": capability_view_revision,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return f"skill-selection:{digest[:32]}"
