from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SECFUSION_", extra="ignore")

    environment: str = "dev"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://secfusion:secfusion@localhost:5432/secfusion"
    redis_broker_url: str = "redis://localhost:6379/0"
    redis_hot_cache_url: str = "redis://localhost:6380/0"
    hot_cache_ttl_seconds: int = 30 * 24 * 60 * 60
    incident_signal_ttl_seconds: int = 7 * 24 * 60 * 60
    source_registry_path: Path = Path("config/sources")
    collection_run_timeout_seconds: int = 15 * 60
    scheduler_tick_seconds: int = 5

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "secfusion"
    s3_secret_key: str = "change-me"
    s3_bucket: str = "secfusion-evidence"
    s3_region: str = "us-east-1"

    nvd_api_key: str | None = None
    github_token: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
