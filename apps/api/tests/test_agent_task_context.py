from __future__ import annotations

import pytest

from apps.api.tests.test_product_agents import NOW, _database
from apps.application.queries.agents import get_agent_task_detail, list_agent_tasks
from apps.application.question_sessions import QuestionSessionModel
from packages.investigation.storage.models import InvestigationCaseModel
from packages.runtime.storage.models import ExecutionRunModel
from packages.task_runtime.storage.models import TaskContractVersionModel, TaskRunModel


@pytest.mark.asyncio
@pytest.mark.parametrize("session_owner", ["user:test", "user:other"])
async def test_task_conversation_link_requires_session_ownership(session_owner: str) -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            session.add(
                QuestionSessionModel(
                    session_id="linked-session",
                    principal=session_owner,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            session.add(
                ExecutionRunModel(
                    execution_id="execution-test",
                    task_run_id="task-run-1",
                    status="running",
                    envelope_json={"trace_context": {"product_session_id": "linked-session"}},
                    created_at=NOW,
                )
            )
        async with factory() as session:
            result = await get_agent_task_detail(session, "task-run-1", principal="user:test")
            assert result is not None
            assert result.task.session_id == (
                "linked-session" if session_owner == "user:test" else None
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("case_owner", ["user:test", "user:other"])
async def test_task_case_goal_uses_case_ownership_before_projection(case_owner: str) -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            contract = await session.get(TaskContractVersionModel, "contract-version-1")
            assert contract is not None
            contract.contract_json = {"desired_state": {"case_id": "case-context"}}
            run = await session.get(TaskRunModel, "task-run-1")
            assert run is not None
            run.case_id = "case-context"
            run.role_id = "DecisionRole"
            session.add(
                InvestigationCaseModel(
                    case_id="case-context",
                    task_signature="signature-context",
                    goal="Case goal",
                    target_object_ids=[],
                    constraints={},
                    rubric={},
                    status="active",
                    created_at=NOW,
                )
            )
            session.add(
                TaskContractVersionModel(
                    task_contract_version_id="controller-contract",
                    task_contract_id="controller",
                    contract_revision=1,
                    principal=case_owner,
                    task_kind="verify_version_fix",
                    effect_ceiling="read_only",
                    policy_revision="policy-v1",
                    contract_json={},
                    content_hash="c" * 64,
                    created_at=NOW,
                )
            )
            session.add(
                TaskRunModel(
                    run_id="controller-run",
                    task_contract_version_id="controller-contract",
                    task_contract_id="controller",
                    task_contract_revision=1,
                    context_manifest_version_id="context-version-1",
                    context_id="context-1",
                    context_revision=1,
                    case_id="case-context",
                    role_id="InvestigationRole",
                    role_version="1",
                    status="running",
                    base_context_revision=1,
                    execution_envelope_ref="controller-envelope",
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        async with factory() as session:
            page = await list_agent_tasks(session, principal="user:test")
            result = next(item for item in page.items if item.run_id == "task-run-1")
            assert result.goal == ("Case goal" if case_owner == "user:test" else None)
    finally:
        await engine.dispose()
