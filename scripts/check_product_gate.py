from __future__ import annotations

import argparse
import gzip
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class GateResult:
    name: str
    detail: str


REPO_ROOT = Path(__file__).resolve().parents[1]


def _json(base_url: str, path: str) -> dict[str, Any]:
    request = Request(f"{base_url.rstrip('/')}{path}", headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=8) as response:
            if response.status >= 400:
                raise RuntimeError(f"{path} returned {response.status}")
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"{path} unavailable: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} did not return an object")
    return payload


def _html(url: str) -> str:
    try:
        with urlopen(Request(url, headers={"Accept": "text/html"}), timeout=8) as response:
            return response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"{url} unavailable: {exc}") from exc


def _sse(base_url: str, case_id: str) -> str:
    path = f"/api/v1/investigations/{quote(case_id, safe='')}/events?follow=false"
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        headers={"Accept": "text/event-stream"},
    )
    try:
        with urlopen(request, timeout=8) as response:
            content_type = response.headers.get("Content-Type", "")
            response.read(4096)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"{path} unavailable: {exc}") from exc
    if not content_type.startswith("text/event-stream"):
        raise RuntimeError(f"{path} returned {content_type!r}, expected text/event-stream")
    return content_type


def _read_source(relative_path: str) -> str:
    path = REPO_ROOT / relative_path
    if not path.is_file():
        raise RuntimeError(f"required product source missing: {relative_path}")
    return path.read_text(encoding="utf-8")


def _require_source(
    results: list[GateResult],
    *,
    name: str,
    relative_path: str,
    needles: tuple[str, ...],
    detail: str,
) -> None:
    source = _read_source(relative_path)
    missing = [needle for needle in needles if needle not in source]
    if missing:
        raise RuntimeError(
            f"{relative_path} missing {name} markers: {', '.join(missing)}"
        )
    results.append(GateResult(name, detail))


def _static_product_gate(results: list[GateResult]) -> None:
    _require_source(
        results,
        name="layout-authority",
        relative_path="apps/web/src/main.tsx",
        needles=(
            "import './cinematic.css'",
            "import './surface-authority.css'",
            "import './layout-authority.css'",
        ),
        detail="cinematic semantics + visual authority + final geometry authority",
    )
    main = _read_source("apps/web/src/main.tsx")
    cinematic_index = main.index("import './cinematic.css'")
    surface_index = main.index("import './surface-authority.css'")
    layout_index = main.index("import './layout-authority.css'")
    if not cinematic_index < surface_index < layout_index:
        raise RuntimeError(
            "stylesheet authority order must be cinematic -> surface -> layout"
        )

    _require_source(
        results,
        name="bilingual-product",
        relative_path="apps/web/src/main.tsx",
        needles=("I18nProvider",),
        detail="global zh/en state mounted",
    )
    _require_source(
        results,
        name="guided-demo",
        relative_path="apps/web/src/components/Shell.tsx",
        needles=(
            "guided-story",
            "storySteps",
            "storyMode",
            "FROZEN PATH",
            "BenchmarkRun / CaseRun",
            "guidedModeFromSearch",
            "withGuidedMode",
        ),
        detail="live + formal frozen guided paths are URL-addressable",
    )
    _require_source(
        results,
        name="world-fallback",
        relative_path="apps/web/src/pages/WorldPage.tsx",
        needles=("WorldField2D", "world-2d-fallback"),
        detail="2D evidence-world fallback present",
    )
    _require_source(
        results,
        name="reduced-motion",
        relative_path="apps/web/src/cinematic.css",
        needles=("@media (prefers-reduced-motion: reduce)",),
        detail="semantic motion has reduced-motion seam",
    )
    _require_source(
        results,
        name="evidence-drilldown",
        relative_path="apps/web/src/pages/InvestigationsPage.tsx",
        needles=("EvidenceOverlay", "getEvidence(", "EvidenceButtons"),
        detail="Case findings drill into Evidence",
    )
    _require_source(
        results,
        name="proof-evidence-drilldown",
        relative_path="apps/web/src/pages/ObservatoryPage.tsx",
        needles=("getEvidence(", "METRIC → EVIDENCE", "getCompetitionProofRun"),
        detail="MetricObservation drills into typed proof refs",
    )
    _require_source(
        results,
        name="degraded-ux",
        relative_path="apps/web/src/pages/WorldPage.tsx",
        needles=(
            "HOT READ SEAM DEGRADED",
            "sourceState(",
            "Operational snapshot is stale",
            "recovery-action",
            "hotQuery.refetch()",
        ),
        detail="live truth degradation remains explicit and recoverable",
    )
    _require_source(
        results,
        name="deep-link-state",
        relative_path="apps/web/src/pages/InvestigationsPage.tsx",
        needles=(
            "params.get('focus')",
            "params.get('evidence')",
            "normalizeCaseFocus",
            "useState<CaseStateFocus | null>(initialFocus)",
        ),
        detail="Case focus/evidence survive direct URL entry",
    )
    _require_source(
        results,
        name="memory-deep-link",
        relative_path="apps/web/src/pages/AgentsPage.tsx",
        needles=("params.get('section')", "agent-memory-field", "scrollIntoView"),
        detail="Agent memory route resolves to Skill / Experience field",
    )
    _require_source(
        results,
        name="world-focus-deep-link",
        relative_path="apps/web/src/pages/WorldPage.tsx",
        needles=(
            "params.get('source')",
            "params.get('lane')",
            "params.get('hot')",
            "nextParams.set('hot', key)",
        ),
        detail="World source / path / Hot focus survive URL entry",
    )
    _require_source(
        results,
        name="intelligence-view-deep-link",
        relative_path="apps/web/src/pages/IntelligencePage.tsx",
        needles=(
            "params.get('view')",
            "function selectReadingMode",
            "next.set('evidence', evidence)",
        ),
        detail="Intelligence dossier / graph / evidence view is URL-addressable",
    )
    _require_source(
        results,
        name="agent-task-deep-link",
        relative_path="apps/web/src/pages/AgentsPage.tsx",
        needles=(
            "params.get('run')",
            "params.get('role')",
            "function selectTask(runId: string)",
            "nextParams.set('run', runId)",
        ),
        detail="Agent Task and Role state survive direct URL entry",
    )
    _require_source(
        results,
        name="observatory-mode-deep-link",
        relative_path="apps/web/src/pages/ObservatoryPage.tsx",
        needles=(
            "params.get('mode') === 'proof'",
            "function selectMode(nextMode: ObservatoryMode)",
            "next.set('mode', 'proof')",
        ),
        detail="LIVE / PROOF mode is URL-addressable",
    )
    _require_source(
        results,
        name="system-overview",
        relative_path="apps/web/src/pages/ObservatoryPage.tsx",
        needles=(
            "getSystemOverview",
            "OUTBOX PENDING",
            "TASK DELIVERY",
            "STREAM UNACKED",
            "Worker process health has no heartbeat owner yet",
        ),
        detail="live Product system health keeps measured dependencies and explicit gaps separate",
    )
    _require_source(
        results,
        name="keyboard-product",
        relative_path="apps/web/src/components/Shell.tsx",
        needles=("product-skip-link", 'id="product-main"', "tabIndex={-1}"),
        detail="skip-link and keyboard main-content target present",
    )
    _require_source(
        results,
        name="semantic-tabs",
        relative_path="apps/web/src/pages/IntelligencePage.tsx",
        needles=('role="tab"', "aria-selected"),
        detail="Intelligence reading modes expose tab semantics",
    )
    dist = REPO_ROOT / "apps/web/dist"
    if dist.is_dir():
        manifest_path = dist / ".vite/manifest.json"
        if not manifest_path.is_file():
            raise RuntimeError("Vite build manifest missing from Product dist")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = manifest.get("index.html")
        if not isinstance(entry, dict):
            raise RuntimeError("Vite manifest missing index.html entry")

        initial_keys: set[str] = {"index.html"}
        pending = list(entry.get("imports", []))
        while pending:
            key = pending.pop()
            if key in initial_keys:
                continue
            initial_keys.add(key)
            node = manifest.get(key)
            if isinstance(node, dict):
                pending.extend(node.get("imports", []))
        initial_files = {
            str(manifest[key]["file"])
            for key in initial_keys
            if isinstance(manifest.get(key), dict) and manifest[key].get("file")
        }
        if any("three-runtime" in name for name in initial_files):
            raise RuntimeError(
                "Three/R3F runtime leaked into the initial Product dependency graph"
            )
        initial_js_gzip = sum(
            len(gzip.compress((dist / name).read_bytes(), compresslevel=9))
            for name in initial_files
            if name.endswith(".js")
        )
        if initial_js_gzip > 180_000:
            raise RuntimeError(
                f"initial Product JS is {initial_js_gzip / 1024:.1f} KiB gzip; "
                "budget is 175.8 KiB"
            )
        results.append(
            GateResult(
                "initial-js",
                f"{initial_js_gzip / 1024:.1f} KiB gzip · no Three/R3F",
            )
        )

        css_files = list((dist / "assets").glob("*.css"))
        if css_files:
            css_gzip = sum(
                len(gzip.compress(path.read_bytes(), compresslevel=9))
                for path in css_files
            )
            if css_gzip > 120_000:
                raise RuntimeError(
                    f"Product CSS is {css_gzip / 1024:.1f} KiB gzip; "
                    "budget is 117.2 KiB"
                )
            results.append(
                GateResult("product-css", f"{css_gzip / 1024:.1f} KiB gzip")
            )

        world_chunks = list((dist / "assets").glob("WorldPage-*.js"))
        if world_chunks:
            world_bytes = max(path.stat().st_size for path in world_chunks)
            if world_bytes > 300_000:
                raise RuntimeError(
                    f"WORLD product chunk is {world_bytes / 1024:.1f} KiB; "
                    "3D runtime must remain separately cacheable"
                )
            results.append(
                GateResult(
                    "world-bundle",
                    f"{world_bytes / 1024:.1f} KiB route chunk",
                )
            )
        three_chunks = list((dist / "assets").glob("three-runtime-*.js"))
        if not three_chunks:
            raise RuntimeError("three-runtime vendor chunk missing after product build")
        results.append(
            GateResult(
                "three-runtime",
                f"{max(path.stat().st_size for path in three_chunks) / 1024:.1f} KiB lazy vendor",
            )
        )


def run_gate(api_base: str, web_url: str | None) -> list[GateResult]:
    results: list[GateResult] = []
    _static_product_gate(results)

    ready = _json(api_base, "/health/ready")
    if ready.get("status") != "ready":
        raise RuntimeError(f"health readiness is not ready: {ready}")
    results.append(GateResult("health", "ready"))

    world = _json(api_base, "/api/v1/world/overview")
    for key in ("source_health", "categories", "sources", "windows", "hourly_series"):
        if key not in world:
            raise RuntimeError(f"world overview missing {key}")
    results.append(
        GateResult(
            "world",
            (
                f"{len(world.get('categories', []))} categories · "
                f"{len(world.get('sources', []))} sources"
            ),
        )
    )
    hot = _json(api_base, "/api/v1/world/hot?limit=8")
    hot_items = hot.get("items", [])
    if not isinstance(hot_items, list):
        raise RuntimeError("hot world items is not a list")
    results.append(GateResult("hot-world", f"{len(hot_items)} objects"))

    agents = _json(api_base, "/api/v1/agents/runtime?task_limit=8")
    roles = agents.get("roles", [])
    tasks = agents.get("recent_tasks", [])
    if not isinstance(roles, list) or not isinstance(tasks, list):
        raise RuntimeError("agent runtime roles/tasks malformed")
    results.append(GateResult("agents", f"{len(roles)} roles · {len(tasks)} recent tasks"))
    if tasks:
        run_id = tasks[0].get("run_id")
        if isinstance(run_id, str) and run_id:
            task = _json(api_base, f"/api/v1/tasks/{quote(run_id, safe='')}")
            if "task" not in task or "events" not in task or "capabilities" not in task:
                raise RuntimeError("task detail missing runtime coordinates")
            results.append(GateResult("task-detail", run_id))

    agent_proof = _json(api_base, "/api/v1/agents/proof")
    suite_ref = agent_proof.get("suite_ref")
    proof_cases = agent_proof.get("cases", [])
    if not isinstance(suite_ref, str) or not suite_ref.startswith(
        "m5-agent-runtime-controlled-v1@"
    ):
        raise RuntimeError("Agent proof is not bound to the controlled M5 runtime suite")
    if not isinstance(proof_cases, list):
        raise RuntimeError("Agent controlled proof cases malformed")
    delegated = next(
        (
            item
            for item in proof_cases
            if isinstance(item, dict)
            and item.get("case_id") == "agent-delegated-enrichment-resume"
        ),
        None,
    )
    if delegated is None or not delegated.get("task_run_ids"):
        raise RuntimeError("Agent proof lost delegated enrichment runtime coordinates")
    results.append(
        GateResult(
            "agent-proof",
            f"{suite_ref} · {len(proof_cases)} controlled cases",
        )
    )

    system = _json(api_base, "/api/v1/observatory/system")
    dependencies = system.get("dependencies", [])
    if not isinstance(dependencies, list):
        raise RuntimeError("system overview dependencies is not a list")
    component_names = {
        item.get("component")
        for item in dependencies
        if isinstance(item, dict) and isinstance(item.get("component"), str)
    }
    required_components = {
        "postgresql",
        "redis_broker",
        "redis_hot_cache",
        "redis_task_bus",
    }
    if not required_components.issubset(component_names):
        raise RuntimeError(
            f"system overview missing dependencies: {sorted(required_components - component_names)}"
        )
    boundaries = system.get("measurement_boundaries", {})
    if not isinstance(boundaries, dict) or boundaries.get("worker_process_health") != (
        "unavailable_no_heartbeat_contract"
    ):
        raise RuntimeError(
            "system overview must preserve the worker heartbeat measurement boundary"
        )
    results.append(
        GateResult(
            "system",
            (
                f"{system.get('overall', 'unknown')} · "
                f"{len(dependencies)} dependencies · "
                f"stream pending {system.get('task_event_stream_pending', '—')}"
            ),
        )
    )

    investigations = _json(api_base, "/api/v1/investigations?limit=8")
    cases = investigations.get("items", [])
    if not isinstance(cases, list):
        raise RuntimeError("investigation items is not a list")
    results.append(GateResult("investigations", f"{len(cases)} durable cases"))
    if cases:
        case_id = cases[0].get("case_id")
        if isinstance(case_id, str) and case_id:
            detail = _json(api_base, f"/api/v1/investigations/{quote(case_id, safe='')}")
            activity = _json(
                api_base,
                f"/api/v1/investigations/{quote(case_id, safe='')}/activity",
            )
            if detail.get("case_id") != case_id or activity.get("case_id") != case_id:
                raise RuntimeError("investigation detail/activity coordinate mismatch")
            content_type = _sse(api_base, case_id)
            results.append(GateResult("investigation-sse", content_type))

    incidents = _json(api_base, "/api/v1/incidents?limit=8")
    incident_items = incidents.get("items", [])
    if not isinstance(incident_items, list):
        raise RuntimeError("incident items is not a list")
    results.append(GateResult("incidents", f"{len(incident_items)} durable incidents"))
    if incident_items:
        incident_id = incident_items[0].get("incident_id")
        if isinstance(incident_id, str) and incident_id:
            detail = _json(api_base, f"/api/v1/incidents/{quote(incident_id, safe='')}")
            if detail.get("incident", {}).get("incident_id") != incident_id:
                raise RuntimeError("incident detail coordinate mismatch")
            results.append(GateResult("incident-detail", incident_id))

    proof = _json(api_base, "/api/v1/observatory/proof")
    runs = proof.get("runs", [])
    if not isinstance(runs, list):
        raise RuntimeError("proof runs is not a list")
    results.append(
        GateResult(
            "proof",
            (
                f"{proof.get('benchmark_runs_completed', 0)} runs · "
                f"{proof.get('case_runs_passed', 0)} passed cases"
            ),
        )
    )
    headline_metrics = proof.get("headline_metrics", [])
    if not isinstance(headline_metrics, list):
        raise RuntimeError("proof headline_metrics is not a list")
    metric_by_name = {
        item.get("metric_name"): item
        for item in headline_metrics
        if isinstance(item, dict) and isinstance(item.get("metric_name"), str)
    }
    delivery = metric_by_name.get("m1.source_delivery_coverage")
    if not isinstance(delivery, dict):
        raise RuntimeError("proof must preserve m1.source_delivery_coverage")
    delivery_value = delivery.get("value")
    if not isinstance(delivery_value, (int, float)):
        raise RuntimeError("m1.source_delivery_coverage has no numeric value")
    if float(delivery_value) >= 1.0:
        raise RuntimeError(
            "expected frozen M1 source-delivery weakness is no longer visible; "
            "verify report identity before changing the product proof"
        )
    results.append(
        GateResult(
            "proof-weakness",
            f"m1.source_delivery_coverage={float(delivery_value):.6f}",
        )
    )
    if runs:
        run_id = runs[0].get("benchmark_run_id")
        if isinstance(run_id, str) and run_id:
            detail = _json(api_base, f"/api/v1/observatory/proof/runs/{quote(run_id, safe='')}")
            if detail.get("run", {}).get("benchmark_run_id") != run_id:
                raise RuntimeError("proof run coordinate mismatch")
            results.append(
                GateResult(
                    "proof-run",
                    (
                        f"{len(detail.get('cases', []))} cases · "
                        f"{len(detail.get('metrics', []))} metrics"
                    ),
                )
            )

    if web_url:
        html = _html(web_url)
        if 'id="root"' not in html:
            raise RuntimeError("product HTML missing React root")
        results.append(GateResult("product-web", web_url))

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate live SecFusion Product read seams.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--web-url", default="http://127.0.0.1:8000/product/")
    parser.add_argument(
        "--static-only",
        action="store_true",
        help="Validate Product source invariants without requiring live services.",
    )
    args = parser.parse_args()
    try:
        if args.static_only:
            results: list[GateResult] = []
            _static_product_gate(results)
        else:
            results = run_gate(args.api_base, args.web_url or None)
    except RuntimeError as exc:
        print(f"PRODUCT GATE FAIL · {exc}")
        return 1
    for result in results:
        print(f"PASS · {result.name:<18} · {result.detail}")
    print(f"PRODUCT GATE PASS · {len(results)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
