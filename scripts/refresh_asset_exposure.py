from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

from apps.runtime_models import register_runtime_models
from packages.enrichment.runtime.post_ingress import ObservationProcessingRuntime
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.storage.factory import create_artifact_store
from packages.monitoring.acquisition.service import AcquisitionService
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.sources.adapters.factory import create_source_adapter
from packages.sources.contracts import AcquisitionTrigger, QuerySpec
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

SOURCE_ID = "shodan-internetdb-assets"


async def _run(ips: list[str]) -> dict[str, Any]:
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    definitions = load_source_definitions(Path(settings.source_registry_path))
    sources = {item.source_id: item for item in definitions}
    source = sources[SOURCE_ID]
    store = create_artifact_store(settings)
    await store.ensure_bucket()
    ingress = EvidenceIngress(store)
    acquisition = AcquisitionService(factory)
    runtime = ObservationProcessingRuntime(store, source_definitions=sources)
    output: dict[str, Any] = {"source_id": SOURCE_ID, "cases": {}}
    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, definitions)
        async with httpx.AsyncClient(timeout=30.0) as client:
            adapter = create_source_adapter(source, client, settings)
            for ip in ips:
                envelopes = await acquisition.query(
                    source,
                    adapter,
                    QuerySpec(filters={"ip": ip}),
                    parent_run_id=None,
                    trigger=AcquisitionTrigger.ON_DEMAND,
                )
                case_results: list[dict[str, Any]] = []
                for envelope in envelopes:
                    async with factory() as session, session.begin():
                        ack = await ingress.accept(session, source, envelope)
                    async with factory() as session, session.begin():
                        result = await runtime.process(session, source, ack.observation_id)
                    case_results.append(result.model_dump(mode="json"))
                output["cases"][ip] = {
                    "observation_count": len(envelopes),
                    "results": case_results,
                }
    finally:
        await engine.dispose()
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh explicit Shodan InternetDB asset-vulnerability associations"
    )
    parser.add_argument("ips", nargs="+")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = asyncio.run(_run(args.ips))
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
