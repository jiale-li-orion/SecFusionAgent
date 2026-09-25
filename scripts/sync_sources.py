import asyncio
from pathlib import Path

from packages.monitoring.storage.service import ensure_source_states
from packages.shared.db import create_engine, create_session_factory
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions


async def _run() -> None:
    definitions = load_source_definitions(Path("config/sources"))
    engine = create_engine()
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        source_ids = await sync_source_definitions(session, definitions)
        await ensure_source_states(session, source_ids)
    await engine.dispose()
    print(f"synced {len(definitions)} source definitions")


if __name__ == "__main__":
    asyncio.run(_run())
