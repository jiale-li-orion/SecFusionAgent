# `apps.web` — SecFusion Product Web

The Product Web has four primary spaces: **World, Intelligence, Ask and Workspace**. The [October experience contract](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Product-Web-Experience-2026-10) defines navigation, reading and interaction contracts. [`SPEC.md`](SPEC.md) retains the underlying behavior contracts. Product facts come from Application/API reads, never presentation fixtures or benchmark snapshots.

## Navigation and content

| Entry | Opening experience | Deeper interaction |
| --- | --- | --- |
| World `/` | Eight directly selectable source nodes in a live material map | Source inspection, real Hot index/search, evidence formation and dossier handoff |
| Intelligence `/intelligence` | Public briefings and personalized reading; Following, Events and Library channels | Recommendation reasons/feedback, evidence-backed dossiers, enrichment and incident evolution |
| Ask `/start` | Natural question, integrated desktop composer and compact starters | Full conversation, history drawer, per-turn evidence/model/context/tool audit |
| Workspace `/workspace` | Compact profile, shortcuts, recent conversations and investigations | Interests, profile editor and Operations overview |

`/investigations` opens My investigations as a cursor-paged record list. Selecting a record opens a report-first reader with Findings and Activity tabs; Continue question retains its server-owned conversation. Search filters loaded records with a local draft and a debounced URL replacement, so rapid typing preserves focus and Back restores the correct query. `/agents` and `/observatory` remain directly addressable under Workspace → Operations, preserving task, Skill and source deep links. `/workspace/profile` edits the display name and explicit recommendation interests; `/workspace/operations` reads current task and service state.

Intelligence uses `channel=recommended|following|events|library`. Legacy `channel=hot` links redirect to World’s Hot view. Both feeds use the dedicated activity API: Following restricts results to explicit object relations and title/body topic matches, while Recommendations also ranks relevant discovery. Persistent followed identities sit above the feed; repositories and ordinary PRs are not activities. Default scope is 30 days, with an explicit older-record control. An anonymous reader gets a public discovery feed and a concise sign-in entry, never a false personalized ranking. Activity feedback persists separately from object follows and supports undo. Dossier return links retain channel and category. Source stories request at most the API's 18-record projection limit.

Recommendation items lead with linked titles and available summaries, followed by one recommendation reason. A retained passage is explicitly marked as a source excerpt; identity-only objects stay in the persistent follow shelf. Source inspection and interest feedback are separate actions; Ignore lives in the standard menu with undo. Preview provenance stays attached to its actual EvidenceRef or canonical property origin. Evidence/source totals represent all unique links, not the bounded display list. Publication and observation timestamps use one identified source observation. Hot discovery lives in World, with the ranking-window limit stated separately from the resident total.

World source controls are the labeled nodes in the scene, with Tooltip explanations and keyboard focus. A desktop inspector or mobile bottom Sheet shows source health and retained material. “Recent knowledge” opens a Sheet of expandable processing results: real object names, fact/relation counts and exact linked commits. Missing change records display pending detail rather than a measured zero. Direct object writes and affected objects have different counts. Closing either Sheet returns focus to its entry control. Source/category filtering uses the same URL contracts; asset acquisition remains on demand.

Object dossiers open with a compact identity and a fact reader. Facts, Relationships, Sources and vulnerability Enrichment are separate Radix tabs, not anchors over one long dashboard. Facts group each claim once with exact evidence links and a contents rail. The relationship view uses a lazily loaded Cytoscape/fCoSE network: bidirectional neighbors, recorded cross-links, expandable nodes, evidence inspection, and relationship-lifetime playback. Initial reads show 16 nodes on phones and at most 40 on wider screens; exploration is capped at 200 loaded objects. Mobile retains the graph and offers fullscreen exploration plus a bottom detail sheet. The accessible object/edge list supports keyboard exploration. Scope and historical metadata limitations are visible below the graph. Sources group actual EvidenceRefs by publisher and open the shared source inspector. The enrichment tab uses a coverage grid whose cells retain the authoritative status and accepted fact refs; it never treats missing or conflicting evidence as complete. Object coordinates remain collapsible. Evidence and view changes preserve the reader instance and citation focus.

Incident evolution reuses the same explorer with an independent incident revision domain. Only retained incident events, actual evidence/claim references and documented source associations create edges. Source event time remains separate from system recording time. Reads are bounded to 200 event and 200 source records; the interface discloses this scope and does not claim a complete historical snapshot.

World keeps source health, acquisition time, original source text and Hot/cache identity separate from durable Knowledge. The Hot index pages 24 ranked source records at a time, up to the API offset cap of 4096, and shows the independent resident total. Exact CVE lookup searches the resident pool; free text filters the loaded page. Sources and materials can be focused without a camera-control vocabulary. Motion follows selection and respects reduced motion. COBE supplies the ambient globe without invented geographic markers; the overlaid source links remain actual material provenance. Animation stops offscreen or in a hidden tab, and unavailable WebGL does not remove the evidence controls.

## Library, events and reports

`MaterialLibrary` reads `/api/v1/intelligence/library` with a default 48-item page and carries `as_of` into later pages. Type, source and multi-label subject facets describe eligible public retained material. The displayed clusters are deterministic browsing aids, not inferred relationships or confirmed facts. `EventLibrary` renders durable incidents along their evidence-linked chronology with shared developing-field motion; it does not fabricate missing event dates.

Reviewed public briefings expose their independent summary directly in the reading feed. Opening public or private HTML reports is read-only. The old Intelligence Hot tab redirects to the World Hot view, where featured incidents/tools share discovery with CVEs.

`WorldStoryCard` expands the existing excerpt instead of repeating it in evidence details. The dark `.world-main` explicitly sets both background and foreground from its scoped theme, preventing inherited light-page text from disappearing on a dark surface. Browser validation covered normal, selected and hovered Hot rows; production build and CSS ownership checks passed.

## Conversation and evidence

Ask sends ordinary natural language. The API resolves intent and builds retrieval queries; the browser does not require a mode or CVE. Optional object scope and provider reasoning are under Answer options. Suggestions fill the editable composer and do not start a model call automatically.

The opening screen has one reading hierarchy: a plain-language purpose, concrete questions drawn from followed interests or general security workflows, and a real recommended source only when its title concerns security. Starters are editable questions in an open, staggered composition. Desktop places the composer before the suggestions; phones retain the bottom composer.

The conversation occupies one reading column. On wide desktops, a new chat places the introduction and composer in the primary column with suggestions in a right rail; tablets stack those sections. The opening scrolls only when its contents exceed the available height. Active conversations align messages and the composer to the same column, with symmetric scrollbar space. The mobile opening retains its scrollable suggestions and bottom composer. In an active conversation the composer has its own bottom layout row, so it cannot overlay the transcript. History and audit are Radix dialogs with focus containment, Escape and focus return. Citations in audit load the exact retained evidence version and display publisher identity, object and evidence type. The Evidence inspector opens above the audit drawer, preserving its reading position; dismissing it returns focus to the original citation.

`POST /api/v1/questions/stream` supplies actual provider SSE. React paces received answer and optional reasoning text; reduced motion displays it immediately. Only `report_paragraphs` are previewed as prose, and the arriving JSON remains an unvalidated draft. The validated durable Decision replaces it immediately. Failed streams retain a clearly incomplete draft and allow retry. Stop receiving aborts the browser stream; its copy explicitly states that the server task may continue. The full dialogue requests a 90-second interactive budget.

Account conversations and turns use owner-checked cursor pages. Loading older turns does not autoscroll away from the reader; a selected older turn can load its preceding pages. Each turn reads its immutable `decision_ref`, never the latest mutable Case report. Accepted investigations keep their live Case/SSE state and distinguish active, waiting, resolved and stopped outcomes. A new conversation clears old outcome and scope coordinates.

Completed answers lead with natural report paragraphs and citations. Older Decisions without paragraphs retain their validated conclusions. Structured answer fields stay expandable for audit and QA. The per-turn audit exposes query plans, evidence, linked TaskRuns, model attempts, usage versus budget settlement, ContextManifest, prompt-fragment provenance and tool/runtime events. Raw provider reasoning stays transient rather than pretending to be durable audit data.

Provider payment failure appears as a service-credit interruption in the question audit and task detail; the raw lifecycle code remains in technical details. A failed model call does not become an evidence judgment or erase task material already recorded.

Evidence inspection leads with readable source content, the cited version and the original link. Provenance details retain source/Observation identity, locator, trust class and content hash. Public managed documents also expose bounded excerpts from the cited source version. These are source previews; object-level evidence does not imply a sentence-level claim locator. Unavailable reads provide retry actions.

## Accounts and integration

The user flow is register/sign in → edit interests → browse recommendations and evidence → ask/investigate → resume the saved conversation. Server-owned HttpOnly cookies resolve account identity; the browser never sends a chosen principal or stores credentials in localStorage. Account changes clear query state, close old streams and notify other tabs. Questions, Cases and private runtime reads remain owner-scoped.

`PUT /api/v1/auth/profile` updates the display name using the existing session and Origin/CSRF checks. Interests retain the backend limit of 20 keywords and 20 followed objects. Saving preferences invalidates recommendation reads. Email verification, password recovery and OAuth remain separate account-lifecycle work.

Question and Case commands carry `Idempotency-Key`; retries cannot silently create duplicate work. Cancellation sends the displayed Case revision through `If-Match`. A completed SSE replay returns its persisted result without inventing token replay. An unavailable model provider yields an explicit error; source and Knowledge reads remain available.

Operations separates overview, task records and service health. Open task entries lead with the user goal, target, outcome and time. Task details show results first, then execution, tools/model calls and context/evidence. A vertical execution tree contains only the selected task and recorded family links; technical identifiers stay in disclosures. Current attention groups related tasks by cause and excludes old failures and non-actionable enrichment stops. Observatory leads with compact hourly trends and source health, followed by source/data/agent/service detail tabs. Dossiers preserve ContextManifest, model attempts, delegation, Skill and Experience links. Observatory distinguishes unavailable reads from measured zeros; refresh retries the live reads without retimestamping cached data. No evaluation scoreboard, frozen-proof screen or guided demonstration belongs in these flows.

## Components and style ownership

The shell uses `LazyMotion` with asynchronously loaded `domMax` features, retaining
route transitions and navigation layout animation without including the complete
engine in the initial script graph. Account controls and the secondary Workspace
navigation are separately loaded; account loading remains explicitly announced.
The Product static gate checks the current component owners (Radix tab semantics,
EvidenceAtlas reduced motion and report-reader continuation) rather than retired
CSS class names. Its initial-script byte budget remains unchanged.

Task detail now reads durable `PerceptionEvent` records separately from external `CapabilityInvocation` calls. The Tools & models tab shows local inspect/search/trace actions, their physical read operators and citation count before external capability calls and model attempts. An empty external-call list no longer suggests that the investigation made no local reads. The execution timeline labels `EvidenceFound` as a completed perception because a read may return no citable evidence.
When a source supports partial findings but cannot satisfy the full EvidenceNeed contract, the timeline shows that the findings were saved and the evidence gap remains. Bounded stops distinguish an unmet evidence contract from a rejected state write and a repeated read.

`src/components/ui/` contains adapted **shadcn/ui source**, with MIT attribution in [`THIRD_PARTY.md`](src/components/ui/THIRD_PARTY.md). Button, Card, Badge, Input, Avatar, Separator, DropdownMenu, Tabs, Item, Tooltip, ToggleGroup, Sheet, Accordion, Skeleton and Empty are editable project components. Radix owns dialogs, account menus and keyboard tab navigation; Phosphor owns functional icons. There is no extra shadcn runtime package.

The current visual direction is a light research workspace with a warm paper canvas and graphite actions. Ordinary reading groups use type scale and spacing, with an open lead-and-columns composition for intelligence and task records; repeated row rules and nested cards are not the default. The World atlas keeps a charcoal-green field. Manrope and locally hosted Noto Sans SC UI are used throughout, including graph labels and audit references. Small metadata uses a shared 12px floor; scattered tiny labels and default monospace styling are removed. The Chinese subset covers 6,763 common Han characters plus static UI text. Publisher marks retain their official local assets. The header becomes bottom navigation at 850px and below.

`ui.css` owns complete day/night variables for text, surfaces, borders, focus, status colors and three elevation levels. Shared controls consume those variables instead of defining their own blue palettes. `UiThemeProvider` carries the presentation theme through React portals; Sheet, Dropdown, Tooltip, conversation drawers and the Evidence inspector explicitly apply it to their content. The header, account menu and application canvas use the same light theme across all four spaces. A shared Motion layout indicator follows the selected navigation item, switching to the mobile bottom bar at 850px. Search and page-owned portals inherit their page theme. Shared surfaces, neutral secondary text and semantic status styles extend to the page background and evidence controls; legacy native-button rules no longer override shadcn buttons. Ask no longer changes theme after the first message: new-chat selectors control layout only, and saved answers, reports and process details remain readable on the same light surface.

The composer separates the text area and action toolbar; enabled send, disabled send and stop have distinct states. Suggestions remain editable question entries with no numbered icon boxes. Citation rows retain source identity, index and title. Task audit surfaces use the same semantic status palette and inherit their reading surface instead of forcing a blue-black card into light pages. Existing routes, subscriptions, graph relations, audit data and SSE behavior are unchanged.

`ActionIndicator` now supplies only a disclosure chevron. Repeated decorative forward arrows and icon backplates are removed from reading, suggestion, workspace and task rows. `productVocabulary.ts` presents readable skill names, lifecycle states, source categories and operating metrics without changing API values or links. Raw identifiers remain available inside explicit technical details; public identifiers and source prose remain accurate.

The earlier 2026-10-13 visual pass passed production build, ESLint, CSS-authority and source-size checks. Browser inspection covered the four spaces at 390/768/1440px, a real relationship and its retained evidence, source selection, task details, editable question starters, history-drawer focus return and reduced motion. No new paid question was submitted. The supplied legacy session returned 403 for the inspection account, so this visual pass does not claim fresh end-to-end validation of that conversation or provider streaming. The existing lazy-loaded graph bundle still triggers Vite's 500 KB size warning.

The global import order in `src/main.tsx` is:

1. `ui.css`: shared light/night tokens, Tailwind utilities and `tw-animate-css`, without a second reset.
2. `product-foundation.css`: tokens, base reset, typography, shared primitives and four-entry shell.
3. `product-spaces.css`: remaining document, shared evidence and detailed runtime/observatory surfaces. Retired dossier hero, orbit, graph and case workspace styles/components are removed as their owners are replaced.
4. `account-space.css`: account controls and authentication.

Detail owners are `components/intelligence/dossier-reader.css`, `knowledge-network.css`, `components/investigations/research-workspace.css` and `investigation-report.css`. Page-local owners are `components/world/world.css`, `components/intelligence/intelligence.css`, `pages/questions-space.css`, `pages/workspace.css`, `pages/personal-space.css`, `components/agents/role-cards.css` and `components/observatory/observatory-overview.css`. Change their actual rules rather than appending competing overrides. The retired legacy stylesheets stay outside the import graph. `lint:css-authority` checks ownership; the source-size guard keeps pages and components bounded.

The user approved the developing-pigment motion base on 2026-10-15 and requested page-specific applications. `DevelopingField` renders abstract pigment deposits through a shared grain-and-diffusion shader. The later typography-based version was rejected and removed; the pre-lettering deposit and diffusion parameters are restored. `developingProfiles.ts` gives each page or channel its own deposit geometry, migration, exposure origin and focus convergence, while preserving the question composition. No enlarged glyphs or decorative data traces are used. The welcome imprint responds to input focus, typing and suggestions. Each page preserves its existing data and action order; decorative motion never claims execution progress or certainty. See [the design system](design-system/MASTER.md).

The renderer caps resolution and frame rate, pauses offscreen or in hidden tabs, renders statically under reduced motion, and releases GPU resources and listeners on unmount. A static fallback covers unavailable/lost WebGL contexts. Shared Card and Item defaults are open surfaces; legacy frames, row fills and repeated internal-link arrows were also removed from evidence, runtime, source, coverage and question components.

Validation includes desktop/mobile route checks, task detail, evidence inspector, source/service tabs, typography, focus-driven motion, reduced motion and offscreen suspension. No paid question was submitted. Technical verification does not imply user acceptance of every page.

### Shared icons and network renderer

`components/ui/icons.ts` maps stable product names to explicit Phosphor module imports. Regular controls use regular weight; selected primary navigation uses fill. Source logos retain publisher identity. The network renderer is loaded only when a graph is opened; fCoSE fixes existing positions during expansion and the viewport refits on width changes.

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

The latest validation scope includes 18 routes/views at 390 and 1440px, plus login/registration, graph, source and coverage views. Checks cover horizontal overflow, readable typography, semantic label mapping and interactive/reduced-motion behavior. Private investigation and conversation contents require an authorized record; this pass does not claim fresh provider/SSE validation. Build, lint and focused vocabulary checks are run after the final changes. The existing lazy graph chunk retains its 500 KB warning. This implementation is included in `main`; dated browser observations are acceptance evidence for their tested revision, not a fresh live-provider check.

Additional deterministic presentation checks:

```bash
node scripts/test-library-presentation.mjs
node scripts/test-material-catalog.mjs
node scripts/test-product-vocabulary.mjs
```
