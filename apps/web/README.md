# `apps.web` — SecFusion Product Web

The Product Web has four primary spaces: **World, Intelligence, Ask and Workspace**. The [October experience contract](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Product-Web-Experience-2026-10) follows the user's latest reference images and feedback and supersedes earlier UI-cache directions. [`SPEC.md`](SPEC.md) retains the underlying behavior contracts. Product facts come from Application/API reads, never presentation fixtures or benchmark snapshots.

## Navigation and content

| Entry | Opening experience | Deeper interaction |
| --- | --- | --- |
| World `/` | Eight directly selectable source nodes in a live material map | Source inspection, real Hot index/search, evidence formation and dossier handoff |
| Intelligence `/intelligence` | Personalized reading feed; Following, Hot, Events and Library channels | Recommendation reasons/feedback, evidence-backed dossiers, enrichment and incident evolution |
| Ask `/start` | Natural question, integrated desktop composer and compact starters | Full conversation, history drawer, per-turn evidence/model/context/tool audit |
| Workspace `/workspace` | Compact profile, shortcuts, recent conversations and investigations | Interests, profile editor and Operations overview |

`/investigations` opens My investigations as a cursor-paged record list. Selecting a record opens a report-first reader with Findings and Activity tabs; Continue question retains its server-owned conversation. Search filters loaded records with a local draft and a debounced URL replacement, so rapid typing preserves focus and Back restores the correct query. `/agents` and `/observatory` remain directly addressable under Workspace → Operations, preserving task, Skill and source deep links. `/workspace/profile` edits the display name and explicit recommendation interests; `/workspace/operations` reads current task and service state.

Intelligence uses `channel=recommended|following|hot|events|library`. Both feeds use the dedicated activity API: Following restricts results to explicit object relations and title/body topic matches, while Recommendations also ranks relevant discovery. Persistent followed identities sit above the feed; repositories and ordinary PRs are not activities. Default scope is 30 days, with an explicit older-record control. An anonymous reader gets a public discovery feed and a concise sign-in entry, never a false personalized ranking. Activity feedback persists separately from object follows and supports undo. Dossier return links retain channel and category. Source stories request at most the API's 18-record projection limit.

Recommendation items lead with linked titles and available summaries, followed by one recommendation reason. A retained passage is explicitly marked as a source excerpt; identity-only objects stay in the persistent follow shelf. Source inspection and interest feedback are separate actions; Ignore lives in the standard menu with undo. Preview provenance stays attached to its actual EvidenceRef or canonical property origin. Evidence/source totals represent all unique links, not the bounded display list. Publication and observation timestamps use one identified source observation. Hot has its own 20-record paged channel, with the ranking-window limit stated separately from the resident total.

World source controls are the labeled nodes in the scene, with Tooltip explanations and keyboard focus. A desktop inspector or mobile bottom Sheet shows source health and retained material. “Recent knowledge” opens a Sheet of expandable processing results: real object names, fact/relation counts and exact linked commits. Missing change records display pending detail rather than a measured zero. Direct object writes and affected objects have different counts. Closing either Sheet returns focus to its entry control. Source/category filtering uses the same URL contracts; asset acquisition remains on demand.

Object dossiers open with a compact identity and a fact reader. Facts, Relationships, Sources and vulnerability Enrichment are separate Radix tabs, not anchors over one long dashboard. Facts group each claim once with exact evidence links and a contents rail. The relationship view uses a lazily loaded Cytoscape/fCoSE network: bidirectional neighbors, recorded cross-links, expandable nodes, evidence inspection, and relationship-lifetime playback. Initial reads show 16 nodes on phones and at most 40 on wider screens; exploration is capped at 200 loaded objects. Mobile retains the graph and offers fullscreen exploration plus a bottom detail sheet. The accessible object/edge list supports keyboard exploration. Scope and historical metadata limitations are visible below the graph. Sources group actual EvidenceRefs by publisher and open the shared source inspector. The enrichment tab uses a coverage grid whose cells retain the authoritative status and accepted fact refs; it never treats missing or conflicting evidence as complete. Object coordinates remain collapsible. Evidence and view changes preserve the reader instance and citation focus.

Incident evolution reuses the same explorer with an independent incident revision domain. Only retained incident events, actual evidence/claim references and documented source associations create edges. Source event time remains separate from system recording time. Reads are bounded to 200 event and 200 source records; the interface discloses this scope and does not claim a complete historical snapshot.

World keeps source health, acquisition time, original source text and Hot/cache identity separate from durable Knowledge. The Hot index pages 24 ranked source records at a time, up to the API offset cap of 4096, and shows the independent resident total. Exact CVE lookup searches the resident pool; free text filters the loaded page. Sources and materials can be focused without a camera-control vocabulary. Motion follows selection and respects reduced motion. COBE supplies the ambient globe without invented geographic markers; the overlaid source links remain actual material provenance. Animation stops offscreen or in a hidden tab, and unavailable WebGL does not remove the evidence controls.

## Conversation and evidence

Ask sends ordinary natural language. The API resolves intent and builds retrieval queries; the browser does not require a mode or CVE. Optional object scope and provider reasoning are under Answer options. Suggestions fill the editable composer and do not start a model call automatically.

The opening screen has one reading hierarchy: a plain-language purpose, concrete questions drawn from followed interests or general security workflows, and a real recommended source only when its title concerns security. Starters form one compact list of editable questions, without a promotional hero or parallel feature cards. The composer stays visible below them on desktop and phone widths.

The conversation occupies one reading column. On desktop, a new chat places the introduction, composer and compact suggested questions in one 820px column; the opening scrolls only when its contents exceed the available height. Active conversations align messages and the composer to the same column, with symmetric scrollbar space. The mobile opening retains its scrollable suggestions and bottom composer. In an active conversation the composer has its own bottom layout row, so it cannot overlay the transcript. History and audit are Radix dialogs with focus containment, Escape and focus return. Citations in audit load the exact retained evidence version and display publisher identity, object and evidence type. The Evidence inspector opens above the audit drawer, preserving its reading position; dismissing it returns focus to the original citation.

`POST /api/v1/questions/stream` supplies actual provider SSE. React paces received answer and optional reasoning text; reduced motion displays it immediately. Only `report_paragraphs` are previewed as prose, and the arriving JSON remains an unvalidated draft. The validated durable Decision replaces it immediately. Failed streams retain a clearly incomplete draft and allow retry. Stop receiving aborts the browser stream; its copy explicitly states that the server task may continue. The full dialogue requests a 90-second interactive budget.

Account conversations and turns use owner-checked cursor pages. Loading older turns does not autoscroll away from the reader; a selected older turn can load its preceding pages. Each turn reads its immutable `decision_ref`, never the latest mutable Case report. Accepted investigations keep their live Case/SSE state and distinguish active, waiting, resolved and stopped outcomes. A new conversation clears old outcome and scope coordinates.

Completed answers lead with natural report paragraphs and citations. Older Decisions without paragraphs retain their validated conclusions. Structured answer fields stay expandable for audit and QA. The per-turn audit exposes query plans, evidence, linked TaskRuns, model attempts, usage versus budget settlement, ContextManifest, prompt-fragment provenance and tool/runtime events. Raw provider reasoning stays transient rather than pretending to be durable audit data.

Evidence inspection leads with readable source content, the cited version and the original link. Provenance details retain source/Observation identity, locator, trust class and content hash. Public managed documents also expose bounded excerpts from the cited source version. These are source previews; object-level evidence does not imply a sentence-level claim locator. Unavailable reads provide retry actions.

## Accounts and integration

The user flow is register/sign in → edit interests → browse recommendations and evidence → ask/investigate → resume the saved conversation. Server-owned HttpOnly cookies resolve account identity; the browser never sends a chosen principal or stores credentials in localStorage. Account changes clear query state, close old streams and notify other tabs. Questions, Cases and private runtime reads remain owner-scoped.

`PUT /api/v1/auth/profile` updates the display name using the existing session and Origin/CSRF checks. Interests retain the backend limit of 20 keywords and 20 followed objects. Saving preferences invalidates recommendation reads. Email verification, password recovery and OAuth remain separate account-lifecycle work.

Question and Case commands carry `Idempotency-Key`; retries cannot silently create duplicate work. Cancellation sends the displayed Case revision through `If-Match`. A completed SSE replay returns its persisted result without inventing token replay. An unavailable model provider yields an explicit error; source and Knowledge reads remain available.

Operations separates overview, task records and service health. Task rows lead with the user goal, target, outcome and time. Task details show results first, then execution, tools/model calls and context/evidence. A vertical execution tree contains only the selected task and recorded family links; technical identifiers stay in disclosures. Current attention groups related tasks by cause and excludes old failures and non-actionable enrichment stops. Observatory leads with compact hourly trends and source health, followed by source/data/agent/service detail tabs. Dossiers preserve ContextManifest, model attempts, delegation, Skill and Experience links. Observatory distinguishes unavailable reads from measured zeros; refresh retries the live reads without retimestamping cached data. No evaluation scoreboard, frozen-proof screen or guided demonstration belongs in these flows.

## Components and style ownership

`src/components/ui/` contains adapted **shadcn/ui source**, with MIT attribution in [`THIRD_PARTY.md`](src/components/ui/THIRD_PARTY.md). Button, Card, Badge, Input, Avatar, Separator, DropdownMenu, Tabs, Item, Tooltip, ToggleGroup, Sheet, Accordion, Skeleton and Empty are editable project components. Radix owns dialogs, account menus and keyboard tab navigation; Phosphor owns functional icons. There is no extra shadcn runtime package.

The visual system uses neutral white reading surfaces, navy source maps, cobalt interactions and restrained semantic colors. Manrope and locally hosted Noto Sans SC UI subsets provide consistent typography; publisher marks come from locally hosted Simple Icons assets (see asset READMEs for licenses). Publisher names match explicit registered source IDs and complete hostnames, keeping NVD, NIST, CNNVD and CNVD distinct. The header uses a typographic secfusion wordmark without a boxed badge; `BrandMark` supplies the standalone SF monogram; decorative 3D icons no longer fill the World, Intelligence, Ask or Agent role openings.

The global import order in `src/main.tsx` is:

1. `ui.css`: shared light/night tokens, Tailwind utilities and `tw-animate-css`, without a second reset.
2. `product-foundation.css`: tokens, base reset, typography, shared primitives and four-entry shell.
3. `product-spaces.css`: remaining document, shared evidence and detailed runtime/observatory surfaces. Retired dossier hero, orbit, graph and case workspace styles/components are removed as their owners are replaced.
4. `account-space.css`: account controls and authentication.

Detail owners are `components/intelligence/dossier-reader.css`, `knowledge-network.css`, `components/investigations/research-workspace.css` and `investigation-report.css`. Page-local owners are `components/world/world.css`, `components/intelligence/intelligence.css`, `pages/questions-space.css`, `pages/workspace.css`, `pages/personal-space.css`, `components/agents/role-cards.css` and `components/observatory/observatory-overview.css`. Change their actual rules rather than appending competing overrides. The retired legacy stylesheets stay outside the import graph. `lint:css-authority` checks ownership; the source-size guard keeps pages and components bounded.

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

### Shared icons and network renderer

`components/ui/icons.ts` maps stable product names to explicit Phosphor module imports. Regular controls use regular weight; selected primary navigation uses fill. Source logos retain publisher identity. The network renderer is loaded only when a graph is opened; fCoSE fixes existing positions during expansion and the viewport refits on width changes.
