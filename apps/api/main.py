import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request

from apps.api.errors import install_error_handlers
from apps.api.product_web import ProductStaticFiles
from apps.api.routes.a2a import router as a2a_router
from apps.api.routes.agents import router as agents_router
from apps.api.routes.authentication import router as authentication_router
from apps.api.routes.decisions import router as decisions_router
from apps.api.routes.enrichment import router as enrichment_router
from apps.api.routes.evidence import router as evidence_router
from apps.api.routes.health import router as health_router
from apps.api.routes.incidents import router as incidents_router
from apps.api.routes.investigations import router as investigations_router
from apps.api.routes.knowledge import router as knowledge_router
from apps.api.routes.observatory import router as observatory_router
from apps.api.routes.questions import router as questions_router
from apps.api.routes.recommendations import router as recommendations_router
from apps.api.routes.world import router as world_router
from apps.application.queries.world_reader import WorldStoryReader
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
        app.state.world_story_reader = WorldStoryReader(app.state.session_factory)
        try:
            # Pay the bounded cold ORM/read cost before accepting the first Product request.
            await asyncio.wait_for(app.state.world_story_reader.warm(), timeout=5)
        except TimeoutError:
            logging.getLogger(__name__).warning("WORLD warm read timed out; HTTP reads can retry")
        try:
            yield
        finally:
            await app.state.world_story_reader.close()
            await engine.dispose()

    app = FastAPI(
        title="SecFusionAgent",
        version="0.1.0",
        lifespan=lifespan,
        openapi_tags=[
            {"name": "agents", "description": "Product-safe Agent runtime and Task reads."},
            {"name": "knowledge", "description": "Stable current-world intelligence reads."},
            {"name": "incidents", "description": "Durable incident timeline and source reads."},
            {
                "name": "observatory",
                "description": "Live operational health and evaluation measurements.",
            },
            {"name": "evidence", "description": "Product-safe Evidence traceability reads."},
            {
                "name": "investigations",
                "description": "Product investigation lifecycle and stable read models.",
            },
            {
                "name": "questions",
                "description": "Product QA routing across synchronous decision and investigations.",
            },
            {"name": "health", "description": "Process and dependency health."},
            {"name": "a2a", "description": "A2A interoperability adapter."},
        ],
    )

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        request.state.request_started_at = datetime.now(UTC)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        if request.url.path.startswith("/api/v1/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(authentication_router)
    app.include_router(a2a_router)
    app.include_router(agents_router)
    app.include_router(investigations_router)
    app.include_router(incidents_router)
    app.include_router(decisions_router)
    app.include_router(evidence_router)
    app.include_router(questions_router)
    app.include_router(knowledge_router)
    app.include_router(recommendations_router)
    app.include_router(enrichment_router)
    app.include_router(world_router)
    app.include_router(observatory_router)
    product_web_root = Path("apps/web/dist")
    if product_web_root.is_dir():
        app.mount(
            "/product",
            ProductStaticFiles(directory=product_web_root, html=True),
            name="product-web",
        )

    return app


app = create_app()
