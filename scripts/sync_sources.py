import asyncio
from pathlib import Path

from apps.runtime_models import register_runtime_models
from packages.monitoring.registration import synchronize_monitoring_sources
from packages.shared.db import create_engine, create_session_factory
from packages.sources.registry.loader import load_source_definitions


async def _run() -> None:
    register_runtime_models()
    definitions = load_source_definitions(Path("config/sources"))
    engine = create_engine()
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        await synchronize_monitoring_sources(session, definitions)
    await engine.dispose()
    print(f"synced {len(definitions)} source definitions")


if __name__ == "__main__":
    asyncio.run(_run())
