from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from apps.evaluation_runtime import ensure_benchmark_deployment_revision
from apps.runtime_models import register_runtime_models
from packages.evaluation.benchmark.storage import DeploymentRevisionModel
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory


async def _freeze() -> dict[str, object]:
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session, session.begin():
            deployment_id = await ensure_benchmark_deployment_revision(session, settings)
            model = await session.get(DeploymentRevisionModel, deployment_id)
            if model is None:
                raise RuntimeError("frozen deployment revision disappeared")
            return {
                "deployment_revision_id": model.deployment_revision_id,
                "git_commit": model.git_commit,
                "schema_revision": model.schema_revision,
                "source_inventory_hash": model.source_inventory_hash,
                "vocabulary_revision": model.vocabulary_revision,
                "policy_revision": model.policy_revision,
                "capability_registry_revision": model.capability_registry_revision,
                "skill_registry_revision": model.skill_registry_revision,
                "model_provider_revision": model.model_provider_revision,
                "configuration_digest": model.configuration_digest,
                "created_at": model.created_at.isoformat(),
            }
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Freeze one DeploymentRevision for a formal benchmark batch"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = asyncio.run(_freeze())
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
