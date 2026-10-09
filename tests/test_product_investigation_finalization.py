import asyncio
from contextlib import asynccontextmanager
from typing import Any

import pytest

from apps.application.commands.finalize_investigation import (
    FinalizationBusyError,
    FinalizeInvestigationUseCase,
)
from apps.application.queries.agents import get_agent_task_detail, list_agent_tasks
from packages.investigation.cases.service import CaseService
from packages.investigation.runtime.test_model_planner import (
    _attach_primary_evidence,
    _database,
    _seed,
)
from packages.investigation.state.contracts import ProposedState, StatePatch, StatePatchOperation
from packages.investigation.state.service import InvestigationStateService
from packages.investigation.storage.models import InvestigationCaseModel
from packages.reasoning.model import DecisionPlannerResponse
from packages.shared.config import Settings
from packages.task_runtime.contracts.models import TaskRunStatus
from packages.task_runtime.storage.service import transition_task_run


@pytest.fixture
def lease():
    locked = False

    @asynccontextmanager
    async def acquire(_run_id):
        nonlocal locked
        if locked:
            yield False
            return
        locked = True
        try:
            yield True
        finally:
            locked = False

    return acquire


class DecisionProvider:
    name = "finalization-test"
    version = "1"

    def __init__(self) -> None:
        self.calls = 0

    async def generate_structured(self, request: Any, response_model: Any) -> Any:
        self.calls += 1
        assert 0 < request.metadata["model_wall_seconds"] <= 60
        state = request.data["investigation_state"]
        finding = state["confirmed"][0]
        assert response_model is DecisionPlannerResponse
        return response_model.model_validate(
            {
                "action": {
                    "kind": "final",
                    "stop_reason": "evidence_sufficient",
                    "answer_payload": {"first_fixed_version": "1.2.3"},
                    "conclusions": [
                        {
                            "statement": finding["proposition"],
                            "type": "fact",
                            "evidence_refs": finding["evidence_refs"],
                        }
                    ],
                }
            }
        )


@pytest.mark.asyncio
async def test_completed_product_investigation_commits_cited_decision_once(lease) -> None:
    engine, factory = await _database()
    try:
        run_id, state = await _completed_case(factory)
        provider = DecisionProvider()
        finalizer = FinalizeInvestigationUseCase(factory, Settings(), provider, lease=lease)
        first = await finalizer.execute(run_id)
        assert first and first.startswith("decision:")
        assert await finalizer.execute(run_id) == first
        assert provider.calls == 1
        async with factory() as session:
            result = await InvestigationStateService().get_state(session, state.case_id)
            assert result.current_decision is not None
            assert result.current_decision["citations"]
            assert result.current_decision["answer_payload"] == {"first_fixed_version": "1.2.3"}
            tasks = await list_agent_tasks(session, case_id=state.case_id)
            decision_task = next(item for item in tasks.items if item.role_id == "DecisionRole")
            assert decision_task.parent_run_id is None  # Sequential handoff, not delegation.
            assert decision_task.predecessor_run_id == run_id
            detail = await get_agent_task_detail(session, decision_task.run_id)
            assert detail and detail.predecessor and detail.predecessor.run_id == run_id
    finally:
        await engine.dispose()


async def _completed_case(factory):
    run_id, object_id, _, state, need, _ = await _seed(factory)
    evidence = await _attach_primary_evidence(factory, object_id=object_id)
    async with factory() as session, session.begin():
        await CaseService().activate(session, state.case_id)
        for status in (TaskRunStatus.QUEUED, TaskRunStatus.RUNNING):
            await transition_task_run(
                session,
                run_id=run_id,
                target=status,
                idempotency_key=f"test:{status}",
                payload_ref="test",
                stream_name="secfusion:test-finalize",
            )
        await InvestigationStateService().apply_patch(
            session,
            StatePatch(
                patch_id="test:confirmed",
                case_id=state.case_id,
                base_case_revision=state.case_revision,
                producer="test",
                operations=[
                    StatePatchOperation(
                        proposition="Primary evidence establishes fix 1.2.3.",
                        target_ref=f"object:{object_id}",
                        proposed_state=ProposedState.CONFIRMED,
                        evidence_refs=[f"evidence:{evidence}"],
                        resolves_need_id=need.need_id,
                    )
                ],
            ),
        )
        await transition_task_run(
            session,
            run_id=run_id,
            target=TaskRunStatus.COMPLETED,
            idempotency_key="test:completed",
            payload_ref="test",
            stream_name="secfusion:test-finalize",
        )
    return run_id, state


@pytest.mark.asyncio
async def test_concurrent_redelivery_cannot_duplicate_or_fail_running_decision(lease) -> None:
    entered, release = asyncio.Event(), asyncio.Event()

    class SlowProvider(DecisionProvider):
        async def generate_structured(self, request: Any, response_model: Any) -> Any:
            entered.set()
            await release.wait()
            return await super().generate_structured(request, response_model)

    engine, factory = await _database()
    try:
        run_id, _state = await _completed_case(factory)
        provider = SlowProvider()
        finalizer = FinalizeInvestigationUseCase(factory, Settings(), provider, lease=lease)
        first = asyncio.create_task(finalizer.execute(run_id))
        await asyncio.wait_for(entered.wait(), timeout=3)
        with pytest.raises(FinalizationBusyError):
            await finalizer.execute(run_id)
        release.set()
        result = await first
        assert result and result.startswith("decision:")
        assert provider.calls == 1
        assert await finalizer.execute(run_id) == result
    finally:
        release.set()
        await engine.dispose()


@pytest.mark.asyncio
async def test_decision_evidence_gap_waits_with_a_durable_need(lease) -> None:

    class GapProvider(DecisionProvider):
        async def generate_structured(self, request: Any, response_model: Any) -> Any:
            return response_model.model_validate(
                {
                    "action": {
                        "kind": "continue",
                        "proposition_or_question": "Confirm downstream applicability",
                        "purpose": "verify_applicability",
                        "reason": "Downstream evidence is missing",
                        "target_objects": request.data["investigation_state"]["targets"],
                    }
                }
            )

    engine, factory = await _database()
    try:
        run_id, state = await _completed_case(factory)
        result = await FinalizeInvestigationUseCase(
            factory, Settings(), GapProvider(), lease=lease
        ).execute(run_id)
        assert result and result.startswith("evidence-need:")
        async with factory() as session:
            case = await session.get(InvestigationCaseModel, state.case_id)
            assert case is not None
            assert case.status == "waiting"
            needs = await InvestigationStateService().list_evidence_needs(session, state.case_id)
            assert any(
                need.proposition_or_question == "Confirm downstream applicability" for need in needs
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_blocked_product_investigation_returns_honest_readable_answer(lease) -> None:
    engine, factory = await _database()
    try:
        run_id, _object_id, _contract, state, _need, _manifest = await _seed(factory)
        async with factory() as session, session.begin():
            await CaseService().activate(session, state.case_id)
            for status in (TaskRunStatus.QUEUED, TaskRunStatus.RUNNING, TaskRunStatus.BLOCKED):
                await transition_task_run(
                    session,
                    run_id=run_id,
                    target=status,
                    idempotency_key=f"test:insufficient:{status}",
                    payload_ref="test",
                    stream_name="secfusion:test-finalize",
                    stop_reason="no_progress" if status is TaskRunStatus.BLOCKED else None,
                )
        provider = DecisionProvider()
        result_ref = await FinalizeInvestigationUseCase(
            factory, Settings(), provider, lease=lease
        ).execute(run_id)
        assert result_ref and result_ref.startswith("decision:")
        assert provider.calls == 0
        async with factory() as session:
            current = await InvestigationStateService().get_state(session, state.case_id)
            assert current.current_decision is not None
            assert current.current_decision["stop_reason"] == "evidence_insufficient"
            assert current.current_decision["report_paragraphs"][0]["text"]
            assert current.current_decision["citations"] == []
            case = await session.get(InvestigationCaseModel, state.case_id)
            assert case is not None and case.status == "waiting"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_invalid_final_report_is_replaced_with_evidence_boundary(lease) -> None:
    class InvalidProvider(DecisionProvider):
        async def generate_structured(self, request: Any, response_model: Any) -> Any:
            return response_model.model_validate({"action": {
                "kind": "final",
                "stop_reason": "evidence_sufficient",
                "conclusions": [{
                    "statement": "An unsupported reformulation of the finding.",
                    "type": "fact",
                    "evidence_refs": (
                        request.data["investigation_state"]["confirmed"][0]["evidence_refs"]
                    ),
                }],
            }})

    engine, factory = await _database()
    try:
        run_id, state = await _completed_case(factory)
        result_ref = await FinalizeInvestigationUseCase(
            factory, Settings(), InvalidProvider(), lease=lease
        ).execute(run_id)
        assert result_ref and result_ref.startswith("decision:")
        async with factory() as session:
            current = await InvestigationStateService().get_state(session, state.case_id)
            assert current.current_decision is not None
            assert current.current_decision["stop_reason"] == "evidence_insufficient"
            assert current.current_decision["conclusions"] == []
            assert current.current_decision["citations"] == []
            case = await session.get(InvestigationCaseModel, state.case_id)
            assert case is not None and case.status == "waiting"
    finally:
        await engine.dispose()
