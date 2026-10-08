from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SECFUSION_", extra="ignore")

    environment: str = "dev"
    log_level: str = "INFO"
    auth_allowed_origins: list[str] = Field(default_factory=list)
    auth_session_ttl_seconds: int = Field(default=7 * 24 * 60 * 60, ge=60, le=30 * 24 * 60 * 60)

    database_url: str = "postgresql+asyncpg://secfusion:secfusion@localhost:5432/secfusion"
    redis_broker_url: str = "redis://localhost:6379/0"
    redis_hot_cache_url: str = "redis://localhost:6380/0"
    redis_task_bus_url: str = "redis://localhost:6381/0"
    task_event_stream_name: str = "secfusion:task-events"
    task_event_scheduler_group: str = "secfusion-task-scheduler"
    task_event_claim_idle_ms: int = 30_000
    hot_cache_ttl_seconds: int = 30 * 24 * 60 * 60
    incident_signal_ttl_seconds: int = 7 * 24 * 60 * 60
    source_registry_path: Path = Path("config/sources")
    runtime_policy_path: Path = Path("config/runtime-policy.json")
    collection_run_timeout_seconds: int = 15 * 60
    scheduler_tick_seconds: int = 5
    upstream_http_proxy: str | None = None
    source_proxy_ids: list[str] = Field(
        default_factory=lambda: [
            "cve-program-cvelist-v5",
            "mitre-atlas",
            "meta-ai-safety",
            "github-target-repos",
            "bleepingcomputer-news",
            "slowmist-reports",
        ]
    )

    artifact_store_backend: Literal["filesystem", "s3"] = "filesystem"
    artifact_root: Path = Path(".local/secfusion-artifacts")
    s3_endpoint_url: str = "http://localhost:4566"
    s3_access_key: str = "secfusion"
    s3_secret_key: str = "change-me"
    s3_bucket: str = "secfusion-evidence"
    runtime_artifact_bucket: str = "secfusion-runtime-artifacts"
    s3_region: str = "us-east-1"

    nvd_api_key: str | None = None
    github_token: str | None = None
    shodan_api_key: str | None = None
    x_bearer_token: str | None = None
    censys_pat: str | None = None
    censys_organization_id: str | None = None
    fofa_api_key: str | None = None
    zoomeye_api_key: str | None = None
    semantic_scholar_api_key: str | None = None

    model_base_url: str | None = None
    model_api_key: str | None = None
    model_name: str | None = None
    embedding_model_name: str | None = None
    embedding_dimensions: int | None = None
    model_max_tokens: int | None = None
    model_token_reservation_per_attempt: int = Field(default=32768, ge=1)
    model_temperature: float | None = 0.0
    model_reasoning_effort: Literal["low", "high", "max"] | None = None
    model_response_format: Literal["auto", "json_schema", "json_object"] = "auto"
    model_timeout_seconds: float = 60.0
    model_max_attempts: int = Field(default=3, ge=1)
    model_retry_base_seconds: float = 0.5
    model_retry_max_seconds: float = 4.0


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
