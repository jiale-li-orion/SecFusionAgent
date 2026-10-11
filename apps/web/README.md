# `apps.web` — SecFusion Product Web

The Product Web has four primary spaces: **World, Intelligence, Ask and Workspace**. The [October experience contract](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Product-Web-Experience-2026-10) follows the user's latest reference images and feedback and supersedes earlier UI-cache directions. [`SPEC.md`](SPEC.md) retains the underlying behavior contracts. Product facts come from Application/API reads, never presentation fixtures or benchmark snapshots.

## Navigation and content

| Entry | Opening experience | Deeper interaction |
| --- | --- | --- |
| World `/` | Eight labeled source controls and a focused live material map | Source inspection, real Hot index/search, evidence formation and dossier handoff |
| Intelligence `/intelligence` | Recommendation feed; Following, Events and Library channels | Recommendation reasons/feedback, evidence-backed dossiers, enrichment and incident evolution |
| Ask `/start` | Natural question, suggested prompts and bottom composer | Full conversation, history drawer, per-turn evidence/model/context/tool audit |
| Workspace `/workspace` | Account, conversations, interests and investigations | Profile editor and Operations overview |

`/investigations` remains the complete Case workspace under My investigations. `/agents` and `/observatory` remain directly addressable under Workspace → Operations, preserving task, Skill and source deep links. `/workspace/profile` edits the display name and explicit recommendation interests; `/workspace/operations` reads current task and service state.

Intelligence uses `channel=recommended|following|events|library`. Recommendations retain server ranking; Following orders matching content by available evidence observation time. An anonymous reader gets a public discovery feed and a concise sign-in entry, never a false personalized ranking. Feedback persists through the existing API and supports undo. Dossier return links retain channel and category. Source stories request at most the API's 18-record projection limit.

Incident evolution uses retained events and their evidence references. Observation time and reported event time remain separate. The graph reveals up to 16 records at stable positions while the timeline retains the full returned history; the range control is available only for real timestamps. This is an incident-record/evidence view, not a fabricated complete Knowledge graph or historical Case replay. Missing history has an explicit empty state.

World keeps source health, acquisition time, original source text and Hot/cache identity separate from durable Knowledge. The Hot index pages 24 ranked source records at a time, up to the API offset cap of 4096, and shows the independent resident total. Exact CVE lookup searches the resident pool; free text filters the loaded page. Sources and materials can be focused without a camera-control vocabulary. Motion follows selection and respects reduced motion. COBE supplies the ambient globe without invented geographic markers; the overlaid source links remain actual material provenance. Animation stops offscreen or in a hidden tab, and unavailable WebGL does not remove the evidence controls.

## Conversation and evidence

Ask sends ordinary natural language. The API resolves intent and builds retrieval queries; the browser does not require a mode or CVE. Optional object scope and provider reasoning are under Answer options. Suggestions fill the editable composer and do not start a model call automatically.

The conversation occupies one reading column. The composer has its own bottom layout row, so it cannot overlay the transcript. History and audit are Radix dialogs with focus containment, Escape and focus return. Citations in audit load the exact retained evidence version and display publisher identity, object and evidence type. The Evidence inspector opens above the audit drawer, preserving its reading position; dismissing it returns focus to the original citation.

`POST /api/v1/questions/stream` supplies actual provider SSE. React paces received answer and optional reasoning text; reduced motion displays it immediately. Only `report_paragraphs` are previewed as prose, and the arriving JSON remains an unvalidated draft. The validated durable Decision replaces it immediately. Failed streams retain a clearly incomplete draft and allow retry. Stop receiving aborts the browser stream; its copy explicitly states that the server task may continue. The full dialogue requests a 90-second interactive budget.

Account conversations and turns use owner-checked cursor pages. Loading older turns does not autoscroll away from the reader; a selected older turn can load its preceding pages. Each turn reads its immutable `decision_ref`, never the latest mutable Case report. Accepted investigations keep their live Case/SSE state and distinguish active, waiting, resolved and stopped outcomes. A new conversation clears old outcome and scope coordinates.

Completed answers lead with natural report paragraphs and citations. Older Decisions without paragraphs retain their validated conclusions. Structured answer fields stay expandable for audit and QA. The per-turn audit exposes query plans, evidence, linked TaskRuns, model attempts, usage versus budget settlement, ContextManifest, prompt-fragment provenance and tool/runtime events. Raw provider reasoning stays transient rather than pretending to be durable audit data.

Evidence inspection leads with readable source content, the cited version and the original link. Provenance details retain source/Observation identity, locator, trust class and content hash. Public managed documents also expose bounded excerpts from the cited source version. These are source previews; object-level evidence does not imply a sentence-level claim locator. Unavailable reads provide retry actions.

## Accounts and integration

The user flow is register/sign in → edit interests → browse recommendations and evidence → ask/investigate → resume the saved conversation. Server-owned HttpOnly cookies resolve account identity; the browser never sends a chosen principal or stores credentials in localStorage. Account changes clear query state, close old streams and notify other tabs. Questions, Cases and private runtime reads remain owner-scoped.

`PUT /api/v1/auth/profile` updates the display name using the existing session and Origin/CSRF checks. Interests retain the backend limit of 20 keywords and 20 followed objects. Saving preferences invalidates recommendation reads. Email verification, password recovery and OAuth remain separate account-lifecycle work.

Question and Case commands carry `Idempotency-Key`; retries cannot silently create duplicate work. Cancellation sends the displayed Case revision through `If-Match`. A completed SSE replay returns its persisted result without inventing token replay. An unavailable model provider yields an explicit error; source and Knowledge reads remain available.

Agent runtime shows recent topology alongside cursor-paged owner-scoped Task history. Task-node spacing uses the visible row count, and phones scroll inside the graph instead of shrinking its labels. Observatory leads with compact hourly trends and source health, followed by source/data/agent/service detail tabs. Dossiers preserve ContextManifest, model attempts, delegation, Skill and Experience links. Observatory distinguishes unavailable reads from measured zeros; refresh retries the live reads without retimestamping cached data. No evaluation scoreboard, frozen-proof screen or guided demonstration belongs in these flows.

## Components and style ownership

`src/components/ui/` contains adapted **shadcn/ui source**, with MIT attribution in [`THIRD_PARTY.md`](src/components/ui/THIRD_PARTY.md). Button, Card, Badge, Input, Avatar, Separator, DropdownMenu, Tabs and Item are editable project components. Radix owns dialogs, account menus and keyboard tab navigation; Lucide owns functional icons. There is no extra shadcn runtime package.

The visual system uses neutral white reading surfaces, navy source maps, cobalt interactions and restrained semantic colors. Manrope and locally hosted Noto Sans SC UI subsets provide consistent typography; publisher marks come from locally hosted Simple Icons assets (see asset READMEs for licenses). Publisher names match explicit registered source IDs and complete hostnames, keeping NVD, NIST, CNNVD and CNVD distinct. `BrandMark` owns the small product identity; decorative 3D icons no longer fill the World, Intelligence, Ask or Agent role openings.

The global import order in `src/main.tsx` is:

1. `ui.css`: Tailwind theme/utilities without a second reset.
2. `product-foundation.css`: tokens, base reset, typography, shared primitives and four-entry shell.
3. `product-spaces.css`: retained dossier, investigation and detailed runtime/observatory surfaces.
4. `account-space.css`: account controls and authentication.

Page-local owners are `components/world/world.css`, `components/intelligence/intelligence.css`, `pages/questions-space.css`, `pages/workspace.css`, `pages/personal-space.css`, `components/agents/role-cards.css` and `components/observatory/observatory-overview.css`. Change their actual rules rather than appending competing overrides. The retired legacy stylesheets stay outside the import graph. `lint:css-authority` checks ownership; the source-size guard keeps pages and components bounded.

## Local development

`make dev-runtime-up` starts the Compose API on `127.0.0.1:8001` and its durable workers. With the infrastructure already running, an alternative API process is:

```bash
.venv/bin/uvicorn apps.api.main:app --host 127.0.0.1 --port 8001
```

Start the web process:

```bash
cd apps/web
npm ci
npm run dev -- --strictPort
```

Open **http://127.0.0.1:5173/product/**. Vite proxies `/api` and `/health` to `127.0.0.1:8001`; `SECFUSION_API_PROXY` changes that target. Production uses same-origin Nginx. Configure `SECFUSION_AUTH_ALLOWED_ORIGINS` for the actual external HTTPS origin; the development API allows local ports 5173 and 4173.

## Focused verification

```bash
npm run build
npm run lint
```

For layout work, inspect loaded desktop and phone pages plus the changed user path against real local data. The existing `make product-visual-check`, `make product-interaction-check` and `scripts/check_product_decision_flow.py` can cover broader geometry and persisted Decision → citation → Evidence → refresh paths without model calls. Run relevant checks rather than automatically rerunning model evaluation for presentation changes. Runtime screenshots, account state and provider output stay outside Git.
