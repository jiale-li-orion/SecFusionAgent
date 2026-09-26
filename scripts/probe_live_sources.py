from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from uuid import uuid4

import httpx

from packages.shared.config import get_settings
from packages.sources.adapters.arxiv import ArxivAdapter
from packages.sources.adapters.cisa_kev import CISAKEVAdapter
from packages.sources.adapters.cnnvd import CNNVDAdapter
from packages.sources.adapters.cvelist_v5 import CVEListV5Adapter
from packages.sources.adapters.direct_document import DirectDocumentAdapter
from packages.sources.adapters.github_advisory import GitHubGlobalAdvisoryAdapter
from packages.sources.adapters.github_repo import GitHubRepoAdapter
from packages.sources.adapters.html_incident import HTMLIncidentAdapter
from packages.sources.adapters.html_index import HTMLIndexAdapter
from packages.sources.adapters.internet_asset import (
    CensysAssetAdapter,
    FOFAAssetAdapter,
    ZoomEyeAssetAdapter,
)
from packages.sources.adapters.nvd import NVDAdapter
from packages.sources.adapters.oscs import OSCSAdapter
from packages.sources.adapters.oss_security import OssSecurityAdapter
from packages.sources.adapters.osv import OSVAdapter
from packages.sources.adapters.rss_incident import RSSIncidentAdapter
from packages.sources.adapters.scholarly_search import ScholarlySearchAdapter
from packages.sources.adapters.shodan import ShodanAdapter
from packages.sources.adapters.slowmist_hacked import SlowMistHackedAdapter
from packages.sources.adapters.x_user_signal import XUserSignalAdapter
from packages.sources.contracts import (
    AcquisitionTrigger,
    QuerySpec,
    SourceDefinition,
    SourceState,
)
from packages.sources.probe import Probe, run_live_probe
from packages.sources.registry.loader import load_source_definitions


def _source_map() -> dict[str, SourceDefinition]:
    return {item.source_id: item for item in load_source_definitions(Path("config/sources"))}


async def _main(*, strict: bool, json_output: bool) -> int:
    settings = get_settings()
    sources = _source_map()
    headers = {
        "User-Agent": "SecFusionAgent/0.1 (+security-intelligence-source-probe)",
        "Accept": "*/*",
    }
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True, headers=headers) as client:
        cvelist = CVEListV5Adapter(client)
        cnnvd = CNNVDAdapter(client)
        nvd = NVDAdapter(client, api_key=settings.nvd_api_key)
        oscs = OSCSAdapter(client)
        oss_security = OssSecurityAdapter(client)
        osv = OSVAdapter(client)
        github_advisory = GitHubGlobalAdvisoryAdapter(client, token=settings.github_token)
        github_repo = GitHubRepoAdapter(client, token=settings.github_token)
        cisa = CISAKEVAdapter(client)
        direct_document = DirectDocumentAdapter(client)
        scholarly = ScholarlySearchAdapter(
            client, semantic_scholar_api_key=settings.semantic_scholar_api_key
        )
        rss = RSSIncidentAdapter(client)
        html_incident = HTMLIncidentAdapter(client)
        html_index = HTMLIndexAdapter(client)
        arxiv = ArxivAdapter(client)
        shodan = ShodanAdapter(client, api_key=settings.shodan_api_key)
        slowmist_hacked = SlowMistHackedAdapter(client)
        x_signal = XUserSignalAdapter(client, bearer_token=settings.x_bearer_token)
        censys = CensysAssetAdapter(
            client,
            pat=settings.censys_pat,
            organization_id=settings.censys_organization_id,
        )
        fofa = FOFAAssetAdapter(client, api_key=settings.fofa_api_key)
        zoomeye = ZoomEyeAssetAdapter(client, api_key=settings.zoomeye_api_key)

        async def discover_rss() -> tuple[int, str | None]:
            batch = await rss.discover(sources["bleepingcomputer-news"], SourceState())
            sample = batch.items[0].external_object_id if batch.items else None
            return len(batch.items), sample

        async def discover_oss_security() -> tuple[int, str | None]:
            batch = await oss_security.discover(sources["oss-security"], SourceState())
            if batch.items:
                await oss_security.fetch(
                    sources["oss-security"],
                    batch.items[0],
                    acquisition_run_id=str(uuid4()),
                    trigger=AcquisitionTrigger.ON_DEMAND,
                )
            sample = batch.items[0].external_object_id if batch.items else None
            return len(batch.items), sample

        async def discover_blockbeats() -> tuple[int, str | None]:
            batch = await html_incident.discover(sources["blockbeats-newsflash"], SourceState())
            sample = batch.items[0].external_object_id if batch.items else None
            return len(batch.items), sample

        async def discover_foresight() -> tuple[int, str | None]:
            batch = await html_incident.discover(sources["foresight-timeline"], SourceState())
            sample = batch.items[0].external_object_id if batch.items else None
            return len(batch.items), sample

        async def discover_slowmist_hacked() -> tuple[int, str | None]:
            batch = await slowmist_hacked.discover(sources["slowmist-hacked"], SourceState())
            if batch.items:
                await slowmist_hacked.fetch(
                    sources["slowmist-hacked"],
                    batch.items[0],
                    acquisition_run_id=str(uuid4()),
                    trigger=AcquisitionTrigger.ON_DEMAND,
                )
            sample = batch.items[0].external_object_id if batch.items else None
            return len(batch.items), sample

        async def discover_x(source_id: str) -> tuple[int, str | None]:
            batch = await x_signal.discover(sources[source_id], SourceState())
            sample = batch.items[0].external_object_id if batch.items else None
            return len(batch.items), sample

        async def discover_html_incident(source_id: str) -> tuple[int, str | None]:
            batch = await html_incident.discover(sources[source_id], SourceState())
            sample = batch.items[0].external_object_id if batch.items else None
            return len(batch.items), sample

        async def probe_html_managed(source_id: str) -> tuple[int, str | None]:
            source = sources[source_id]
            method = dict(source.discovery_method)
            configured_max = method.get("max_items", 3)
            max_items = configured_max if isinstance(configured_max, int) else 3
            method["max_items"] = min(max_items, 3)
            probe_source = source.model_copy(update={"discovery_method": method})
            batch = await html_index.discover(probe_source, SourceState())
            if batch.items:
                await html_index.fetch(
                    probe_source,
                    batch.items[0],
                    acquisition_run_id=str(uuid4()),
                    trigger=AcquisitionTrigger.ON_DEMAND,
                )
            sample = batch.items[0].external_object_id if batch.items else None
            return len(batch.items), sample

        async def probe_direct_document(source_id: str) -> tuple[int, str | None]:
            source = sources[source_id]
            batch = await direct_document.discover(source, SourceState())
            if batch.items:
                await direct_document.fetch(
                    source,
                    batch.items[0],
                    acquisition_run_id=str(uuid4()),
                    trigger=AcquisitionTrigger.ON_DEMAND,
                )
            sample = batch.items[0].external_object_id if batch.items else None
            return len(batch.items), sample

        async def probe_scholarly(source_id: str) -> tuple[int, str | None]:
            source = sources[source_id]
            results = await scholarly.query(
                source,
                QuerySpec(filters={"query": "agent security", "limit": 3}),
                acquisition_run_id=str(uuid4()),
                trigger=AcquisitionTrigger.INVESTIGATION,
            )
            sample = results[0].external_object_id if results else None
            return len(results), sample

        async def discover_arxiv() -> tuple[int, str | None]:
            source = sources["arxiv-ai-security"]
            method = dict(source.discovery_method)
            method.update({"page_size": 3, "initial_limit": 3})
            probe_source = source.model_copy(update={"discovery_method": method})
            batch = await arxiv.discover(probe_source, SourceState())
            sample = batch.items[0].external_object_id if batch.items else None
            return len(batch.items), sample

        run_id = str(uuid4())
        trigger = AcquisitionTrigger.ON_DEMAND
        probes: list[tuple[str, str, Probe]] = [
            (
                "cve-program-cvelist-v5",
                "query:CVE-2024-3094",
                lambda: cvelist.query(
                    sources["cve-program-cvelist-v5"],
                    QuerySpec(filters={"cve_id": "CVE-2024-3094"}),
                    acquisition_run_id=run_id,
                    trigger=trigger,
                ),
            ),
            (
                "cnnvd-vulnerabilities",
                "query:CVE-2024-3094",
                lambda: cnnvd.query(
                    sources["cnnvd-vulnerabilities"],
                    QuerySpec(filters={"cve_id": "CVE-2024-3094", "page_size": 3}),
                    acquisition_run_id=run_id,
                    trigger=trigger,
                ),
            ),
            (
                "nvd-cves-2",
                "query:CVE-2024-3094",
                lambda: nvd.query(
                    sources["nvd-cves-2"],
                    QuerySpec(filters={"cve_id": "CVE-2024-3094"}),
                    acquisition_run_id=run_id,
                    trigger=trigger,
                ),
            ),
            (
                "osv-vulnerabilities",
                "query:CVE-2024-3094",
                lambda: osv.query(
                    sources["osv-vulnerabilities"],
                    QuerySpec(filters={"vulnerability_id": "CVE-2024-3094"}),
                    acquisition_run_id=run_id,
                    trigger=trigger,
                ),
            ),
            (
                "github-global-advisories",
                "query:CVE-2024-3094",
                lambda: github_advisory.query(
                    sources["github-global-advisories"],
                    QuerySpec(filters={"cve_id": "CVE-2024-3094"}),
                    acquisition_run_id=run_id,
                    trigger=trigger,
                ),
            ),
            (
                "cisa-kev",
                "query:CVE-2021-44228",
                lambda: cisa.query(
                    sources["cisa-kev"],
                    QuerySpec(filters={"cve_id": "CVE-2021-44228"}),
                    acquisition_run_id=run_id,
                    trigger=trigger,
                ),
            ),
            (
                "github-target-repos",
                "query:vllm-project/vllm",
                lambda: github_repo.query(
                    sources["github-target-repos"],
                    QuerySpec(filters={"repo_full_name": "vllm-project/vllm"}),
                    acquisition_run_id=run_id,
                    trigger=trigger,
                ),
            ),
            (
                "github-target-repos",
                "query:ray-project/ray",
                lambda: github_repo.query(
                    sources["github-target-repos"],
                    QuerySpec(filters={"repo_full_name": "ray-project/ray"}),
                    acquisition_run_id=run_id,
                    trigger=trigger,
                ),
            ),
            ("bleepingcomputer-news", "discover", discover_rss),
            ("oss-security", "discover+fetch", discover_oss_security),
            ("blockbeats-newsflash", "discover", discover_blockbeats),
            (
                "trailofbits-research",
                "discover+fetch",
                lambda: probe_html_managed("trailofbits-research"),
            ),
            ("nist-ai-rmf", "discover+fetch", lambda: probe_html_managed("nist-ai-rmf")),
            (
                "aws-security-bulletins",
                "discover+fetch",
                lambda: probe_html_managed("aws-security-bulletins"),
            ),
            (
                "openai-deployment-safety",
                "discover+fetch",
                lambda: probe_html_managed("openai-deployment-safety"),
            ),
            (
                "openai-research",
                "discover+fetch",
                lambda: probe_html_managed("openai-research"),
            ),
            (
                "openai-safety",
                "discover+fetch",
                lambda: probe_html_managed("openai-safety"),
            ),
            (
                "anthropic-system-cards",
                "discover+fetch",
                lambda: probe_html_managed("anthropic-system-cards"),
            ),
            (
                "anthropic-research",
                "discover+fetch",
                lambda: probe_html_managed("anthropic-research"),
            ),
            (
                "anthropic-news",
                "discover+fetch",
                lambda: probe_html_managed("anthropic-news"),
            ),
            (
                "deepmind-safety",
                "discover+fetch",
                lambda: probe_html_managed("deepmind-safety"),
            ),
            (
                "bytedance-seed-research",
                "discover+fetch",
                lambda: probe_html_managed("bytedance-seed-research"),
            ),
            (
                "microsoft-security-ai",
                "discover+fetch",
                lambda: probe_html_managed("microsoft-security-ai"),
            ),
            (
                "nvidia-ai-security",
                "discover+fetch",
                lambda: probe_html_managed("nvidia-ai-security"),
            ),
            (
                "meta-ai-safety",
                "discover+fetch",
                lambda: probe_html_managed("meta-ai-safety"),
            ),
            (
                "wiz-research",
                "discover+fetch",
                lambda: probe_html_managed("wiz-research"),
            ),
            (
                "unit42-research",
                "discover+fetch",
                lambda: probe_html_managed("unit42-research"),
            ),
            (
                "talos-research",
                "discover+fetch",
                lambda: probe_html_managed("talos-research"),
            ),
            (
                "certcc-vulnerability-notes",
                "discover+fetch",
                lambda: probe_html_managed("certcc-vulnerability-notes"),
            ),
            (
                "owasp-genai",
                "discover+fetch",
                lambda: probe_html_managed("owasp-genai"),
            ),
            (
                "certik-incident-analysis",
                "discover+fetch",
                lambda: probe_html_managed("certik-incident-analysis"),
            ),
            (
                "hiddenlayer-security-advisories",
                "discover+fetch",
                lambda: probe_html_managed("hiddenlayer-security-advisories"),
            ),
            (
                "hiddenlayer-reports",
                "discover+fetch",
                lambda: probe_html_managed("hiddenlayer-reports"),
            ),
            (
                "chainalysis-research",
                "discover+fetch",
                lambda: probe_html_managed("chainalysis-research"),
            ),
            ("foresight-timeline", "discover", discover_foresight),
            ("slowmist-hacked", "discover+fetch", discover_slowmist_hacked),
            (
                "oscs-community",
                "query:vllm",
                lambda: oscs.query(
                    sources["oscs-community"],
                    QuerySpec(filters={"keyword": "vllm"}),
                    acquisition_run_id=run_id,
                    trigger=trigger,
                ),
            ),
            ("lookonchain-x", "discover", lambda: discover_x("lookonchain-x")),
            (
                "peckshieldalert-x",
                "discover",
                lambda: discover_x("peckshieldalert-x"),
            ),
            ("zachxbt-x", "discover", lambda: discover_x("zachxbt-x")),
            (
                "cnvd-vulnerabilities",
                "discover",
                lambda: probe_html_managed("cnvd-vulnerabilities"),
            ),
            (
                "seebug-vuldb",
                "discover+fetch",
                lambda: probe_html_managed("seebug-vuldb"),
            ),
            (
                "theblock-exploits",
                "discover",
                lambda: discover_html_incident("theblock-exploits"),
            ),
            (
                "securityweek-news",
                "discover",
                lambda: discover_html_incident("securityweek-news"),
            ),
            (
                "cisa-cybersecurity-advisories",
                "discover+fetch",
                lambda: probe_html_managed("cisa-cybersecurity-advisories"),
            ),
            (
                "mandiant-threat-intelligence",
                "discover+fetch",
                lambda: probe_html_managed("mandiant-threat-intelligence"),
            ),
            (
                "certik-security-dashboard",
                "discover+fetch",
                lambda: probe_direct_document("certik-security-dashboard"),
            ),
            (
                "slowmist-reports",
                "discover+fetch",
                lambda: probe_direct_document("slowmist-reports"),
            ),
            (
                "cyvers-reports",
                "discover+fetch",
                lambda: probe_direct_document("cyvers-reports"),
            ),
            (
                "crossref-search",
                "query:agent-security",
                lambda: probe_scholarly("crossref-search"),
            ),
            (
                "openalex-search",
                "query:agent-security",
                lambda: probe_scholarly("openalex-search"),
            ),
            (
                "openreview-search",
                "query:agent-security",
                lambda: probe_scholarly("openreview-search"),
            ),
            (
                "semantic-scholar-search",
                "query:agent-security",
                lambda: probe_scholarly("semantic-scholar-search"),
            ),
            (
                "cac-ai-regulations",
                "discover+fetch",
                lambda: probe_direct_document("cac-ai-regulations"),
            ),
            (
                "china-ai-standards",
                "discover+fetch",
                lambda: probe_direct_document("china-ai-standards"),
            ),
            (
                "nist-genai-profile",
                "discover+fetch",
                lambda: probe_direct_document("nist-genai-profile"),
            ),
            (
                "eu-ai-act",
                "discover+fetch",
                lambda: probe_direct_document("eu-ai-act"),
            ),
            (
                "iso-ai-standards",
                "discover+fetch",
                lambda: probe_direct_document("iso-ai-standards"),
            ),
            (
                "mitre-atlas",
                "discover+fetch",
                lambda: probe_direct_document("mitre-atlas"),
            ),
            ("arxiv-ai-security", "discover", discover_arxiv),
            (
                "shodan-assets",
                "query:product:vllm",
                lambda: shodan.query(
                    sources["shodan-assets"],
                    QuerySpec(filters={"query": 'product:"vLLM"', "page": 1, "minify": True}),
                    acquisition_run_id=run_id,
                    trigger=trigger,
                ),
            ),
            (
                "censys-assets",
                "query:vllm",
                lambda: censys.query(
                    sources["censys-assets"],
                    QuerySpec(filters={"query": "vllm", "page_size": 1}),
                    acquisition_run_id=run_id,
                    trigger=trigger,
                ),
            ),
            (
                "fofa-assets",
                "query:vllm",
                lambda: fofa.query(
                    sources["fofa-assets"],
                    QuerySpec(filters={"query": 'product="vllm"', "size": 1}),
                    acquisition_run_id=run_id,
                    trigger=trigger,
                ),
            ),
            (
                "zoomeye-assets",
                "query:vllm",
                lambda: zoomeye.query(
                    sources["zoomeye-assets"],
                    QuerySpec(filters={"query": 'app:"vllm"', "page": 1, "pagesize": 1}),
                    acquisition_run_id=run_id,
                    trigger=trigger,
                ),
            ),
        ]
        configured_source_ids = set(sources)
        registered_source_ids = {source_id for source_id, _, _ in probes}
        missing_probe_owners = sorted(configured_source_ids - registered_source_ids)
        if missing_probe_owners:
            raise RuntimeError(
                f"configured sources without live probe owner: {missing_probe_owners}"
            )

        semaphore = asyncio.Semaphore(8)

        async def run_bounded(source_id: str, operation: str, probe: Probe):
            async with semaphore:
                return await run_live_probe(source_id, operation, probe)

        results = await asyncio.gather(
            *(run_bounded(source_id, operation, probe) for source_id, operation, probe in probes)
        )

    if json_output:
        print(json.dumps([item.model_dump(mode="json") for item in results], indent=2))
    else:
        width = max(len(item.source_id) for item in results)
        for item in results:
            sample = f" sample={item.sample_external_id}" if item.sample_external_id else ""
            detail = f" detail={item.detail}" if item.detail else ""
            print(
                f"{item.source_id:<{width}}  {item.status:<17} "
                f"{item.elapsed_ms:>6}ms records={item.record_count}{sample}{detail}"
            )
        summary: dict[str, int] = {}
        for item in results:
            summary[item.status] = summary.get(item.status, 0) + 1
        print("summary:", ", ".join(f"{key}={value}" for key, value in sorted(summary.items())))

    return 1 if strict and any(item.status != "ok" for item in results) else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe configured external sources with live requests"
    )
    parser.add_argument(
        "--strict", action="store_true", help="exit non-zero if any source is not OK"
    )
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON results")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_main(strict=args.strict, json_output=args.json)))


if __name__ == "__main__":
    main()
