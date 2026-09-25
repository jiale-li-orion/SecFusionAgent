from fastapi import FastAPI

from packages.shared.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="SecFusionAgent", version="0.1.0")

    @app.get("/health/live", tags=["health"])
    async def liveness() -> dict[str, str]:
        return {"status": "ok", "environment": settings.environment}

    return app


app = create_app()
