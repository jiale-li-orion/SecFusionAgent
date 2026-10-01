from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

from apps.runtime_models import register_runtime_models
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.normalization.cvelist_v5_durable import CVEListV5CanonicalNormalizer
from packages.intelligence.storage.factory import create_artifact_store
from packages.monitoring.acquisition.service import AcquisitionService
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.sources.adapters.factory import create_source_adapter
from packages.sources.contracts import AcquisitionTrigger, QuerySpec
from packages.sources.errors import SourceFetchFailed, SourceRateLimited
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

SOURCE_ID = "cve-program-cvelist-v5"


async def _run(cves: list[str]) -> dict[str, Any]:
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
    output: dict[str, Any] = {"source_id": SOURCE_ID, "cases": {}}
    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, definitions)
        async with httpx.AsyncClient(timeout=30.0) as client:
            adapter = create_source_adapter(source, client, settings)
            for cve_id in cves:
                envelopes = None
                for attempt in range(5):
                    try:
                        envelopes = await acquisition.query(
                            source,
                            adapter,
                            QuerySpec(filters={"cve_id": cve_id}),
                            parent_run_id=None,
                            trigger=AcquisitionTrigger.ON_DEMAND,
                        )
                    except (SourceFetchFailed, SourceRateLimited):
                        if attempt == 4:
                            raise
                        await asyncio.sleep(2**attempt)
                    else:
                        break
                if envelopes is None:
                    raise RuntimeError(f"CVE5 retry loop produced no response for {cve_id}")
                revisions: list[int] = []
                observations: list[str] = []
                for envelope in envelopes:
                    async with factory() as session, session.begin():
                        ack = await ingress.accept(session, source, envelope)
                        result = await CVEListV5CanonicalNormalizer().normalize(
                            session,
                            source,
                            envelope,
                            ack,
                        )
                    observations.append(ack.observation_id)
                    revisions.append(result.knowledge_revision)
                output["cases"][cve_id] = {
                    "observation_count": len(envelopes),
                    "observation_ids": observations,
                    "knowledge_revisions": revisions,
                }
    finally:
        await engine.dispose()
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh deterministic CVE 5.x applicability")
    parser.add_argument("cves", nargs="+")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = asyncio.run(_run([item.upper() for item in args.cves]))
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
