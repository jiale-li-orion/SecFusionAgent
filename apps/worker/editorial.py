"""Public editorial worker bootstrap; durable retry state belongs to M6."""

import asyncio
import logging
from datetime import UTC, datetime

import httpx

from apps.application.automatic_editorial import execute_editorial
from apps.model_runtime import create_recorded_model_provider
from apps.worker.celery_app import celery_app
from packages.reasoning.briefing import BriefingGenerator
from packages.reasoning.editorial import claim_run, finish_run
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory

logger = logging.getLogger(__name__)


async def run_editorial(run_id: str) -> str:
    settings = get_settings()
    if not settings.background_llm_enabled or not settings.editorial_enabled:
        return "disabled"
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    token = None
    try:
        async with factory() as session, session.begin():
            token = await claim_run(session, run_id, now=datetime.now(UTC))
        if token is None:
            return "not_claimed"
        async with httpx.AsyncClient(timeout=settings.model_timeout_seconds) as client:
            provider = create_recorded_model_provider(settings, factory, client)
            if provider is None:
                raise ValueError("editorial model provider is not configured")
            return await asyncio.wait_for(
                execute_editorial(factory, BriefingGenerator(provider), settings, run_id, token),
                timeout=840,
            )
    except Exception as exc:
        # Details remain in recorded model calls; no source content or credentials in job logs.
        if token:
            async with factory() as session, session.begin():
                await finish_run(
                    session,
                    run_id,
                    token,
                    status="failed" if isinstance(exc, ValueError) else "retry",
                    now=datetime.now(UTC),
                    error=str(exc)[:300] if type(exc) is ValueError else type(exc).__name__,
                )
        logger.warning("editorial run failed run_id=%s error_type=%s", run_id, type(exc).__name__)
        return "failed"
    finally:
        await engine.dispose()


@celery_app.task(name="secfusion.editorial.run", soft_time_limit=870, time_limit=900)
def editorial_run(run_id: str) -> str:
    return asyncio.run(run_editorial(run_id))
