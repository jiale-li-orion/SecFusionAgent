from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.api.routes.knowledge import router as knowledge_router
from apps.runtime_models import register_runtime_models
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory


def create_app() -> FastAPI:
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.session_factory = create_session_factory(engine)
        yield
        await engine.dispose()

    app = FastAPI(title="SecFusionAgent", version="0.1.0", lifespan=lifespan)
    app.include_router(knowledge_router)

    @app.get("/health/live", tags=["health"])
    async def liveness() -> dict[str, str]:
        return {"status": "ok", "environment": settings.environment}

    return app


app = create_app()
