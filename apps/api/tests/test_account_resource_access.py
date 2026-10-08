from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import database_session
from apps.api.main import create_app
from apps.api.tests.test_product_agents import NOW, _database
from apps.application.authentication import AccountUserModel, issue_account_session
from apps.application.queries.agents import get_agent_runtime_overview
from apps.application.queries.decisions import DecisionQueries
from apps.application.queries.investigations import InvestigationQueries
from apps.application.question_sessions import QuestionSessionModel, QuestionSessionTurnModel
from packages.investigation.cases.service import CaseService
from packages.reasoning.decision import DecisionResult
from packages.reasoning.storage import DecisionResultStore
from packages.runtime.model.storage import ModelRequestModel
from packages.task_runtime.storage.models import TaskContractVersionModel, TaskRunModel


@pytest.mark.asyncio
async def test_account_owned_cases_decisions_tasks_and_runtime_do_not_cross_accounts():
    engine, factory = await _database()
    app = create_app()
    app.state.session_factory = factory

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with factory() as session, session.begin():
            for user_id in ("test", "other"):
                session.add(
                    AccountUserModel(
                        user_id=user_id,
                        email=f"{user_id}@example.invalid",
                        display_name=user_id,
                        password_hash="fixture-unused",
                        active=True,
                        created_at=NOW,
                    )
                )
            await session.flush()
            owner_token = await issue_account_session(session, "test")
            foreign_token = await issue_account_session(session, "other")
            case = await CaseService().create(
                session,
                task_signature="fixture",
                target_object_ids=[],
                goal="private goal",
                initial_knowledge_revision=None,
            )
            await session.execute(
                update(TaskRunModel)
                .where(TaskRunModel.run_id == "task-run-1")
                .values(case_id=case.case_id)
            )
            source = await session.get(TaskContractVersionModel, "contract-version-1")
            run = await session.get(TaskRunModel, "task-run-1")
            contract_values = {
                column.name: getattr(source, column.name) for column in source.__table__.columns
            }
            run_values = {
                column.name: getattr(run, column.name) for column in run.__table__.columns
            }
            system_cases = {}
            for name, on_behalf in (("public", None), ("delegated", "user:test")):
                system_case = await CaseService().create(
                    session,
                    task_signature=name,
                    target_object_ids=[],
                    goal=f"{name} system goal",
                    initial_knowledge_revision=None,
                )
                system_cases[name] = system_case.case_id
                session.add(
                    TaskContractVersionModel(
                        **{
                            **contract_values,
                            "task_contract_version_id": f"contract-{name}",
                            "task_contract_id": name,
                            "principal": "system:collection",
                            "on_behalf_of": on_behalf,
                            "contract_json": {
                                "task_contract_id": name,
                                "contract_revision": 1,
                                "principal": "system:collection",
                                "on_behalf_of": on_behalf,
                                "task_kind": "verify_version_fix",
                                "desired_state": {"answered": True},
                                "effect_ceiling": "read_only",
                                "completion_predicate": {"answered": True},
                                "policy_revision": "policy-v1",
                            },
                        }
                    )
                )
                session.add(
                    TaskRunModel(
                        **{
                            **run_values,
                            "run_id": name,
                            "task_contract_version_id": f"contract-{name}",
                            "task_contract_id": name,
                            "case_id": system_case.case_id,
                            "parent_run_id": "task-run-1",
                        }
                    )
                )
            await session.flush()
            session.add(
                QuestionSessionModel(
                    session_id="private-session",
                    principal="user:test",
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            session.add(
                QuestionSessionTurnModel(
                    turn_id="private-turn",
                    session_id="private-session",
                    turn_index=1,
                    request_id="direct-request",
                    question="private question",
                    task_kind="verify_version_fix",
                    target_object_ids=[],
                    decision_ref="private-direct-decision",
                    created_at=NOW,
                )
            )
            request = await session.get(ModelRequestModel, "model-request-1")
            request_values = {
                column.name: getattr(request, column.name) for column in request.__table__.columns
            }
            for name, task, owner_ref in (
                ("direct-owned", None, "product-request:direct-request"),
                ("unowned", None, "unknown"),
                ("public-model", "public", "task:public"),
            ):
                session.add(
                    ModelRequestModel(
                        **{
                            **request_values,
                            "model_request_id": name,
                            "task_run_id": task,
                            "request_owner_ref": owner_ref,
                        }
                    )
                )
            for decision_id, case_id in (
                ("private-case-decision", case.case_id),
                ("private-direct-decision", "ephemeral-case"),
                ("public-case-decision", system_cases["public"]),
                ("delegated-case-decision", system_cases["delegated"]),
            ):
                await DecisionResultStore().persist(
                    session,
                    DecisionResult(
                        decision_id=decision_id,
                        case_id=case_id,
                        case_revision=0,
                        stop_reason="answered",
                        model_prompt_revision="fixture",
                        answer_payload={"answer": "private answer"},
                    ),
                )

        owner = {"Cookie": f"secfusion_session={owner_token}"}
        foreign = {"Cookie": f"secfusion_session={foreign_token}", "X-Principal": "user:test"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            private_paths = [
                f"/api/v1/investigations/{case.case_id}",
                f"/api/v1/investigations/{case.case_id}/activity",
                f"/api/v1/investigations/{case.case_id}/events?follow=false",
                "/api/v1/decisions/private-case-decision",
                "/api/v1/decisions/private-direct-decision",
                "/api/v1/tasks/task-run-1",
            ]
            for path in private_paths:
                assert (await client.get(path)).status_code == 401
                denied = await client.get(path, headers=foreign)
                assert denied.status_code == 404, (path, denied.text)
                accepted = await client.get(path, headers=owner)
                assert accepted.status_code == 200, (path, accepted.text)
            assert (await client.get("/api/v1/investigations", headers=foreign)).json()[
                "items"
            ] == []
            for suffix in ("", "/activity", "/events?follow=false"):
                public_path = f"/api/v1/investigations/{system_cases['public']}{suffix}"
                assert (await client.get(public_path)).status_code == 401
                assert (await client.get(public_path, headers=foreign)).status_code == 200
                delegated_path = f"/api/v1/investigations/{system_cases['delegated']}{suffix}"
                assert (await client.get(delegated_path, headers=foreign)).status_code == 404
                assert (await client.get(delegated_path, headers=owner)).status_code == 404
            public_case = await client.get(
                f"/api/v1/investigations/{system_cases['public']}", headers=foreign
            )
            assert public_case.json()["can_cancel"] is False
            assert (
                await client.get("/api/v1/decisions/public-case-decision", headers=foreign)
            ).status_code == 200
            assert (
                await client.get("/api/v1/decisions/delegated-case-decision", headers=foreign)
            ).status_code == 404
            denied_cancel = await client.post(
                f"/api/v1/investigations/{system_cases['public']}/cancel",
                headers={**foreign, "X-SecFusion-CSRF": "1"},
            )
            assert denied_cancel.status_code == 403
            assert denied_cancel.json()["code"] == "permission_denied"
            own_page = await client.get("/api/v1/investigations?limit=1", headers=owner)
            assert [item["case_id"] for item in own_page.json()["items"]] == [case.case_id]
            foreign_tasks = await client.get("/api/v1/tasks", headers=foreign)
            assert [item["run_id"] for item in foreign_tasks.json()["items"]] == ["public"]
            assert foreign_tasks.json()["items"][0]["parent_run_id"] is None
            public_detail = await client.get("/api/v1/tasks/public", headers=foreign)
            assert public_detail.json()["parent"] is None
            assert public_detail.json()["task"]["parent_run_id"] is None
            foreign_runtime = (await client.get("/api/v1/agents/runtime", headers=foreign)).json()
            assert foreign_runtime["model_runtime"]["request_count"] == 1
            assert foreign_runtime["model_runtime"]["attempt_count"] == 0
            assert foreign_runtime["control_runtime"]["sampled_task_count"] == 1
            role = next(
                item for item in foreign_runtime["roles"] if item["role_id"] == "InvestigationRole"
            )
            assert role["total_tasks"] == 1
            own_runtime = (await client.get("/api/v1/agents/runtime", headers=owner)).json()
            assert own_runtime["model_runtime"]["request_count"] == 2
            assert own_runtime["model_runtime"]["attempt_count"] == 2
            # A public controller does not publish a Case once any user run
            # joins it, even when the user run has a different Role.
            async with factory() as session, session.begin():
                session.add(
                    TaskRunModel(
                        **{
                            **run_values,
                            "run_id": "mixed-private-child",
                            "case_id": system_cases["public"],
                            "role_id": "EnrichmentRole",
                        }
                    )
                )
            assert (
                await client.get(
                    f"/api/v1/investigations/{system_cases['public']}", headers=foreign
                )
            ).status_code == 404
            assert (
                await client.get("/api/v1/decisions/public-case-decision", headers=foreign)
            ).status_code == 404
        # Internal diagnostics retain their explicitly unscoped compatibility.
        async with factory() as session:
            assert (await InvestigationQueries().get(session, case.case_id)).case_id == case.case_id
            assert (
                await DecisionQueries().get(session, "private-direct-decision")
            ).decision_id == "private-direct-decision"
            assert (await get_agent_runtime_overview(session)).model_runtime.request_count == 4
    finally:
        await engine.dispose()
