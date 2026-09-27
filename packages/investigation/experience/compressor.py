from __future__ import annotations

import json
from hashlib import sha256

from pydantic import BaseModel, Field, model_validator

from packages.investigation.experience.service import (
    ExperienceSupportRecord,
    ExperienceVersion,
)
from packages.investigation.skills.contracts import (
    SkillManifest,
    SkillProcedure,
    SkillProvenance,
    SkillSourceType,
    SkillStatus,
    SkillVersion,
)


class ExperiencePattern(BaseModel):
    pattern_id: str
    task_signature: str
    condition_signature: str
    reusable_procedure_fragments: list[str] = Field(default_factory=list)
    failure_guard_candidates: list[str] = Field(default_factory=list)
    fallback_candidates: list[str] = Field(default_factory=list)
    stop_condition_candidates: list[str] = Field(default_factory=list)
    capability_preference_candidates: list[str] = Field(default_factory=list)
    support_refs: list[str] = Field(default_factory=list)
    counterexample_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_pattern(self) -> ExperiencePattern:
        if not self.task_signature.strip() or not self.condition_signature.strip():
            raise ValueError("ExperiencePattern task/condition signature cannot be empty")
        if not self.support_refs and not self.counterexample_refs:
            raise ValueError("ExperiencePattern requires support or counterexample provenance")
        return self


class SkillPatchCandidate(BaseModel):
    patch_id: str
    target_skill_ref: str
    source_pattern_refs: list[str] = Field(min_length=1)
    support_refs: list[str] = Field(default_factory=list)
    counterexample_refs: list[str] = Field(default_factory=list)
    proposed_skill: SkillVersion
    rationale: str

    @model_validator(mode="after")
    def validate_patch(self) -> SkillPatchCandidate:
        if self.proposed_skill.manifest.status is not SkillStatus.CANDIDATE:
            raise ValueError("SkillPatchCandidate proposed skill must remain candidate")
        if self.proposed_skill.manifest.supersedes != self.target_skill_ref:
            raise ValueError("SkillPatchCandidate must supersede its target skill")
        return self


class ExperienceCompressor:
    """Deterministic v1 Experience -> Pattern -> SkillPatch transformation.

    This layer never activates a Skill. M7 replay/regression owns promotion.
    """

    def extract(
        self,
        experience: ExperienceVersion,
        *,
        support_records: list[ExperienceSupportRecord],
    ) -> ExperiencePattern:
        support_refs = sorted(
            {
                f"trajectory:{record.trajectory_id}"
                for record in support_records
                if record.outcome in {"success", "partial"}
            }
        )
        counterexample_refs = sorted(
            {
                f"trajectory:{record.trajectory_id}"
                for record in support_records
                if record.outcome == "failure"
            }
        )
        if not support_refs and not counterexample_refs:
            support_refs = [f"experience:{experience.experience_version_id}"]

        capability_preferences = _string_list(experience.scope.get("capability_preferences"))
        condition_payload = {
            "task_signature": experience.task_signature,
            "scope": experience.scope,
            "trigger_signals": experience.trigger_signals,
            "applicable_conditions": experience.applicable_conditions,
        }
        condition_signature = _digest(condition_payload)
        pattern_payload = {
            "experience_version_id": experience.experience_version_id,
            "condition_signature": condition_signature,
            "recommended_actions": experience.recommended_actions,
            "failure_modes": experience.failure_modes,
            "fallback_actions": experience.fallback_actions,
            "stop_conditions": experience.stop_conditions,
            "capability_preferences": capability_preferences,
            "support_refs": support_refs,
            "counterexample_refs": counterexample_refs,
        }
        return ExperiencePattern(
            pattern_id=f"experience-pattern:{_digest(pattern_payload)[:32]}",
            task_signature=experience.task_signature,
            condition_signature=condition_signature,
            reusable_procedure_fragments=_unique(experience.recommended_actions),
            failure_guard_candidates=_unique(experience.failure_modes),
            fallback_candidates=_unique(experience.fallback_actions),
            stop_condition_candidates=_unique(experience.stop_conditions),
            capability_preference_candidates=_unique(capability_preferences),
            support_refs=support_refs,
            counterexample_refs=counterexample_refs,
        )

    def merge(self, patterns: list[ExperiencePattern]) -> ExperiencePattern:
        if not patterns:
            raise ValueError("ExperienceCompressor.merge requires at least one pattern")
        task_signatures = {pattern.task_signature for pattern in patterns}
        if len(task_signatures) != 1:
            raise ValueError("cannot merge ExperiencePatterns with different task signatures")
        merged_conditions = sorted({pattern.condition_signature for pattern in patterns})
        payload = {
            "task_signature": patterns[0].task_signature,
            "conditions": merged_conditions,
            "pattern_ids": sorted(pattern.pattern_id for pattern in patterns),
        }
        return ExperiencePattern(
            pattern_id=f"experience-pattern:{_digest(payload)[:32]}",
            task_signature=patterns[0].task_signature,
            condition_signature=_digest(merged_conditions),
            reusable_procedure_fragments=_merge_lists(
                pattern.reusable_procedure_fragments for pattern in patterns
            ),
            failure_guard_candidates=_merge_lists(
                pattern.failure_guard_candidates for pattern in patterns
            ),
            fallback_candidates=_merge_lists(pattern.fallback_candidates for pattern in patterns),
            stop_condition_candidates=_merge_lists(
                pattern.stop_condition_candidates for pattern in patterns
            ),
            capability_preference_candidates=_merge_lists(
                pattern.capability_preference_candidates for pattern in patterns
            ),
            support_refs=_merge_lists(pattern.support_refs for pattern in patterns),
            counterexample_refs=_merge_lists(pattern.counterexample_refs for pattern in patterns),
        )

    def propose_patch(
        self,
        base_skill: SkillVersion,
        pattern: ExperiencePattern,
        *,
        rationale: str,
    ) -> SkillPatchCandidate:
        if pattern.task_signature not in base_skill.manifest.task_patterns:
            raise ValueError("ExperiencePattern task signature does not match target Skill")
        next_version = base_skill.manifest.version + 1
        steps = [
            step.model_copy(update={"version": next_version}) for step in base_skill.procedure.steps
        ]
        procedure = SkillProcedure(
            skill_id=base_skill.manifest.skill_id,
            version=next_version,
            steps=steps,
            evidence_expectations=list(base_skill.procedure.evidence_expectations),
            failure_guards=_unique(
                [
                    *base_skill.procedure.failure_guards,
                    *pattern.failure_guard_candidates,
                ]
            ),
            fallbacks=_unique([*base_skill.procedure.fallbacks, *pattern.fallback_candidates]),
            stop_conditions=_unique(
                [
                    *base_skill.procedure.stop_conditions,
                    *pattern.stop_condition_candidates,
                ]
            ),
            budget_profile=base_skill.procedure.budget_profile,
        )
        manifest = SkillManifest(
            **{
                **base_skill.manifest.model_dump(mode="python"),
                "version": next_version,
                "status": SkillStatus.CANDIDATE,
                "source_type": SkillSourceType.EXPERIENCE_DERIVED,
                "optional_capability_classes": _unique(
                    [
                        *base_skill.manifest.optional_capability_classes,
                        *pattern.capability_preference_candidates,
                    ]
                ),
                "procedure_ref": (f"skill-procedure:{base_skill.manifest.skill_id}@{next_version}"),
                "provenance_ref": (
                    f"skill-provenance:{base_skill.manifest.skill_id}@{next_version}"
                ),
                "validation_ref": None,
                "supersedes": base_skill.manifest.ref,
            }
        )
        provenance = SkillProvenance(
            skill_id=base_skill.manifest.skill_id,
            version=next_version,
            origin="ExperienceCompressor",
            supporting_trajectory_refs=[
                ref.removeprefix("trajectory:")
                for ref in pattern.support_refs
                if ref.startswith("trajectory:")
            ],
            supporting_experience_pattern_refs=[pattern.pattern_id],
            promotion_history=["proposed_from_experience_pending_m7_replay"],
        )
        proposed = SkillVersion(
            manifest=manifest,
            procedure=procedure,
            provenance=provenance,
        )
        patch_payload = {
            "target_skill_ref": base_skill.manifest.ref,
            "pattern_id": pattern.pattern_id,
            "proposed": proposed.model_dump(mode="json"),
        }
        return SkillPatchCandidate(
            patch_id=f"skill-patch:{_digest(patch_payload)[:32]}",
            target_skill_ref=base_skill.manifest.ref,
            source_pattern_refs=[pattern.pattern_id],
            support_refs=list(pattern.support_refs),
            counterexample_refs=list(pattern.counterexample_refs),
            proposed_skill=proposed,
            rationale=rationale,
        )


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in values if item.strip()))


def _merge_lists(groups) -> list[str]:
    merged: list[str] = []
    for group in groups:
        merged.extend(group)
    return _unique(merged)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _digest(payload: object) -> str:
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
