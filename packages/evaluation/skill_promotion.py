from __future__ import annotations

import json
from enum import StrEnum
from hashlib import sha256

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.investigation.experience.compressor import SkillPatchCandidate
from packages.investigation.replay import ReplayCheckpointService
from packages.investigation.skills.contracts import SkillStatus, SkillVersion
from packages.investigation.skills.service import SkillStore
from packages.investigation.storage.models import InvestigationTrajectoryModel
from packages.investigation.trajectory.service import TrajectoryService


class ReplayValidationKind(StrEnum):
    SUPPORT = "support"
    COUNTEREXAMPLE = "counterexample"
    REGRESSION = "regression"


class SkillReplayCaseSpec(BaseModel):
    case_id: str
    checkpoint_id: str
    checkpoint_trajectory_id: str
    source_ref: str
    kind: ReplayValidationKind

    @model_validator(mode="after")
    def validate_case_spec(self) -> SkillReplayCaseSpec:
        if not self.source_ref.strip():
            raise ValueError("SkillReplayCaseSpec source_ref cannot be empty")
        return self


class SkillPromotionSuite(BaseModel):
    suite_id: str
    patch_id: str
    cases: list[SkillReplayCaseSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_suite(self) -> SkillPromotionSuite:
        identities = [
            (
                item.case_id,
                item.checkpoint_id,
                item.checkpoint_trajectory_id,
                item.source_ref,
                item.kind.value,
            )
            for item in self.cases
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("SkillPromotionSuite replay cases must be unique")
        return self


class SkillReplayResult(BaseModel):
    result_ref: str
    patch_id: str
    suite_id: str
    case_id: str
    trajectory_id: str
    checkpoint_id: str
    checkpoint_trajectory_id: str
    source_ref: str
    kind: ReplayValidationKind
    passed: bool
    failure_reasons: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    replay: bool = False

    @model_validator(mode="after")
    def validate_result(self) -> SkillReplayResult:
        for value, label in (
            (self.result_ref, "result_ref"),
            (self.patch_id, "patch_id"),
            (self.suite_id, "suite_id"),
            (self.case_id, "case_id"),
            (self.trajectory_id, "trajectory_id"),
            (self.checkpoint_id, "checkpoint_id"),
            (self.checkpoint_trajectory_id, "checkpoint_trajectory_id"),
            (self.source_ref, "source_ref"),
        ):
            if not value.strip():
                raise ValueError(f"SkillReplayResult {label} cannot be empty")
        if self.passed and self.failure_reasons:
            raise ValueError("passed replay result cannot carry failure_reasons")
        return self


class SkillPromotionPolicy(BaseModel):
    min_support_cases: int = Field(default=1, ge=1)
    require_counterexample: bool = True
    require_regression: bool = True
    require_all_pass: bool = True


class SkillPromotionDecision(BaseModel):
    patch_id: str
    approved: bool
    validation_ref: str | None = None
    failures: list[str] = Field(default_factory=list)
    replay_result_refs: list[str] = Field(default_factory=list)


class SkillPromotionOutcome(BaseModel):
    decision: SkillPromotionDecision
    promoted_skill: SkillVersion | None = None


class _SkillReplaySummary(BaseModel):
    result_ref: str
    patch_id: str
    suite_id: str
    checkpoint_id: str
    checkpoint_trajectory_id: str
    source_ref: str
    kind: ReplayValidationKind
    passed: bool
    failure_reasons: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)


class SkillPromotionGate:
    """M7 replay/regression authority for publishing an active SkillVersion."""

    def __init__(
        self,
        *,
        policy: SkillPromotionPolicy | None = None,
        skill_store: SkillStore | None = None,
        trajectory_service: TrajectoryService | None = None,
        checkpoint_service: ReplayCheckpointService | None = None,
    ) -> None:
        self._policy = policy or SkillPromotionPolicy()
        self._skills = skill_store or SkillStore()
        self._trajectories = trajectory_service or TrajectoryService()
        self._checkpoints = checkpoint_service or ReplayCheckpointService()

    def build_suite(
        self,
        patch: SkillPatchCandidate,
        cases: list[SkillReplayCaseSpec],
    ) -> SkillPromotionSuite:
        payload = {
            "patch_id": patch.patch_id,
            "cases": sorted(
                (item.model_dump(mode="json") for item in cases),
                key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
            ),
        }
        digest = sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return SkillPromotionSuite(
            suite_id=f"m7-suite:{digest[:32]}",
            patch_id=patch.patch_id,
            cases=cases,
        )

    async def record_replay_result(
        self,
        session: AsyncSession,
        *,
        patch_id: str,
        suite_id: str,
        trajectory_id: str,
        checkpoint_id: str,
        checkpoint_trajectory_id: str,
        source_ref: str,
        kind: ReplayValidationKind,
        passed: bool,
        failure_reasons: list[str] | None = None,
        metrics: dict[str, float] | None = None,
    ) -> SkillReplayResult:
        trajectory = await session.scalar(
            select(InvestigationTrajectoryModel)
            .where(InvestigationTrajectoryModel.trajectory_id == trajectory_id)
            .with_for_update()
        )
        if trajectory is None:
            raise LookupError(f"trajectory not found: {trajectory_id}")
        reasons = list(failure_reasons or [])
        if passed and reasons:
            raise ValueError("passed replay result cannot carry failure reasons")
        result_ref = _result_ref(
            patch_id=patch_id,
            suite_id=suite_id,
            trajectory_id=trajectory_id,
            checkpoint_id=checkpoint_id,
            source_ref=source_ref,
            kind=kind,
        )
        summary_model = _SkillReplaySummary(
            result_ref=result_ref,
            patch_id=patch_id,
            suite_id=suite_id,
            checkpoint_id=checkpoint_id,
            checkpoint_trajectory_id=checkpoint_trajectory_id,
            source_ref=source_ref,
            kind=kind,
            passed=passed,
            failure_reasons=reasons,
            metrics=dict(metrics or {}),
        )
        summary = summary_model.model_dump(mode="json")
        expected_outcome = "success" if passed else "failure"
        if trajectory.status == "completed":
            if trajectory.outcome != expected_outcome:
                raise ValueError("completed replay trajectory outcome conflicts with result")
            if trajectory.outcome_summary.get("m7_replay_result") != summary:
                raise ValueError("completed replay trajectory summary conflicts with result")
            return _result_from_summary(
                trajectory,
                summary_model,
                replay=True,
            )
        if trajectory.status != "running":
            raise ValueError("replay result can only finish a running trajectory")
        await self._trajectories.finish(
            session,
            trajectory_id=trajectory_id,
            outcome=expected_outcome,
            outcome_summary={"m7_replay_result": summary},
        )
        return _result_from_summary(trajectory, summary_model, replay=False)

    def evaluate(
        self,
        patch: SkillPatchCandidate,
        suite: SkillPromotionSuite,
        results: list[SkillReplayResult],
    ) -> SkillPromotionDecision:
        failures: list[str] = []
        if suite.patch_id != patch.patch_id:
            failures.append("suite_patch_identity_mismatch")
        if not results:
            failures.append("replay_evidence_missing")
        if len({item.result_ref for item in results}) != len(results):
            failures.append("duplicate_replay_result")
        if len({item.trajectory_id for item in results}) != len(results):
            failures.append("duplicate_replay_trajectory")
        if any(item.patch_id != patch.patch_id for item in results):
            failures.append("replay_patch_identity_mismatch")
        if any(item.suite_id != suite.suite_id for item in results):
            failures.append("replay_suite_identity_mismatch")

        expected_cases = {
            (
                item.case_id,
                item.checkpoint_id,
                item.checkpoint_trajectory_id,
                item.source_ref,
                item.kind.value,
            )
            for item in suite.cases
        }
        actual_cases = {
            (
                item.case_id,
                item.checkpoint_id,
                item.checkpoint_trajectory_id,
                item.source_ref,
                item.kind.value,
            )
            for item in results
        }
        missing_cases = sorted(expected_cases - actual_cases)
        extra_cases = sorted(actual_cases - expected_cases)
        failures.extend("suite_case_missing:" + "|".join(item) for item in missing_cases)
        failures.extend("suite_case_unexpected:" + "|".join(item) for item in extra_cases)

        support_specs = [item for item in suite.cases if item.kind is ReplayValidationKind.SUPPORT]
        counterexample_specs = [
            item for item in suite.cases if item.kind is ReplayValidationKind.COUNTEREXAMPLE
        ]
        regression_specs = [
            item for item in suite.cases if item.kind is ReplayValidationKind.REGRESSION
        ]
        support_sources = {item.source_ref for item in support_specs}
        counterexample_sources = {item.source_ref for item in counterexample_specs}
        failures.extend(
            f"patch_support_source_missing:{item}"
            for item in sorted(set(patch.support_refs) - support_sources)
        )
        failures.extend(
            f"patch_counterexample_source_missing:{item}"
            for item in sorted(set(patch.counterexample_refs) - counterexample_sources)
        )
        support = [item for item in results if item.kind is ReplayValidationKind.SUPPORT]
        passed_support = sum(item.passed for item in support)
        if passed_support < self._policy.min_support_cases:
            failures.append(
                f"support_cases_insufficient:{passed_support}/{self._policy.min_support_cases}"
            )
        if self._policy.require_counterexample and not counterexample_specs:
            failures.append("counterexample_case_missing")
        if self._policy.require_regression and not regression_specs:
            failures.append("regression_case_missing")
        if len(support_specs) < self._policy.min_support_cases:
            failures.append(
                "suite_support_cases_insufficient:"
                f"{len(support_specs)}/{self._policy.min_support_cases}"
            )
        if self._policy.require_all_pass:
            failures.extend(
                f"replay_failed:{item.result_ref}" for item in results if not item.passed
            )
        validation_ref = None if failures else _validation_ref(patch, suite, results)
        return SkillPromotionDecision(
            patch_id=patch.patch_id,
            approved=not failures,
            validation_ref=validation_ref,
            failures=failures,
            replay_result_refs=sorted(item.result_ref for item in results),
        )

    async def promote(
        self,
        session: AsyncSession,
        *,
        patch: SkillPatchCandidate,
        base_skill: SkillVersion,
        suite: SkillPromotionSuite,
        results: list[SkillReplayResult],
    ) -> SkillPromotionOutcome:
        if base_skill.manifest.ref != patch.target_skill_ref:
            raise ValueError("Skill promotion base skill does not match patch target")
        if patch.proposed_skill.manifest.version != base_skill.manifest.version + 1:
            raise ValueError("Skill patch must advance exactly one Skill version")

        durable_failures: list[str] = []
        case_refs: list[str] = []
        for result in results:
            failure = await self._verify_durable_result(session, result)
            if failure is not None:
                durable_failures.append(failure)
            case_refs.append(f"case:{result.case_id}")
        decision = self.evaluate(patch, suite, results)
        if durable_failures:
            decision = decision.model_copy(
                update={
                    "approved": False,
                    "validation_ref": None,
                    "failures": [*decision.failures, *durable_failures],
                }
            )
        if not decision.approved or decision.validation_ref is None:
            return SkillPromotionOutcome(decision=decision)

        candidate = patch.proposed_skill
        manifest = candidate.manifest.model_copy(
            update={
                "status": SkillStatus.ACTIVE,
                "validation_ref": decision.validation_ref,
            }
        )
        provenance = candidate.provenance.model_copy(
            update={
                "supporting_trajectory_refs": sorted(
                    {
                        *candidate.provenance.supporting_trajectory_refs,
                        *(item.trajectory_id for item in results),
                    }
                ),
                "validation_case_refs": sorted(set(case_refs)),
                "promotion_history": [
                    *candidate.provenance.promotion_history,
                    f"m7_validated:{decision.validation_ref}",
                    f"activated_from_patch:{patch.patch_id}",
                ],
            }
        )
        promoted = SkillVersion(
            manifest=manifest,
            procedure=candidate.procedure,
            provenance=provenance,
        )
        stored = await self._skills.publish(session, promoted)
        return SkillPromotionOutcome(decision=decision, promoted_skill=stored)

    async def _verify_durable_result(
        self,
        session: AsyncSession,
        result: SkillReplayResult,
    ) -> str | None:
        try:
            await self._checkpoints.get(
                session,
                trajectory_id=result.checkpoint_trajectory_id,
                checkpoint_id=result.checkpoint_id,
            )
        except LookupError:
            return f"replay_checkpoint_missing:{result.checkpoint_id}"
        trajectory = await session.get(InvestigationTrajectoryModel, result.trajectory_id)
        if trajectory is None or trajectory.status != "completed":
            return f"replay_trajectory_not_completed:{result.trajectory_id}"
        summary = trajectory.outcome_summary.get("m7_replay_result")
        if not isinstance(summary, dict):
            return f"replay_summary_missing:{result.trajectory_id}"
        stored = _SkillReplaySummary.model_validate(summary)
        expected = _summary_from_result(result)
        if stored != expected:
            return f"replay_summary_mismatch:{result.trajectory_id}"
        return None


def _result_ref(
    *,
    patch_id: str,
    suite_id: str,
    trajectory_id: str,
    checkpoint_id: str,
    source_ref: str,
    kind: ReplayValidationKind,
) -> str:
    payload = f"{patch_id}|{suite_id}|{trajectory_id}|{checkpoint_id}|{source_ref}|{kind.value}"
    return f"m7-replay:{sha256(payload.encode()).hexdigest()[:32]}"


def _validation_ref(
    patch: SkillPatchCandidate,
    suite: SkillPromotionSuite,
    results: list[SkillReplayResult],
) -> str:
    payload = {
        "patch_id": patch.patch_id,
        "suite_id": suite.suite_id,
        "results": sorted(
            (
                {
                    "result_ref": item.result_ref,
                    "kind": item.kind.value,
                    "passed": item.passed,
                    "checkpoint_id": item.checkpoint_id,
                    "trajectory_id": item.trajectory_id,
                    "source_ref": item.source_ref,
                }
                for item in results
            ),
            key=lambda item: str(item["result_ref"]),
        ),
    }
    digest = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    return f"m7-validation:{digest[:32]}"


def _summary_from_result(result: SkillReplayResult) -> _SkillReplaySummary:
    return _SkillReplaySummary(
        result_ref=result.result_ref,
        patch_id=result.patch_id,
        suite_id=result.suite_id,
        checkpoint_id=result.checkpoint_id,
        checkpoint_trajectory_id=result.checkpoint_trajectory_id,
        source_ref=result.source_ref,
        kind=result.kind,
        passed=result.passed,
        failure_reasons=list(result.failure_reasons),
        metrics=dict(result.metrics),
    )


def _result_from_summary(
    trajectory: InvestigationTrajectoryModel,
    summary: _SkillReplaySummary,
    *,
    replay: bool,
) -> SkillReplayResult:
    return SkillReplayResult(
        result_ref=summary.result_ref,
        patch_id=summary.patch_id,
        suite_id=summary.suite_id,
        case_id=trajectory.case_id,
        trajectory_id=trajectory.trajectory_id,
        checkpoint_id=summary.checkpoint_id,
        checkpoint_trajectory_id=summary.checkpoint_trajectory_id,
        source_ref=summary.source_ref,
        kind=summary.kind,
        passed=summary.passed,
        failure_reasons=list(summary.failure_reasons),
        metrics=dict(summary.metrics),
        replay=replay,
    )
