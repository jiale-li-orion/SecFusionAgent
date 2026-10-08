from datetime import UTC, datetime

import pytest
from sqlalchemy import update

from apps.application.queries.agent_learning import (
    get_agent_learning_overview,
    get_product_experience,
    get_product_skill,
)
from packages.investigation.runtime.test_model_planner import _database, _seed
from packages.investigation.skills.storage import SkillVersionModel
from packages.investigation.storage.models import (
    ExperienceModel,
    ExperienceSupportModel,
    ExperienceVersionModel,
    InvestigationTrajectoryModel,
)
from packages.task_runtime.storage.models import TaskContractVersionModel


@pytest.mark.asyncio
async def test_public_learning_excludes_user_and_delegated_user_provenance() -> None:
    engine, factory = await _database()
    try:
        _, _, contract, state, _, _ = await _seed(factory)
        now = datetime.now(UTC)
        async with factory() as session, session.begin():
            session.add(
                InvestigationTrajectoryModel(
                    trajectory_id="privacy-trajectory",
                    case_id=state.case_id,
                    status="completed",
                    started_at=now,
                )
            )
            session.add(
                ExperienceModel(
                    experience_id="privacy-experience",
                    name="Private user question",
                    task_signature="verify_version_fix",
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.flush()
            session.add(
                ExperienceVersionModel(
                    experience_version_id="privacy-version",
                    experience_id="privacy-experience",
                    version=1,
                    status="active",
                    recommended_actions=["Private recommendation"],
                    created_at=now,
                )
            )
            await session.flush()
            session.add(
                ExperienceSupportModel(
                    support_id="privacy-support",
                    experience_version_id="privacy-version",
                    trajectory_id="privacy-trajectory",
                    outcome="success",
                    evaluator="test",
                    created_at=now,
                )
            )
            for kind in ("seeded", "experience_derived"):
                session.add(
                    SkillVersionModel(
                        skill_version_id=f"privacy-{kind}",
                        skill_id=f"test.{kind}",
                        version=1,
                        namespace="test",
                        status="active",
                        source_type=kind,
                        manifest_json={},
                        procedure_json={},
                        provenance_json={},
                        content_hash="0" * 64,
                        created_at=now,
                    )
                )
        async with factory() as session:
            overview = await get_agent_learning_overview(session)
            assert overview.experiences == []
            assert overview.trajectory_count == 0
            assert "test.seeded" in {skill.skill_id for skill in overview.skills}
            assert "test.experience_derived" not in {skill.skill_id for skill in overview.skills}
            assert await get_product_experience(session, "privacy-version") is None
            assert await get_product_skill(session, "skill:test.experience_derived@1") is None
        async with factory() as session, session.begin():
            await session.execute(
                update(TaskContractVersionModel)
                .where(TaskContractVersionModel.task_contract_id == contract.task_contract_id)
                .values(principal="system:learning")
            )
        async with factory() as session:
            overview = await get_agent_learning_overview(session)
            assert overview.trajectory_count == 1
            assert len(overview.experiences) == 1
        async with factory() as session, session.begin():
            await session.execute(
                update(TaskContractVersionModel)
                .where(TaskContractVersionModel.task_contract_id == contract.task_contract_id)
                .values(on_behalf_of="user:another-account")
            )
        async with factory() as session:
            overview = await get_agent_learning_overview(session)
            assert overview.experiences == []
            assert overview.trajectory_count == 0
    finally:
        await engine.dispose()
