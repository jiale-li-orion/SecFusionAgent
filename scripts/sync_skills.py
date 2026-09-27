import asyncio

from apps.runtime_models import register_runtime_models
from packages.investigation.skills.seeds import seeded_skills
from packages.investigation.skills.service import SkillStore
from packages.shared.db import create_engine, create_session_factory


async def _run() -> None:
    register_runtime_models()
    engine = create_engine()
    factory = create_session_factory(engine)
    skills = seeded_skills()
    async with factory() as session, session.begin():
        store = SkillStore()
        for skill in skills:
            await store.publish(session, skill)
    await engine.dispose()
    print(f"synced {len(skills)} candidate seed skills pending M7 validation")


if __name__ == "__main__":
    asyncio.run(_run())
