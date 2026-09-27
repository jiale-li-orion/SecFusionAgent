from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.application.commands.start_investigation import (
    StartInvestigationCommand,
    StartInvestigationUseCase,
)
from apps.application.queries.investigations import InvestigationQueries
from apps.runtime_models import register_runtime_models
from packages.intelligence.storage.knowledge_models import (
    ExternalIdentifierModel,
    KnowledgeRevisionModel,
    ObjectModel,
)
from packages.investigation.storage.models import InvestigationCaseModel
from packages.runtime.storage.models import BudgetAccountModel, ExecutionRunModel
from packages.shared.config import get_settings
from packages.shared.db import Base
from packages.task_runtime.contracts.models import TaskKind
from packages.task_runtime.storage.models import TaskRunModel

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


async def _factory():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed_vulnerability(factory) -> str:
    async with factory() as session, session.begin():
        revision = KnowledgeRevisionModel(committed_at=NOW)
        session.add(revision)
        await session.flush()
        obj = ObjectModel(
            object_id="product-vuln-object",
            object_type="Vulnerability",
            canonical_key="cve:CVE-2026-42424",
            properties={"display_name": "CVE-2026-42424"},
            created_revision=revision.revision,
        )
        session.add(obj)
        session.add(
            ExternalIdentifierModel(
                external_identifier_id="product-vuln-cve-id",
                namespace="cve",
                value="CVE-2026-42424",
                object_id=obj.object_id,
            )
        )
    return "product-vuln-object"


@pytest.mark.asyncio
async def test_start_investigation_builds_real_domain_runtime_coordinate() -> None:
    engine, factory = await _factory()
    await _seed_vulnerability(factory)
    settings = get_settings()
    use_case = StartInvestigationUseCase(
        policy_path=settings.runtime_policy_path,
        task_event_stream_name=settings.task_event_stream_name,
    )
    try:
        async with factory() as session:
            result = await use_case.execute(
                session,
                StartInvestigationCommand(
                    principal="user:test",
                    request_id="request-product-1",
                    cve_id="CVE-2026-42424",
                    goal="Confirm the first fixed release.",
                    evidence_question="Which release first contains the fix?",
                    task_kind=TaskKind.VERIFY_VERSION_FIX,
                    required_source_roles=["primary"],
                ),
            )
            view = result.investigation
            assert view.status == "active"
            assert view.execution_profile == "VERIFY"
            assert len(view.open_evidence_needs) == 1
            assert view.open_evidence_needs[0].required_source_roles == ["primary"]
            assert view.current_activity.task_status == "queued"

        async with factory() as session:
            case = await session.get(InvestigationCaseModel, view.case_id)
            assert case is not None and case.status == "active"
            run = await session.scalar(
                select(TaskRunModel).where(TaskRunModel.case_id == view.case_id)
            )
            assert run is not None and run.status == "queued"
            execution = await session.scalar(
                select(ExecutionRunModel).where(ExecutionRunModel.task_run_id == run.run_id)
            )
            assert execution is not None
            assert execution.envelope_json["trace_context"]["request_id"] == "request-product-1"
            budget = await session.scalar(
                select(BudgetAccountModel).where(BudgetAccountModel.task_run_id == run.run_id)
            )
            assert budget is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_investigation_list_uses_opaque_cursor() -> None:
    engine, factory = await _factory()
    await _seed_vulnerability(factory)
    settings = get_settings()
    use_case = StartInvestigationUseCase(
        policy_path=settings.runtime_policy_path,
        task_event_stream_name=settings.task_event_stream_name,
    )
    try:
        async with factory() as session:
            for index in range(2):
                await use_case.execute(
                    session,
                    StartInvestigationCommand(
                        principal="user:test",
                        request_id=f"request-page-{index}",
                        object_id="product-vuln-object",
                        goal=f"Investigation {index}",
                        evidence_question=f"Question {index}?",
                    ),
                )

        async with factory() as session:
            query = InvestigationQueries()
            first = await query.list(session, limit=1)
            assert len(first.items) == 1
            assert first.has_more is True
            assert first.next_cursor is not None
            second = await query.list(session, limit=1, cursor=first.next_cursor)
            assert len(second.items) == 1
            assert second.items[0].case_id != first.items[0].case_id
    finally:
        await engine.dispose()
