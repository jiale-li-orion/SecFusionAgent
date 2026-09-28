from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

from apps.runtime_models import register_runtime_models
from packages.enrichment.processors.csaf_vex import RedHatCSAFVEXMapper
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.knowledge.read import get_vulnerability_by_cve
from packages.intelligence.knowledge.write import EvidenceBackedKnowledgeWriter
from packages.intelligence.normalization.cvelist_v5_durable import CVEListV5CanonicalNormalizer
from packages.intelligence.storage.factory import create_s3_artifact_store
from packages.monitoring.acquisition.service import AcquisitionService
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.sources.adapters.factory import create_source_adapter
from packages.sources.contracts import AcquisitionTrigger, QuerySpec, SourceDefinition
from packages.sources.errors import SourceFetchFailed, SourceRateLimited
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

SOURCE_ID = "redhat-csaf-vex"
IDENTITY_SOURCE_ID = "cve-program-cvelist-v5"


async def _query_with_retry(
    acquisition: AcquisitionService,
    source: SourceDefinition,
    adapter: Any,
    cve_id: str,
):
    for attempt in range(5):
        try:
            return await acquisition.query(
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
    raise RuntimeError(f"provider retry loop produced no result for {cve_id}")


async def _run(cves: list[str]) -> dict[str, Any]:
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    definitions = load_source_definitions(Path(settings.source_registry_path))
    sources = {item.source_id: item for item in definitions}
    source = sources[SOURCE_ID]
    identity_source = sources[IDENTITY_SOURCE_ID]
    store = create_s3_artifact_store(settings)
    await store.ensure_bucket()
    ingress = EvidenceIngress(store)
    acquisition = AcquisitionService(factory)
    writer = EvidenceBackedKnowledgeWriter()
    mapper = RedHatCSAFVEXMapper()
    output: dict[str, Any] = {"source_id": SOURCE_ID, "cases": {}}
    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, definitions)
        async with httpx.AsyncClient(timeout=45.0) as client:
            adapter = create_source_adapter(source, client, settings)
            identity_adapter = create_source_adapter(identity_source, client, settings)
            for cve_id in cves:
                async with factory() as session:
                    view = await get_vulnerability_by_cve(session, cve_id)
                identity_revision = None
                if view is None:
                    identity_envelopes = await _query_with_retry(
                        acquisition,
                        identity_source,
                        identity_adapter,
                        cve_id,
                    )
                    for envelope in identity_envelopes:
                        async with factory() as session, session.begin():
                            ack = await ingress.accept(session, identity_source, envelope)
                            result = await CVEListV5CanonicalNormalizer().normalize(
                                session,
                                identity_source,
                                envelope,
                                ack,
                            )
                        identity_revision = result.knowledge_revision
                    async with factory() as session:
                        view = await get_vulnerability_by_cve(session, cve_id)
                if view is None:
                    raise RuntimeError(f"canonical vulnerability unavailable for {cve_id}")

                envelopes = await _query_with_retry(acquisition, source, adapter, cve_id)
                revisions: list[int] = []
                observations: list[str] = []
                for envelope in envelopes:
                    candidate = mapper.map(envelope)
                    async with factory() as session, session.begin():
                        ack = await ingress.accept(session, source, envelope)
                        result = await writer.apply(
                            session,
                            root_object_id=view.object_id,
                            source=source,
                            observation=ack,
                            candidate=candidate,
                            processor_name=mapper.PROCESSOR_NAME,
                            processor_version=mapper.PROCESSOR_VERSION,
                        )
                    observations.append(ack.observation_id)
                    revisions.append(result.knowledge_revision)
                output["cases"][cve_id] = {
                    "identity_revision": identity_revision,
                    "observation_count": len(envelopes),
                    "observation_ids": observations,
                    "knowledge_revisions": revisions,
                }
    finally:
        await engine.dispose()
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh Red Hat CSAF/VEX product status")
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
