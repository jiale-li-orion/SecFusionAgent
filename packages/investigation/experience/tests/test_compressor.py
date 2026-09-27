from __future__ import annotations

from datetime import UTC, datetime

from packages.investigation.experience.compressor import ExperienceCompressor
from packages.investigation.experience.service import ExperienceSupportRecord, ExperienceVersion
from packages.investigation.skills.contracts import SkillSourceType, SkillStatus
from packages.investigation.skills.seeds import seeded_skills

NOW = datetime(2026, 9, 27, 20, 0, tzinfo=UTC)


def _experience() -> ExperienceVersion:
    return ExperienceVersion(
        experience_id="experience-1",
        experience_version_id="experience-version-1",
        version=1,
        name="Fix-boundary replay lesson",
        task_signature="verify_version_fix",
        status="active",
        scope={
            "repository": "public",
            "capability_preferences": ["repository.compare"],
        },
        trigger_signals=["release_metadata_missing"],
        applicable_conditions=["fix commit is known"],
        recommended_actions=["compare release ancestry before using timestamps"],
        evidence_expectation=["release containment evidence"],
        failure_modes=["PR merge time is not release containment"],
        stop_conditions=["record unknown when all primary release paths are exhausted"],
        fallback_actions=["check package registry publication metadata"],
        validation_summary={},
        success_count=1,
        failure_count=1,
        partial_count=0,
        last_validated_at=NOW,
    )


def _support(outcome: str, trajectory_id: str) -> ExperienceSupportRecord:
    return ExperienceSupportRecord(
        trajectory_id=trajectory_id,
        outcome=outcome,
        evaluation={"fixture": True},
        evaluator="m7-test",
        created_at=NOW,
    )


def test_compressor_preserves_support_counterexample_and_builds_patch() -> None:
    compressor = ExperienceCompressor()
    pattern = compressor.extract(
        _experience(),
        support_records=[
            _support("success", "trajectory-support"),
            _support("failure", "trajectory-counterexample"),
        ],
    )
    base = seeded_skills()[0]
    patch = compressor.propose_patch(
        base,
        pattern,
        rationale="Replay exposed a timestamp-based false positive.",
    )

    assert pattern.support_refs == ["trajectory:trajectory-support"]
    assert pattern.counterexample_refs == ["trajectory:trajectory-counterexample"]
    assert patch.support_refs == pattern.support_refs
    assert patch.counterexample_refs == pattern.counterexample_refs
    assert patch.target_skill_ref == base.manifest.ref
    assert patch.proposed_skill.manifest.version == base.manifest.version + 1
    assert patch.proposed_skill.manifest.status is SkillStatus.CANDIDATE
    assert patch.proposed_skill.manifest.source_type is SkillSourceType.EXPERIENCE_DERIVED
    assert patch.proposed_skill.manifest.validation_ref is None
    assert patch.proposed_skill.manifest.supersedes == base.manifest.ref
    assert "repository.compare" in patch.proposed_skill.manifest.optional_capability_classes
    assert (
        "PR merge time is not release containment" in patch.proposed_skill.procedure.failure_guards
    )
    assert all(
        step.version == patch.proposed_skill.manifest.version
        for step in patch.proposed_skill.procedure.steps
    )


def test_experience_compressor_merge_rejects_cross_task_patterns() -> None:
    compressor = ExperienceCompressor()
    first = compressor.extract(_experience(), support_records=[])
    second_experience = _experience().model_copy(update={"task_signature": "resolve_conflict"})
    second = compressor.extract(second_experience, support_records=[])
    try:
        compressor.merge([first, second])
    except ValueError as exc:
        assert "different task signatures" in str(exc)
    else:
        raise AssertionError("cross-task ExperiencePattern merge should fail closed")
