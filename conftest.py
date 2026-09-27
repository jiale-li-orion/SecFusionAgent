"""Repository-wide pytest bootstrap for deterministic SQLAlchemy model registration."""

from apps.runtime_models import register_runtime_models


def pytest_configure() -> None:
    register_runtime_models()
