from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from packages.intelligence.storage import document_models as document_models
from packages.intelligence.storage import evidence_models as evidence_models
from packages.intelligence.storage import incident_models as incident_models
from packages.intelligence.storage import knowledge_models as knowledge_models
from packages.intelligence.storage import models as intelligence_models  # noqa: F401
from packages.intelligence.storage import projection_models as projection_models
from packages.investigation.storage import models as investigation_models  # noqa: F401
from packages.monitoring.storage import models as monitoring_models  # noqa: F401
from packages.shared.config import get_settings
from packages.shared.db import Base
from packages.shared.storage import models as shared_models  # noqa: F401
from packages.sources.storage import models as source_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: object) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    import asyncio

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
