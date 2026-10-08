from __future__ import annotations

import argparse
import gzip
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request

if TYPE_CHECKING:
    from scripts.product_check_session import (
        open_product_request,
        product_session_cookie,
        request_headers,
    )
elif __package__:
    from .product_check_session import open_product_request, product_session_cookie, request_headers
else:
    from product_check_session import open_product_request, product_session_cookie, request_headers


@dataclass(frozen=True)
class GateResult:
    name: str
    detail: str
    status: Literal["pass", "skip"] = "pass"


REPO_ROOT = Path(__file__).resolve().parents[1]


def _json(
    base_url: str, path: str, *, cookie: str | None = None, timeout: float = 8
) -> dict[str, Any]:
    request = Request(
        f"{base_url.rstrip('/')}{path}", headers=request_headers("application/json", cookie)
    )
    try:
        with open_product_request(request, timeout=timeout) as response:
            if response.status >= 400:
                raise RuntimeError(f"{path} returned {response.status}")
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"{path} unavailable: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} did not return an object")
    return payload


def _json_list(base_url: str, path: str) -> list[dict[str, Any]]:
    request = Request(f"{base_url.rstrip('/')}{path}", headers={"Accept": "application/json"})
    try:
        with open_product_request(request, timeout=8) as response:
            if response.status >= 400:
                raise RuntimeError(f"{path} returned {response.status}")
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"{path} unavailable: {exc}") from exc
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise RuntimeError(f"{path} did not return an object list")
    return payload


def _html(url: str) -> str:
    try:
        with open_product_request(
            Request(url, headers={"Accept": "text/html"}), timeout=8
        ) as response:
            return response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"{url} unavailable: {exc}") from exc


def _sse(base_url: str, case_id: str, *, cookie: str | None = None) -> str:
    path = f"/api/v1/investigations/{quote(case_id, safe='')}/events?follow=false"
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        headers=request_headers("text/event-stream", cookie),
    )
    try:
        with open_product_request(request, timeout=8) as response:
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
        raise RuntimeError(f"{relative_path} missing {name} markers: {', '.join(missing)}")
    results.append(GateResult(name, detail))


def _static_product_gate(results: list[GateResult]) -> None:
    _require_source(
        results,
        name="layout-authority",
        relative_path="apps/web/src/main.tsx",
        needles=(
            "import './product-foundation.css'",
            "import './product-spaces.css'",
            "import './account-space.css'",
        ),
        detail="Product foundation, spaces and account style authorities",
    )
    main = _read_source("apps/web/src/main.tsx")
    if (
        not main.index("import './product-foundation.css'")
        < main.index("import './product-spaces.css'")
        < main.index("import './account-space.css'")
    ):
        raise RuntimeError("Product styles must load foundation, spaces, then account styles")

    _require_source(
        results,
        name="bilingual-product",
        relative_path="apps/web/src/main.tsx",
        needles=("I18nProvider",),
        detail="global zh/en state mounted",
    )
    _require_source(
        results,
        name="world-spatial-read",
        relative_path="apps/web/src/components/world/WorldScene.tsx",
        needles=(
            "<EvidenceAtlas",
            "ew-foreground",
            "onFocus(story)",
            "useReducedMotion",
            "ew-inspector",
        ),
        detail="DOM story and SVG spatial focus remain readable without WebGL",
    )
    _require_source(
        results,
        name="world-fact-projection",
        relative_path="apps/application/queries/world.py",
        needles=(
            "list_world_stories",
            "DocumentRevisionModel",
            "WorldStoryEvidenceView",
            'RelationModel.lifecycle == "accepted"',
            "_interleave",
        ),
        detail="heterogeneous projection preserves source facts, current revisions and evidence",
    )
    _require_source(
        results,
        name="world-hot-boundary",
        relative_path="apps/web/src/pages/WorldPage.tsx",
        needles=(
            "getHotWorld(64)",
            "getHotWorldItem",
            "enabled: Boolean(hotCoordinate?.length",
            "evidence: null",
        ),
        detail="Hot remains replaceable source state and cannot masquerade as durable evidence",
    )
    _require_source(
        results,
        name="world-source-inspection",
        relative_path="apps/web/src/components/world/WorldSourceInspector.tsx",
        needles=("getWorldOverview", "measurement_category === category", "last_success_at"),
        detail="source inspection uses measured runtime state and does not block the initial story",
    )
    _require_source(
        results,
        name="world-live-overview-read",
        relative_path="apps/api/routes/world.py",
        needles=(
            "from packages.monitoring.data_plane_status import data_plane_status",
            "payload = await _live_overview_payload()",
        ),
        detail="inspection reads current runtime state through its existing aggregation owner",
    )
    _require_source(
        results,
        name="reduced-motion",
        relative_path="apps/web/src/product-foundation.css",
        needles=("@media (prefers-reduced-motion:reduce)",),
        detail="semantic motion has reduced-motion seam",
    )
    _require_source(
        results,
        name="start-enrichment-delegation",
        relative_path="apps/web/src/components/start/AlchemistBoundary.tsx",
        needles=(
            "getInvestigationActivity(caseId!)",
            "event.role_id === 'EnrichmentRole' && event.task_run_id",
            "getAgentTask(enrichmentRunId!)",
            "task?.parent_run_id && parent",
            "This investigation has not requested intelligence enrichment.",
        ),
        detail=(
            "START lights ALCHEMIST only from a real EnrichmentRole TaskRun and "
            "verifies delegated parent state"
        ),
    )
    _require_source(
        results,
        name="start-enrichment-wiring",
        relative_path="apps/web/src/pages/StartPage.tsx",
        needles=(
            "<AlchemistBoundary",
            "result?.mode === 'accepted'",
            "caseId={result?.investigation?.case_id ?? null}",
        ),
        detail="START binds the enrichment boundary to the accepted durable Case",
    )
    _require_source(
        results,
        name="evidence-drilldown",
        relative_path="apps/web/src/components/investigations/CaseSurfaces.tsx",
        needles=("EvidenceOverlay", "getEvidence(", "EvidenceButtons"),
        detail="Case findings drill into Evidence",
    )
    _require_source(
        results,
        name="case-task-injection",
        relative_path="apps/web/src/components/investigations/CaseSurfaces.tsx",
        needles=(
            "const continuationKind = continuationTaskKind",
            "askQuestion({ question, sessionId, taskKind: continuationKind })",
            "CONTINUE THIS INVESTIGATION",
            "CONTINUE THE SAME CASE",
            (
                "This follow-up continues the current durable Case "
                "while preserving its targets, evidence, and state."
            ),
        ),
        detail=(
            "Case follow-up is presented as a same-session next episode injection, "
            "while persisted ProductEvent/SSE remains the state authority"
        ),
    )
    _require_source(
        results,
        name="degraded-ux",
        relative_path="apps/web/src/pages/WorldPage.tsx",
        needles=(
            "workingSet.isError",
            "onHotRetry",
            "getWorldOverview",
            "onRetry",
            "workingSet.refetch()",
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
            "continuation_session_id",
            "normalizeCaseFocus",
            "<CaseWorkspace",
        ),
        detail=(
            "Case focus/evidence survive direct URL entry and owned sessions "
            "resume the durable Case"
        ),
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
            "params.get('view')",
            "params.get('hot')",
            "next.set('hot', story.story_id.slice(4))",
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
    for path, forbidden in (
        ("apps/web/src/components/Shell.tsx", ("guided-story", "getCompetitionProof")),
        ("apps/web/src/pages/ObservatoryPage.tsx", ("ProofObservatory", "getCompetitionProof")),
        ("apps/web/src/pages/AgentsPage.tsx", ("AgentControlledProof", "getAgentControlledProof")),
        ("apps/web/src/App.tsx", ('path="/demo"', 'path="/demo/frozen"')),
    ):
        source = _read_source(path)
        if any(marker in source for marker in forbidden):
            raise RuntimeError(f"Product must not expose demo or frozen proof surfaces: {path}")
    results.append(
        GateResult("production-surfaces", "live product navigation without demo/proof surfaces")
    )
    _require_source(
        results,
        name="system-overview-query",
        relative_path="apps/web/src/pages/ObservatoryPage.tsx",
        needles=("getSystemOverview", "observatory-system"),
        detail="Observatory orchestration owns the live system read",
    )
    _require_source(
        results,
        name="system-overview",
        relative_path="apps/web/src/components/observatory/ObservatoryLive.tsx",
        needles=(
            "OUTBOX PENDING",
            "TASK DELIVERY",
            "STREAM UNACKED",
            "<WorkerHealth probe={system?.worker_probe ?? null}",
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
            raise RuntimeError("Three/R3F runtime leaked into the initial Product dependency graph")
        initial_js_gzip = sum(
            len(gzip.compress((dist / name).read_bytes(), compresslevel=9))
            for name in initial_files
            if name.endswith(".js")
        )
        if initial_js_gzip > 180_000:
            raise RuntimeError(
                f"initial Product JS is {initial_js_gzip / 1024:.1f} KiB gzip; budget is 175.8 KiB"
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
                len(gzip.compress(path.read_bytes(), compresslevel=9)) for path in css_files
            )
            if css_gzip > 120_000:
                raise RuntimeError(
                    f"Product CSS is {css_gzip / 1024:.1f} KiB gzip; budget is 117.2 KiB"
                )
            results.append(GateResult("product-css", f"{css_gzip / 1024:.1f} KiB gzip"))

        world_chunks = list((dist / "assets").glob("WorldPage-*.js"))
        if world_chunks:
            world_bytes = max(path.stat().st_size for path in world_chunks)
            if world_bytes > 300_000:
                raise RuntimeError(
                    f"WORLD product chunk is {world_bytes / 1024:.1f} KiB; "
                    "World route must remain separately cacheable"
                )
            results.append(
                GateResult(
                    "world-bundle",
                    f"{world_bytes / 1024:.1f} KiB route chunk",
                )
            )


def run_gate(api_base: str, web_url: str | None) -> list[GateResult]:
    results: list[GateResult] = []
    _static_product_gate(results)

    ready = _json(api_base, "/health/ready")
    if ready.get("status") != "ready":
        raise RuntimeError(f"health readiness is not ready: {ready}")
    results.append(GateResult("health", "ready"))

    world = _json(api_base, "/api/v1/world/overview", timeout=12)
    for key in ("source_health", "categories", "sources", "windows", "hourly_series"):
        if key not in world:
            raise RuntimeError(f"world overview missing {key}")
    window_24h = world.get("windows", {}).get("24h", {})
    for key in (
        "document_chunks",
        "document_text_bytes",
        "fresh_contributing_sources",
        "fresh_contributing_categories",
        "fresh_top1_source_share",
        "evidence_integrity_rate",
        "evidence_physical_bytes",
    ):
        if key not in window_24h:
            raise RuntimeError(f"world 24h measurement contract missing {key}")
    hourly = world.get("hourly_series", [])
    if hourly and isinstance(hourly[-1], dict):
        for key in (
            "document_chunks",
            "fresh_contributing_sources",
            "fresh_contributing_categories",
            "fresh_top1_source_share",
        ):
            if key not in hourly[-1]:
                raise RuntimeError(f"world hourly measurement contract missing {key}")
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

    cookie = product_session_cookie()
    if cookie is not None:
        account = _json(api_base, "/api/v1/auth/me", cookie=cookie)
        if account.get("authenticated") is not True:
            raise RuntimeError("configured Product session is expired or unauthenticated")
        agents = _json(api_base, "/api/v1/agents/runtime?task_limit=8", cookie=cookie)
        roles = agents.get("roles", [])
        tasks = agents.get("recent_tasks", [])
        if not isinstance(roles, list) or not isinstance(tasks, list):
            raise RuntimeError("agent runtime roles/tasks malformed")
        results.append(GateResult("agents", f"{len(roles)} roles · {len(tasks)} recent tasks"))
        if tasks:
            run_id = tasks[0].get("run_id")
            if isinstance(run_id, str) and run_id:
                task = _json(api_base, f"/api/v1/tasks/{quote(run_id, safe='')}", cookie=cookie)
                if any(
                    key not in task
                    for key in ("task", "parent", "children", "events", "capabilities")
                ):
                    raise RuntimeError("task detail missing runtime coordinates")
                results.append(GateResult("task-detail", run_id))

        if not tasks:
            results.append(GateResult("task-detail", "no visible tasks for this account", "skip"))
    else:
        results.append(GateResult("agents", "no Product account session supplied", "skip"))
        results.append(GateResult("task-detail", "no Product account session supplied", "skip"))

    skills = _json_list(api_base, "/api/v1/agents/skills")
    experiences = _json_list(api_base, "/api/v1/agents/experiences")
    if skills:
        skill_ref = skills[0].get("skill_ref")
        if not isinstance(skill_ref, str):
            raise RuntimeError("agent skill collection lost immutable skill_ref")
        skill = _json(api_base, f"/api/v1/agents/skills/{quote(skill_ref, safe='')}")
        if skill.get("skill_ref") != skill_ref:
            raise RuntimeError("agent skill detail coordinate mismatch")
    if experiences:
        experience_ref = experiences[0].get("experience_version_id")
        if not isinstance(experience_ref, str):
            raise RuntimeError("agent experience collection lost immutable version id")
        experience = _json(
            api_base,
            f"/api/v1/agents/experiences/{quote(experience_ref, safe='')}",
        )
        if experience.get("experience_version_id") != experience_ref:
            raise RuntimeError("agent experience detail coordinate mismatch")
    results.append(
        GateResult(
            "agent-learning",
            f"{len(skills)} skills · {len(experiences)} experience versions",
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
        "bounded_celery_control_responses_not_durable_heartbeat"
    ):
        raise RuntimeError(
            "system overview must declare the bounded Celery control measurement boundary"
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

    if cookie is not None:
        investigations = _json(api_base, "/api/v1/investigations?limit=8", cookie=cookie)
        cases = investigations.get("items", [])
        if not isinstance(cases, list):
            raise RuntimeError("investigation items is not a list")
        results.append(GateResult("investigations", f"{len(cases)} durable cases"))
        if cases:
            case_id = cases[0].get("case_id")
            if isinstance(case_id, str) and case_id:
                detail = _json(
                    api_base, f"/api/v1/investigations/{quote(case_id, safe='')}", cookie=cookie
                )
                activity = _json(
                    api_base,
                    f"/api/v1/investigations/{quote(case_id, safe='')}/activity",
                    cookie=cookie,
                )
                if detail.get("case_id") != case_id or activity.get("case_id") != case_id:
                    raise RuntimeError("investigation detail/activity coordinate mismatch")
                content_type = _sse(api_base, case_id, cookie=cookie)
                results.append(GateResult("investigation-sse", content_type))

        if not cases:
            results.append(
                GateResult("investigation-detail", "no durable cases for this account", "skip")
            )
            results.append(
                GateResult("investigation-sse", "no durable cases for this account", "skip")
            )
    else:
        for name in ("investigations", "investigation-detail", "investigation-sse"):
            results.append(GateResult(name, "no Product account session supplied", "skip"))

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

    live_cve = next(
        (
            item.get("cve_id")
            for item in hot_items
            if isinstance(item, dict) and isinstance(item.get("cve_id"), str)
        ),
        None,
    )
    if live_cve:
        search = _json(
            api_base, f"/api/v1/intelligence/search?q={quote(live_cve, safe='')}&limit=4"
        )
        vulnerability = next(
            (
                item
                for item in search.get("items", [])
                if isinstance(item, dict)
                and item.get("object_type") == "Vulnerability"
                and isinstance(item.get("object_id"), str)
            ),
            None,
        )
        if vulnerability:
            object_id = quote(vulnerability["object_id"], safe="")
            enrichment = _json(
                api_base,
                f"/api/v1/intelligence/objects/{object_id}/enrichment",
            )
            dimensions = enrichment.get("dimensions", [])
            if not isinstance(dimensions, list) or len(dimensions) != 12:
                raise RuntimeError("enrichment-v1 Product state must expose 12 dimensions")
            states = {item.get("status") for item in dimensions if isinstance(item, dict)}
            if not states or not states <= {"resolved", "conflict", "unknown", "missing"}:
                raise RuntimeError("invalid current enrichment dimension states")
            results.append(
                GateResult("enrichment-state", "current live Vulnerability · 12 dimensions")
            )
        else:
            results.append(
                GateResult(
                    "enrichment-state", "Hot target has no canonical Vulnerability yet", "skip"
                )
            )
    else:
        results.append(
            GateResult("enrichment-state", "no live Vulnerability target available", "skip")
        )

    if web_url:
        html = _html(web_url)
        if 'id="root"' not in html:
            raise RuntimeError("product HTML missing React root")
        results.append(GateResult("product-web", web_url))

    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate live SecFusion Product read seams.",
        epilog="SECFUSION_PRODUCT_SESSION_COOKIE enables private checks; missing accounts skip.",
    )
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
        print(f"{result.status.upper()} · {result.name:<18} · {result.detail}")
    passed = sum(result.status == "pass" for result in results)
    skipped = len(results) - passed
    outcome = "COMPLETE" if skipped else "PASS"
    print(f"PRODUCT GATE {outcome} · {passed} passed · {skipped} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
