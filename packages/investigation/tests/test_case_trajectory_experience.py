from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.investigation.cases.service import CaseService
from packages.investigation.experience.service import ExperienceDraft, ExperienceStore
from packages.investigation.storage.models import ExperienceVersionModel
from packages.investigation.trajectory.service import TrajectoryService, list_events
from packages.shared.db import Base


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 25, 15, 0, tzinfo=UTC)

    def now(self) -> datetime:
        current = self.value
        self.value += timedelta(seconds=1)
        return current


@pytest.mark.asyncio
async def test_case_trajectory_and_experience_evolution_lifecycle() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    clock = Clock()
    cases = CaseService(now=clock.now)
    trajectories = TrajectoryService(now=clock.now)
    experiences = ExperienceStore(now=clock.now)

    try:
        async with factory() as session, session.begin():
            case = await cases.create(
                session,
                task_signature="vulnerability-fix-boundary",
                target_object_ids=["vulnerability-1"],
                goal="Determine the first fixed release from repository evidence.",
                initial_knowledge_revision=12,
                constraints={"require_primary_evidence": True},
                rubric={"fixed_release_correct": True},
            )
            trajectory = await trajectories.start(session, case_id=case.case_id)
            first_event = await trajectories.append_event(
                session,
                trajectory_id=trajectory.trajectory_id,
                event_type="provider_query",
                payload={"provider": "github", "query": "fix commit"},
                evidence_refs=["observation-1"],
            )
            second_event = await trajectories.append_event(
                session,
                trajectory_id=trajectory.trajectory_id,
                event_type="hypothesis",
                payload={"statement": "merged PR may identify the fix commit"},
            )
            finished = await trajectories.finish(
                session,
                trajectory_id=trajectory.trajectory_id,
                outcome="success",
                outcome_summary={"fixed_release": "0.11.1"},
                cost=0.03,
            )
        assert first_event.ordinal == 1
        assert second_event.ordinal == 2
        assert finished.tool_calls == 1
        assert finished.latency_ms is not None and finished.latency_ms > 0

        async with factory() as session, session.begin():
            concurrent_case = await cases.create(
                session,
                task_signature="incident-follow-up",
                target_object_ids=["incident-1"],
                goal="Track one active incident.",
                initial_knowledge_revision=12,
            )
            running = await trajectories.start(session, case_id=concurrent_case.case_id)
            with pytest.raises(ValueError, match="already has a running trajectory"):
                await trajectories.start(session, case_id=concurrent_case.case_id)
            with pytest.raises(ValueError, match="running trajectory"):
                await cases.close(session, concurrent_case.case_id)
            await trajectories.finish(
                session,
                trajectory_id=running.trajectory_id,
                outcome="partial",
            )
            closed = await cases.close(session, concurrent_case.case_id)
            assert closed.status == "closed"

        draft = ExperienceDraft(
            name="Verify fix boundary through release containment",
            task_signature="vulnerability-fix-boundary",
            scope={"domain": "ai-infra", "provider": ["github"]},
            trigger_signals=["fix-pr-found"],
            applicable_conditions=["repository history is public"],
            recommended_actions=[
                "resolve fix PR to commit",
                "find the first release containing the fix commit",
            ],
            evidence_expectation=["fix commit", "release tag or changelog"],
            failure_modes=["PR merged_at does not prove released_at"],
            stop_conditions=["release containing fix commit is verified"],
            fallback_actions=["check vendor advisory and package registry"],
        )
        async with factory() as session, session.begin():
            candidate = await experiences.create_candidate(
                session,
                source_trajectory_id=trajectory.trajectory_id,
                extraction_kind="procedure",
                draft=draft,
                rationale="The successful trajectory separated merge time from release evidence.",
            )
            version1 = await experiences.materialize_candidate(session, candidate.candidate_id)
            version1 = await experiences.record_evaluation(
                session,
                experience_version_id=version1.experience_version_id,
                trajectory_id=trajectory.trajectory_id,
                outcome="success",
                evaluation={"evidence_correct": True, "unsupported_claims": 0},
                evaluator="m7-fixture",
            )
            version1 = await experiences.mark_validated(
                session,
                version1.experience_version_id,
                validation_summary={"approved_by": "m7-fixture", "replay_cases": 1},
            )
            version1 = await experiences.activate(session, version1.experience_version_id)
        assert version1.status == "active"
        assert version1.success_count == 1

        async with factory() as session, session.begin():
            with pytest.raises(ValueError, match="cannot be validated from status=active"):
                await experiences.mark_validated(
                    session,
                    version1.experience_version_id,
                    validation_summary={"should_not_apply": True},
                )

        async with factory() as session:
            retrieved = await experiences.retrieve(
                session,
                task_signature="vulnerability-fix-boundary",
                scope_filter={"domain": "ai-infra"},
            )
        assert [item.experience_version_id for item in retrieved] == [
            version1.experience_version_id
        ]

        async with factory() as session, session.begin():
            replay_case = await cases.create(
                session,
                task_signature="vulnerability-fix-boundary",
                target_object_ids=["vulnerability-2"],
                goal="Replay the fix-boundary procedure on another repository.",
                initial_knowledge_revision=18,
            )
            replay_trajectory = await trajectories.start(
                session,
                case_id=replay_case.case_id,
                retrieved_experience_versions=[version1.experience_version_id],
            )
            await trajectories.append_event(
                session,
                trajectory_id=replay_trajectory.trajectory_id,
                event_type="experience_used",
                experience_version_refs=[version1.experience_version_id],
                payload={"reason": "same task signature and repo evidence shape"},
            )
            replay_trajectory = await trajectories.finish(
                session,
                trajectory_id=replay_trajectory.trajectory_id,
                outcome="partial",
                outcome_summary={"gap": "release tag unavailable"},
            )
            version1_after_replay = await experiences.record_evaluation(
                session,
                experience_version_id=version1.experience_version_id,
                trajectory_id=replay_trajectory.trajectory_id,
                outcome="partial",
                evaluation={"evidence_correct": True, "gap": "release metadata"},
                evaluator="m7-fixture",
            )
        assert replay_trajectory.used_experience_versions == [version1.experience_version_id]
        assert version1_after_replay.success_count == 1
        assert version1_after_replay.partial_count == 1

        revised_draft = draft.model_copy(
            update={
                "fallback_actions": [
                    "check vendor advisory",
                    "check package registry publication time",
                    "record unknown if no release evidence is available",
                ]
            }
        )
        async with factory() as session, session.begin():
            revision_candidate = await experiences.create_candidate(
                session,
                source_trajectory_id=replay_trajectory.trajectory_id,
                extraction_kind="fallback",
                draft=revised_draft,
                rationale="Replay exposed a missing-release-metadata failure mode.",
            )
            version2 = await experiences.materialize_candidate(
                session,
                revision_candidate.candidate_id,
                experience_id=version1.experience_id,
            )
            assert version2.version == 2
            assert version2.supersedes_version_id == version1.experience_version_id
            version2 = await experiences.record_evaluation(
                session,
                experience_version_id=version2.experience_version_id,
                trajectory_id=replay_trajectory.trajectory_id,
                outcome="success",
                evaluation={"fallback_resolved_gap": True},
                evaluator="m7-fixture",
            )
            version2 = await experiences.mark_validated(
                session,
                version2.experience_version_id,
                validation_summary={"approved_by": "m7-fixture", "replay_cases": 1},
            )
            version2 = await experiences.activate(session, version2.experience_version_id)
        assert version2.status == "active"

        async with factory() as session:
            stored_v1 = await session.get(
                ExperienceVersionModel,
                version1.experience_version_id,
            )
            assert stored_v1 is not None and stored_v1.status == "deprecated"
            active = await experiences.retrieve(
                session,
                task_signature="vulnerability-fix-boundary",
            )
            assert [item.experience_version_id for item in active] == [
                version2.experience_version_id
            ]
            events = await list_events(session, replay_trajectory.trajectory_id)
            assert [event.ordinal for event in events] == [1]
            assert events[0].experience_version_refs == [version1.experience_version_id]
    finally:
        await engine.dispose()
