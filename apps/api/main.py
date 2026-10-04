from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from apps.api.errors import install_error_handlers
from apps.api.routes.a2a import router as a2a_router
from apps.api.routes.agents import router as agents_router
from apps.api.routes.decisions import router as decisions_router
from apps.api.routes.evidence import router as evidence_router
from apps.api.routes.health import router as health_router
from apps.api.routes.investigations import router as investigations_router
from apps.api.routes.knowledge import router as knowledge_router
from apps.api.routes.observatory import router as observatory_router
from apps.api.routes.questions import router as questions_router
from apps.api.routes.world import router as world_router
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

    app = FastAPI(
        title="SecFusionAgent",
        version="0.1.0",
        lifespan=lifespan,
        openapi_tags=[
            {"name": "agents", "description": "Product-safe Agent runtime and Task reads."},
            {"name": "knowledge", "description": "Stable current-world intelligence reads."},
            {"name": "observatory", "description": "Live operational and frozen evaluation proof reads."},
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
        return response

    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(a2a_router)
    app.include_router(agents_router)
    app.include_router(investigations_router)
    app.include_router(decisions_router)
    app.include_router(evidence_router)
    app.include_router(questions_router)
    app.include_router(knowledge_router)
    app.include_router(world_router)
    app.include_router(observatory_router)
    product_web_root = Path("apps/web/dist")
    if product_web_root.is_dir():
        app.mount(
            "/product",
            StaticFiles(directory=product_web_root, html=True),
            name="product-web",
        )

    return app


app = create_app()
