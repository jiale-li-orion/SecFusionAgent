from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.investigation.perception.contracts import (
    EvidenceRequirement,
    ObservedProposition,
    PerceptionOperation,
    PerceptionRequest,
    PerceptionStepResult,
    PerceptionTarget,
    PhysicalOperator,
    PhysicalPerceptionPlan,
    PhysicalPerceptionStep,
)
from packages.investigation.perception.planner import PerceptionPlanner
from packages.investigation.perception.runtime import PerceptionRuntime

NOW = datetime(2026, 9, 27, 11, 0, tzinfo=UTC)


class _PhysicalPort:
    def __init__(self) -> None:
        self.calls: list[tuple[str, PhysicalOperator]] = []

    async def execute(self, *, task_run_id, request, step):
        self.calls.append((task_run_id, step.operator))
        if step.operator is PhysicalOperator.EXTERNAL:
            return PerceptionStepResult(
                observed_propositions=[
                    ObservedProposition(
                        statement="Provider currently reports release v1.2.3.",
                        support_refs=["observation:provider-release-1"],
                        freshness={"observed_at": NOW.isoformat()},
                    )
                ],
                observation_handles=["observation:provider-release-1"],
                cost={"tool_calls": 1},
            )
        return PerceptionStepResult(
            observed_propositions=[
                ObservedProposition(
                    statement="Sandbox ancestry check reports commit is contained in the tag.",
                    support_refs=["observation:sandbox-ancestry-1"],
                )
            ],
            observation_handles=["observation:sandbox-ancestry-1"],
            cost={"sandbox_calls": 1},
        )


@pytest.mark.asyncio
async def test_observe_external_plans_physical_operator_without_claiming_evidence() -> None:
    request = PerceptionRequest(
        request_id="external-1",
        operation=PerceptionOperation.OBSERVE_EXTERNAL,
        target=PerceptionTarget(
            object_id="release-object",
            source_ids=["github-repo-vllm"],
        ),
        desired_observation="current release metadata",
        evidence_requirement=EvidenceRequirement(required_source_roles=["primary"]),
    )
    plan = PerceptionPlanner().plan(request)
    assert [step.operator for step in plan.steps] == [PhysicalOperator.EXTERNAL]
    assert plan.steps[0].capability_requirement == "external_observation"

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    port = _PhysicalPort()
    try:
        async with factory() as session:
            percept = await PerceptionRuntime(port).execute(
                session,
                request=request,
                plan=plan,
                task_run_id="run-1",
            )
        assert port.calls == [("run-1", PhysicalOperator.EXTERNAL)]
        assert percept.observation_handles == ["observation:provider-release-1"]
        assert percept.evidence_handles == []
        assert percept.candidate_evidence == []
        assert percept.observed_propositions[0].support_refs == ["observation:provider-release-1"]
        assert "required_source_role_missing:primary" in percept.unresolved
        assert "no_candidates" in percept.unresolved
        assert percept.cost["external:0:tool_calls"] == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_physical_operator_without_execution_port_fails_closed_into_unresolved() -> None:
    request = PerceptionRequest(
        request_id="external-missing-port",
        operation=PerceptionOperation.OBSERVE_EXTERNAL,
        target=PerceptionTarget(query_text="latest vendor advisory"),
    )
    plan = PerceptionPlanner().plan(request)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            percept = await PerceptionRuntime().execute(
                session,
                request=request,
                plan=plan,
                task_run_id="run-1",
            )
        assert "physical_operator_unavailable:external" in percept.unresolved
        assert percept.observation_handles == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_sandbox_plan_uses_same_physical_observation_port() -> None:
    request = PerceptionRequest(
        request_id="sandbox-1",
        operation=PerceptionOperation.TRACE,
        target=PerceptionTarget(object_id="commit-abc"),
        desired_observation="release containment",
    )
    plan = PhysicalPerceptionPlan(
        request_id=request.request_id,
        steps=[
            PhysicalPerceptionStep(
                step_id="sandbox:0",
                operator=PhysicalOperator.SANDBOX,
                input={
                    "program_ref": "program:verify-release",
                    "arguments": {"release": "v1.2.3"},
                },
                expected_output_type="ephemeral_observation",
                capability_requirement="git.ancestry_check",
                estimated_cost="medium",
            )
        ],
    )
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    port = _PhysicalPort()
    try:
        async with factory() as session:
            percept = await PerceptionRuntime(port).execute(
                session,
                request=request,
                plan=plan,
                task_run_id="run-2",
            )
        assert port.calls == [("run-2", PhysicalOperator.SANDBOX)]
        assert percept.observation_handles == ["observation:sandbox-ancestry-1"]
        assert percept.evidence_handles == []
        assert percept.cost["sandbox:0:sandbox_calls"] == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_trace_preserves_incoming_edge_and_fetches_its_real_evidence() -> None:
    from packages.intelligence.retrieval.contracts import CandidateKind, RetrievedCandidate

    class Graph:
        async def neighbors(self, session, **arguments):
            assert arguments == {
                "object_id": "repo", "direction": "both", "relation_types": [], "limit": 1,
            }
            return [RetrievedCandidate(
                candidate_id="relation:pr-repo", candidate_kind=CandidateKind.RELATION,
                relation_id="pr-repo", score_channels={"graph": 1.0},
                payload={"relation_type": "belongs-to-repo",
                         "source": {"object_id": "pr"}, "target": {"object_id": "repo"}},
            )]

    class Evidence:
        async def for_target(self, session, *, target_kind, target_id, limit=None):
            assert (target_kind, target_id) == ("relation", "pr-repo")
            assert limit == 2  # One candidate plus one bounded truncation probe.
            return [RetrievedCandidate(
                candidate_id="evidence:association", candidate_kind=CandidateKind.EVIDENCE,
                evidence_ref="evidence:association", source_id="github-test", source_role="primary",
                score_channels={"evidence": 1.0}, payload={"target_id": "pr-repo"},
            )]

    runtime = PerceptionRuntime()
    runtime._graph, runtime._evidence = Graph(), Evidence()
    request = PerceptionRequest(
        request_id="trace-with-evidence", operation=PerceptionOperation.TRACE,
        target=PerceptionTarget(object_id="repo"),
        evidence_requirement=EvidenceRequirement(max_candidates=1, min_independent_sources=1),
    )
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with async_sessionmaker(engine)() as session:
            result = await runtime.execute(
                session, request=request, plan=PerceptionPlanner().plan(request),
            )
        assert result.evidence_handles == ["evidence:association"]
        assert result.relations[0]["source"] == {"object_id": "pr"}
        assert result.relations[0]["relation_id"] == "pr-repo"
        assert result.unresolved == []
        assert result.operator_counts == {"graph": 1, "evidence": 1}
        assert result.cost["graph-evidence:0:read_queries"] == 1
        assert result.observed_propositions == []  # No factual promotion during a read.
    finally:
        await engine.dispose()
