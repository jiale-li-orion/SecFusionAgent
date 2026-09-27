from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from packages.enrichment.runtime.post_ingress import ObservationProcessingRuntime
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.storage.factory import create_s3_artifact_store
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

SOURCE_ID = "shodan-internetdb-assets"


def _stable_run_id(case_key: str, observed_at: str, ip: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"secfusion:asset-seed:{case_key}:{observed_at}:{ip}"))


async def _run(path: Path) -> None:
    seed_text = await asyncio.to_thread(path.read_text)
    seed = json.loads(seed_text)
    if seed.get("status") != "pre-schema-asset-seed":
        raise ValueError("asset seed must be marked pre-schema-asset-seed")
    raw = seed.get("raw_result")
    provider = seed.get("provider")
    normalized = seed.get("normalized_candidate")
    discovery = seed.get("discovery_target")
    relation = seed.get("relation_to_case")
    if not all(isinstance(item, dict) for item in (raw, provider, normalized, discovery, relation)):
        raise ValueError("asset seed is missing required structured sections")
    assert isinstance(raw, dict)
    assert isinstance(provider, dict)
    assert isinstance(normalized, dict)
    assert isinstance(discovery, dict)
    assert isinstance(relation, dict)

    ip = raw.get("ip")
    ports = raw.get("ports")
    observed_at_raw = seed.get("observed_at")
    case_key = seed.get("case_key")
    if not isinstance(ip, str) or not isinstance(ports, list) or not ports:
        raise ValueError("asset seed requires raw_result.ip and non-empty ports")
    if not isinstance(observed_at_raw, str) or not isinstance(case_key, str):
        raise ValueError("asset seed requires observed_at and case_key")
    if len(ports) != 1 or not isinstance(ports[0], int):
        raise ValueError("current curated asset-seed importer requires exactly one integer port")
    observed_at = datetime.fromisoformat(observed_at_raw.replace("Z", "+00:00"))
    port = ports[0]

    settings = get_settings()
    definitions = load_source_definitions(Path(settings.source_registry_path))
    sources = {item.source_id: item for item in definitions}
    source = sources[SOURCE_ID]
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    store = create_s3_artifact_store(settings)
    await store.ensure_bucket()
    run_id = _stable_run_id(case_key, observed_at_raw, ip)
    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, definitions)
            run = await session.get(AcquisitionRunModel, run_id)
            if run is None:
                session.add(
                    AcquisitionRunModel(
                        run_id=run_id,
                        source_id=source.source_id,
                        trigger=AcquisitionTrigger.INVESTIGATION.value,
                        parent_run_id=None,
                        query_spec={
                            "filters": {
                                "ip": ip,
                                "discovery_context": discovery,
                                "relation_context": relation,
                            }
                        },
                        status="success",
                        cursor_in={},
                        cursor_out={"result_count": 1, "curated_seed": True},
                        attempt=1,
                        created_at=observed_at,
                        started_at=observed_at,
                        finished_at=observed_at,
                    )
                )

        payload: dict[str, object] = {
            "ip": ip,
            "port": port,
            "transport": normalized.get("transport") or "tcp",
            "hostnames": raw.get("hostnames") if isinstance(raw.get("hostnames"), list) else [],
            "domains": [],
            # Product/version in the seed are analyst-normalized candidates rather
            # than InternetDB provider fields. Keep provider payload neutral and
            # preserve the candidate separately in request metadata.
            "product": None,
            "version": None,
            "org": None,
            "isp": None,
            "asn": None,
            "cpe": raw.get("cpes") if isinstance(raw.get("cpes"), list) else [],
            "tags": raw.get("tags") if isinstance(raw.get("tags"), list) else [],
            "vulns": raw.get("vulns") if isinstance(raw.get("vulns"), list) else [],
            "location": {},
            "raw_provider_record": raw,
        }
        endpoint = provider.get("endpoint")
        query = provider.get("query")
        if not isinstance(endpoint, str) or not isinstance(query, str):
            raise ValueError("asset seed provider requires endpoint and query")
        envelope = IngestEnvelope.for_json_payload(
            acquisition_run_id=run_id,
            trigger=AcquisitionTrigger.INVESTIGATION,
            source_id=source.source_id,
            external_object_id=f"{ip}:{port}/{payload['transport']}",
            payload=payload,
            canonical_url=endpoint,
            published_at=None,
            updated_at=observed_at,
            external_revision=observed_at.isoformat(),
            request_metadata={
                "provider": "shodan-internetdb",
                "query": query,
                "passive_observation": True,
                "curated_seed": True,
                "case_key": case_key,
                "discovery_context": discovery,
                "relation_context": relation,
                "normalized_candidate": normalized,
            },
            observed_at=observed_at,
        )
        async with factory() as session, session.begin():
            ack = await EvidenceIngress(store).accept(session, source, envelope)
        runtime = ObservationProcessingRuntime(store)
        async with factory() as session, session.begin():
            result = await runtime.process(session, source, ack.observation_id)
        print(result.model_dump_json(indent=2))
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a curated passive Internet-asset seed")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    asyncio.run(_run(args.path.resolve()))


if __name__ == "__main__":
    main()
