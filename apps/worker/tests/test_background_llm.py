from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from apps.worker import editorial, scheduler, tasks
from packages.enrichment.providers.factory import create_configured_ai_provider
from packages.shared.config import Settings


@pytest.mark.asyncio
async def test_editorial_pause_wins_over_editorial_enabled(monkeypatch):
    settings = Settings(background_llm_enabled=False, editorial_enabled=True)
    monkeypatch.setattr(editorial, "get_settings", lambda: settings)
    engine = MagicMock(side_effect=AssertionError("disabled editorial touched database"))
    monkeypatch.setattr(editorial, "create_engine", engine)
    assert await editorial.run_editorial("queued-before-pause") == "disabled"
    engine.assert_not_called()


@pytest.mark.asyncio
async def test_pause_keeps_source_scheduling_and_outbox_delivery(monkeypatch):
    settings = Settings(background_llm_enabled=False, editorial_enabled=True)
    monkeypatch.setattr(scheduler, "get_settings", lambda: settings)
    engine = MagicMock(dispose=AsyncMock())
    session = MagicMock()
    session.begin.return_value = AsyncMock()
    context = AsyncMock()
    context.__aenter__.return_value = session
    monkeypatch.setattr(scheduler, "create_engine", lambda _: engine)
    monkeypatch.setattr(scheduler, "create_session_factory", lambda _: lambda: context)
    mocks = {}
    for name, value in [
        ("recover_stale_acquisition_runs", []),
        ("schedule_due_sources", ["source"]),
        ("dispatch_pending_events", 3),
        ("schedule_editorial", None),
    ]:
        mocks[name] = AsyncMock(return_value=value)
        monkeypatch.setattr(scheduler, name, mocks[name])
    assert await scheduler.tick() == (1, 0, 3)
    mocks["schedule_due_sources"].assert_awaited_once()
    mocks["dispatch_pending_events"].assert_awaited_once()
    mocks["schedule_editorial"].assert_not_awaited()


@pytest.mark.asyncio
async def test_background_pause_preserves_interactive_model_provider():
    settings = Settings(
        background_llm_enabled=False,
        model_base_url="https://model.invalid/v1",
        model_name="interactive",
    )
    async with httpx.AsyncClient() as client:
        assert create_configured_ai_provider(settings, client) is not None


@pytest.mark.asyncio
async def test_pause_preserves_projection_without_automatic_watch(monkeypatch):
    monkeypatch.setattr(tasks, "get_settings", lambda: Settings(background_llm_enabled=False))
    engine = MagicMock(dispose=AsyncMock())
    session = MagicMock()
    session.begin.return_value = AsyncMock()
    context = AsyncMock()
    context.__aenter__.return_value = session
    monkeypatch.setattr(tasks, "create_engine", lambda _: engine)
    monkeypatch.setattr(tasks, "create_session_factory", lambda _: lambda: context)
    projection = MagicMock(
        rebuild_knowledge_object_views=AsyncMock(return_value=[MagicMock(changed=True)])
    )
    world = MagicMock(process=AsyncMock(return_value=["impact"]))
    watch = MagicMock(spawn_for_world_change=AsyncMock())
    monkeypatch.setattr(tasks, "CurrentProjectionService", lambda: projection)
    monkeypatch.setattr(tasks, "WorldChangeService", lambda: world)
    monkeypatch.setattr(tasks, "WatchWakeService", lambda **_: watch)
    assert await tasks._rebuild_knowledge_projections({"revision": 1, "object_ids": ["obj"]}) == 1
    projection.rebuild_knowledge_object_views.assert_awaited_once()
    world.process.assert_awaited_once()
    watch.spawn_for_world_change.assert_not_awaited()
