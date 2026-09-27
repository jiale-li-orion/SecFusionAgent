from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, status
from pydantic import BaseModel, Field
from sqlalchemy import inspect, text

from apps.api.dependencies import SessionDep
from packages.shared.config import get_settings

router = APIRouter(tags=["health"])


class HealthComponent(BaseModel):
    component: str
    status: str
    checked_at: datetime
    detail_code: str | None = None


class HealthView(BaseModel):
    overall: str
    components: list[HealthComponent] = Field(default_factory=list)


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok", "environment": get_settings().environment}


@router.get("/health/ready")
async def readiness(session: SessionDep) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    connection = await session.connection()
    table_names = set(await connection.run_sync(lambda conn: inspect(conn).get_table_names()))
    required = {"objects", "investigation_cases", "task_runs"}
    missing = sorted(required - table_names)
    if missing:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"required database schema missing: {','.join(missing)}",
        )
    settings = get_settings()
    if not settings.runtime_policy_path.exists():
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="runtime policy configuration missing",
        )
    return {"status": "ready"}


@router.get("/health", response_model=HealthView)
async def aggregate_health(session: SessionDep) -> HealthView:
    now = datetime.now(UTC)
    components: list[HealthComponent] = []
    try:
        await session.execute(text("SELECT 1"))
        components.append(HealthComponent(component="postgresql", status="healthy", checked_at=now))
    except Exception:
        components.append(
            HealthComponent(
                component="postgresql",
                status="unhealthy",
                checked_at=now,
                detail_code="database_unavailable",
            )
        )
    settings = get_settings()
    components.append(
        HealthComponent(
            component="model_provider",
            status="healthy" if settings.model_base_url and settings.model_name else "disabled",
            checked_at=now,
            detail_code=(
                None if settings.model_base_url and settings.model_name else "not_configured"
            ),
        )
    )
    if any(item.status == "unhealthy" for item in components):
        overall = "unhealthy"
    elif any(item.status in {"degraded", "disabled"} for item in components):
        overall = "degraded"
    else:
        overall = "healthy"
    return HealthView(overall=overall, components=components)
