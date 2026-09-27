from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

from apps.runtime_models import register_runtime_models
from packages.enrichment.planner import EnrichmentJobSpec, VulnerabilityEnrichmentPlanner
from packages.enrichment.service import VulnerabilityEnrichmentService
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.knowledge.read import get_vulnerability_by_cve
from packages.intelligence.knowledge.write import EvidenceBackedKnowledgeWriter
from packages.intelligence.normalization.nvd_durable import NVDCanonicalNormalizer
from packages.intelligence.storage.factory import create_s3_artifact_store
from packages.monitoring.acquisition.service import AcquisitionService
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.sources.adapters.factory import create_source_adapter
from packages.sources.contracts import AcquisitionTrigger, QuerySpec
from packages.sources.errors import SourceFetchFailed, SourceRateLimited
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

DEFAULT_CVES = (
    "CVE-2025-47828",
    "CVE-2024-13980",
    "CVE-2024-13981",
    "CVE-2024-13984",
    "CVE-2024-13985",
    "CVE-2026-48746",
)
PROVIDER_IDS = (
    "first-epss",
    "github-global-advisories",
    "osv-vulnerabilities",
    "cisa-kev",
)


async def _run(
    cves: list[str],
    *,
    refresh_nvd: bool = True,
    provider_ids: tuple[str, ...] = PROVIDER_IDS,
) -> dict[str, Any]:
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    definitions = load_source_definitions(Path(settings.source_registry_path))
    sources = {item.source_id: item for item in definitions}
    async with factory() as session, session.begin():
        await sync_source_definitions(session, definitions)
    nvd = sources["nvd-cves-2"]
    artifact_store = create_s3_artifact_store(settings)
    await artifact_store.ensure_bucket()
    ingress = EvidenceIngress(artifact_store)
    acquisition = AcquisitionService(factory)
    writer = EvidenceBackedKnowledgeWriter()
    output: dict[str, Any] = {"cases": {}}
    nvd_interval_seconds = 0.7 if settings.nvd_api_key else 6.5
    next_nvd_request_at = 0.0

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            required_source_ids = tuple(
                dict.fromkeys(((nvd.source_id,) if refresh_nvd else ()) + provider_ids)
            )
            adapters = {
                source_id: create_source_adapter(sources[source_id], client, settings)
                for source_id in required_source_ids
            }
            provider_service = VulnerabilityEnrichmentService(
                factory,
                acquisition,
                ingress,
                writer,
                planner=VulnerabilityEnrichmentPlanner(),
                sources=sources,
                adapters=adapters,
            )

            async def query_nvd(cve_id: str):
                nonlocal next_nvd_request_at
                loop = asyncio.get_running_loop()
                for attempt in range(6):
                    wait_seconds = max(0.0, next_nvd_request_at - loop.time())
                    if wait_seconds:
                        await asyncio.sleep(wait_seconds)
                    next_nvd_request_at = loop.time() + nvd_interval_seconds
                    try:
                        return await acquisition.query(
                            nvd,
                            adapters[nvd.source_id],
                            QuerySpec(filters={"cve_id": cve_id}),
                            parent_run_id=None,
                            trigger=AcquisitionTrigger.ON_DEMAND,
                        )
                    except (SourceRateLimited, SourceFetchFailed):
                        if attempt == 5:
                            raise
                        next_nvd_request_at = max(
                            next_nvd_request_at,
                            loop.time() + nvd_interval_seconds,
                        )
                raise RuntimeError("unreachable NVD retry loop")

            for raw_cve in cves:
                cve_id = raw_cve.upper()
                case: dict[str, Any] = {
                    "nvd_normalizations": 0,
                    "provider_results": {},
                }
                if refresh_nvd:
                    nvd_envelopes = await query_nvd(cve_id)
                    for envelope in nvd_envelopes:
                        async with factory() as session, session.begin():
                            observation = await ingress.accept(session, nvd, envelope)
                            result = await NVDCanonicalNormalizer().normalize(
                                session,
                                nvd,
                                envelope,
                                observation,
                            )
                        case["nvd_normalizations"] += 1
                        case["nvd_knowledge_revision"] = result.knowledge_revision

                async with factory() as session:
                    view = await get_vulnerability_by_cve(session, cve_id)
                if view is None:
                    case["error"] = "canonical vulnerability missing after NVD refresh"
                    output["cases"][cve_id] = case
                    continue

                for source_id in provider_ids:
                    job = EnrichmentJobSpec(
                        source_id=source_id,
                        query=QuerySpec(filters={"cve_id": cve_id}),
                    )
                    try:
                        results = await provider_service.execute_job(
                            cve_id,
                            job,
                            view=view,
                        )
                    except Exception as exc:  # keep cross-provider refresh best-effort
                        case["provider_results"][source_id] = {
                            "status": "error",
                            "error_type": type(exc).__name__,
                            "detail": str(exc)[:1000],
                        }
                    else:
                        case["provider_results"][source_id] = {
                            "status": "ok",
                            "result_count": len(results),
                            "knowledge_revisions": [item.knowledge_revision for item in results],
                        }
                output["cases"][cve_id] = case
    finally:
        await engine.dispose()
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-run deterministic structured enrichment for selected real CVEs"
    )
    parser.add_argument("cves", nargs="*", default=list(DEFAULT_CVES))
    parser.add_argument("--skip-nvd", action="store_true")
    parser.add_argument(
        "--provider",
        action="append",
        choices=PROVIDER_IDS,
        dest="providers",
        help="Refresh only selected structured provider(s); repeat for multiple providers",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    providers = tuple(args.providers) if args.providers else PROVIDER_IDS
    result = asyncio.run(
        _run(
            [item.upper() for item in args.cves],
            refresh_nvd=not args.skip_nvd,
            provider_ids=providers,
        )
    )
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
