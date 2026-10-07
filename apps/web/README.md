# `apps.web` — SecFusion Product App

`apps.web` is the user-facing SecFusionAgent product frontend.

The authoritative Product UI contract is [`SPEC.md`](SPEC.md). Product exposes Evidence Plane, Agent Runtime, Investigation/Decision and live Operations. Competition evaluation remains an internal engineering capability.

## Boundary

The Product App is independent from:

- the project Wiki/Website, which explains the architecture and competition evidence;
- the retired Runtime Workbench surface; Product UI uses Product/Application contracts only;
- A2A transport DTOs, which are protocol compatibility rather than Product presentation contracts.

The Product browser must use stable Product/Application routes and Product-safe read models. It must not query internal persistence models or depend on Workbench responses.

## Styling ownership

The stylesheet order is intentional and forms a small authority stack:

- `styles.css` owns shared product primitives and low-level defaults.
- `cinematic.css` owns the default visual language of the six product spaces.
- `cinematic-seams.css` owns late cross-space product seams and navigational surfaces that must stay after the base cinematic layer but before final authorities.
- `surface-authority.css` owns the small set of intentional late visual overrides: palette, borders, shadows, typography emphasis, and motion styling.
- `layout-authority.css` owns geometry, responsive composition, overflow, safe areas, readable type floors, and z-index.

Do not fix layout by appending visual overrides to `layout-authority.css`, or fix visual semantics by moving geometry into `surface-authority.css`. `npm run lint:css-authority` enforces this boundary. Page-specific composition should stay page-specific; avoid introducing a generic page shell that collapses WORLD, INTELLIGENCE, INVESTIGATIONS, AGENTS, OBSERVATORY, and START into the same layout.

## Product spaces

```text
WORLD           Evidence World / Data Plane
INTELLIGENCE    dossiers, graph and evidence
INVESTIGATIONS  durable cases and continuous interaction
AGENTS          Role / Task / Capability / Skill / Experience
OBSERVATORY     live operations and service health

                START
```

`START` exposes the canonical DIRECT / RETRIEVE / VERIFY / INVESTIGATE / WATCH interaction modes.

Completed START results display the full persisted answer, typed conclusions, conflicts, unknowns and assumptions. Citations open Evidence directly even for a generic RETRIEVE without a selected target. The URL carries `decision` and, when present, `session` so refresh restores the result through `GET /api/v1/decisions/{id}`. Follow-up sends the same session without rebinding its target; “New session” explicitly clears that binding. Ctrl/Cmd+Enter submits the question.

## Local frontend/backend integration

Start the API from a shell that has loaded the repository's local experiment environment when model-backed QA is needed:

```bash
. ./activate.sh
.venv/bin/uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
cd apps/web
npm run dev
```

Open `http://localhost:5173/product/`. To use another API port, set `SECFUSION_API_PROXY=http://127.0.0.1:8001` when starting Vite. The proxy setting is development-only; production uses the existing Nginx same-origin routes. An API started without model configuration can serve Knowledge and Evidence while returning an explicit dependency error for model-backed QA.

The user-facing app contains no demonstration guide or frozen benchmark view. WORLD keeps source geometry, recent Knowledge changes, Hot objects and its detail panel in distinct regions. START uses five profile cards with a separate question console; asynchronous accepted Cases update into their persisted Decision when the worker completes M5 → M6.

## Browser regression gate

`make product-visual-check` runs Chromium against the live local Product at `http://127.0.0.1:8000/product`. It resolves current Hot / Case / Task coordinates, checks all six Product spaces at 1440×1000, 1366×768, 1024×768, and 390×844, rejects document-level horizontal overflow or collapsed primary regions, checks the reduced-motion WORLD fallback, and writes review screenshots under `/tmp/secfusion-product-visual`.

`make product-interaction-check` complements the geometry gate. It hit-tests visible interactive controls so decorative layers cannot silently intercept clicks, then exercises the stateful WORLD time window, START execution-profile / advanced controls, and OBSERVATORY time window and refresh. Keep both browser gates separate from the fast `make product-check`; run the interaction gate whenever z-index, pointer-event ownership, or interactive composition changes.

`uv run python scripts/check_product_decision_flow.py` checks persisted Decision → target-free citation → Evidence → Escape/focus recovery → refresh at desktop and mobile widths. It only reads existing results and makes no model calls. Override `--api-base` and `--product-base` for a separate Vite/API integration environment.

Install the browser runtime once with `uv run playwright install chromium`. Run `make product-visual-check` whenever composition, responsive layout, navigation shell, or cinematic state changes.

## Current product state

The former Runtime Workbench UI and `/api/v1/workbench/*` transport have been retired. Runtime facts required by the competition are exposed through Product-safe read models used by WORLD, INTELLIGENCE, INVESTIGATIONS, AGENTS and OBSERVATORY.

## Truthfulness rule

Live visuals must be driven by runtime facts. Benchmark results are not exposed as live Product facts. The frontend may add presentation aliases and cinematic motion, but it may not fabricate source health, Hot CVEs, Agent activity, Skill status, tool calls, token streaming, or monetary cost.
