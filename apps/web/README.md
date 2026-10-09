# `apps.web` — SecFusion Product Web

`apps.web` is the six-space user product. [`SPEC.md`](SPEC.md) defines behavior; the project Wiki and the 2026-10-08 UI design cache define the evidence-led visual direction. Product facts come from Application/API read models, never presentation fixtures or benchmark snapshots. Evaluation remains an engineering capability outside user navigation.

## Spaces and user flow

| Space | Product question | Live contract |
| --- | --- | --- |
| WORLD | What is entering and changing now? | Source material, Evidence/Knowledge formation, incidents, Hot resident count and bounded ranking window |
| INTELLIGENCE | What is known about this object? | Dossier, relations, source excerpt, twelve enrichment dimensions, selected-dimension EnrichmentRole task, personal recommendations with reason-level evidence links and progressive browsing |
| QUESTIONS | What can the system answer, and why? | Complete account-owned conversation, real model SSE, optional provider reasoning, Decision/citation/Evidence view and context/model/tool/task audit |
| INVESTIGATIONS | What is being followed? | Durable Case, state, activity, citations and continuation |
| AGENTS | What did the system do? | Recent Role/Task topology, cursor-browsable Task history, context/model/capability audit and Skill/Experience memory |
| OBSERVATORY | Is the service operating? | Measured source/runtime health, queues, Celery worker control probe and explicit unavailable states |

WORLD's Hot resident total is distinct from the displayed ranking page. A source story retains the original headline/excerpt and has an evidence/source path. The INTELLIGENCE catalog keeps its retained-document selection separate from the live Hot vulnerability window: the Vulnerabilities filter displays up to 16 real Hot CVEs and the resident total, and its action opens the CVE view with the original Hot coordinate. This does not promote a cache item into durable Evidence. Missing, unknown and conflicting enrichment dimensions remain explicit. QUESTIONS at `/start` renders the entire session turn by turn. DIRECT/RETRIEVE use `POST /api/v1/questions/stream` for actual provider deltas; the draft is visibly unvalidated until the durable Decision arrives. In dialogue, structured answer fields and conclusions lead, while raw supporting facts remain expandable with their citations; narrow screens wrap long source fields instead of clipping the answer. Provider reasoning is opt-in and appears only when emitted by the provider; the current page keeps each emitted stream beside its completed turn through URL updates and turn selection until reload, while the durable audit stores usage/counts and context metadata rather than raw reasoning. VERIFY/INVESTIGATE/WATCH retain the accepted Case and follow its existing investigation SSE. A resolved Case contributes its final citations to the audit rail, which loads every owner-checked TaskRun linked by the Case activity feed: InvestigationRole and DecisionRole model calls, contexts, prompt-fragment metadata and runtime events remain separately inspectable. Clicking citations opens the Evidence record. A session URL restores the same Decision or Case after refresh and resolves the target object's human-readable identifier. New conversation clears the prior target and result.
WORLD's source directions show actual source and healthy counts instead of naming an arbitrary first source. The source inspector separates health, latest successful acquisition, next due time and current error; it participates in the layout as a side column on wide screens and a full-width section below the canvas on narrower screens, without covering the source artwork.
OBSERVATORY distinguishes a failed source, Agent, or system read from an in-progress read in its pulse, chart, spectrum and dependency panels. The top refresh control retries the affected reads; previously measured data retains its timestamp if still cached. An empty hourly series shows an unavailable peak rather than a measured zero.
WORLD's four view-specific empty and failure states distinguish source health, Hot residency, processing records and source signals. The processing field can expand all records returned by the current API projection rather than stopping at its first five rows.
The INTELLIGENCE vulnerability selection offers a direct route to WORLD's paged Hot index, so the 16-item editorial shelf is not the end of Hot discovery.

Long account conversations and sessions load older entries on demand through owner-checked cursor pages. During genuine provider SSE, the unvalidated draft previews arriving report paragraphs as they stream; machine-readable conclusion fields are not flashed as prose. Completed Question turns and final Cases lead with generated natural paragraphs and paragraph-level Evidence links; the complete structured Decision remains expandable for audit and QA. Older Question turns without retained paragraphs lead with validated conclusions, with raw answer fields in a disclosure. Cases without retained paragraphs say so and keep validated conclusions available in the audit section.

The dialogue reveals received SSE content and optional provider reasoning a character at a time in React, with a small catch-up allowance when a network chunk is large. Reduced-motion users see received text immediately. The final durable Decision replaces the draft immediately on completion. A terminal stream error retains any partial text as an explicitly incomplete, unvalidated draft; the same question can be retried with a fresh idempotency key. When the server has a failed TaskRun coordinate, the audit rail loads its owner-checked model/context/runtime trace even though no completed conversation turn was saved. The full dialogue asks for a 90-second interactive budget so a still-streaming report is not cut off at the previous 30-second limit.
The streaming report preview reads only the `report_paragraphs` array, so later JSON fields cannot appear as report prose before the final Decision replaces the draft.
The Question audit rail links each owner-checked TaskRun to its complete AGENTS dossier and explicitly flags partial Task read failures. Investigation turns display their actual active/waiting/resolved/stopped state instead of treating every unfinished Case as an evidence gap. The composer only labels a session saved after it exists.
AGENTS task activity exposes every materialized Skill link. Learning records show all governance references and evaluation fields returned by the read, including those beyond earlier compact previews.
Task dossiers enumerate every persisted PromptAssemblyRecord, including each materialized Skill and capability view, percept count, digest, and inspectable prompt-fragment provenance metadata.
Evidence groups in INTELLIGENCE and INVESTIGATIONS can reveal every linked citation beyond the initial compact set. Both evidence inspectors offer a read retry, and the Case evidence lens shows the source-bound claim value when the Evidence target is a Claim.
INTELLIGENCE keeps the graph canvas to a readable ten-node preview while its relation ledger exposes every relation in the loaded window with Evidence and target actions. The graph read can expand from 24 to the API's 64-relation limit when more edges exist; the loaded/total count remains visible.
The full Case workspace can expand all confirmed findings, conflicts, unknowns and open evidence needs returned by the Case read. Expanding execution-event history shows every event returned by the activity read instead of stopping after 32.
Case activity events now open their linked Evidence records directly and link to their TaskRun dossier when the event carries a task run ID.
The Case continuation composer accepts multiline questions. A failed submission keeps the draft intact and shows a retryable inline error without adding a false conversation turn. Case targets can expand beyond the first six linked objects.
The audit rail can retry failed TaskRun and saved Case activity reads. Live Case SSE events expose newly linked TaskRuns immediately while the saved activity feed refreshes; a dropped live connection is labeled without hiding already saved events.

The new-conversation composer leads the workspace and explains each of the five execution paths. Target search uses the existing Intelligence object search, accepts a selected canonical object or a complete CVE ID, and rejects unrecognized free text instead of silently dropping it. Transcript autoscroll is scoped to its own scroll container and only follows a new latest turn; loading older turns does not move the browser page. The model audit row distinguishes provider-reported token usage from unavailable usage and labels conservative budget settlement separately.

The INTELLIGENCE Incidents filter shows a separate candidate watch from live incident signals. Its count screens out obvious general news from the broader raw signal pool, and every card remains visibly a candidate until durable Incident promotion. Selecting a candidate opens its WORLD signal/source path and original link rather than an empty Incident dossier. WORLD uses the same projection in its Incidents direction, including source-filtered neighboring materials.

WORLD only offers the multi-step investigation action when the focused material has a canonical object or CVE target. A candidate without one opens its signal/provenance detail and original source instead of sending the user to an unlaunchable investigation form. The SPA router keeps the configured base URL's trailing slash, so returning to WORLD at `/product/` survives a browser refresh in development.
Durable Incident material without a canonical object now opens a targetless RETRIEVE question from WORLD or its INTELLIGENCE dossier. The dossier uses the current incident summary as its visible headline and prefilled question context, falling back to incident type only when no summary exists. QUESTIONS keeps a link to the originating material and states that this route searches existing evidence rather than binding the Incident as a verified investigation target. Object- and CVE-backed material still launches target-bound investigation.

The WORLD material atlas uses orbit placement on wide screens and a separate focus-then-neighbours composition below 600px. On narrow screens the source cards follow the central artifact in a grid, keeping their labels and actions clear of the 3D object and its category caption.

The INVESTIGATIONS empty state provides a direct verification action and a readable preview of the Case contents. It uses the active space stylesheet at desktop and mobile widths; no legacy blueprint CSS is required for an account with no Cases.
The Case index loads older account-owned investigations through the existing API cursor. Expanding the current batch and fetching older batches are separate actions; a directly linked older Case is inserted into the visible index after its owner-checked detail loads.
The AGENTS Task dossier now reads its persisted ContextManifest and every ModelAttempt. Evidence and object references open their corresponding INTELLIGENCE views; relation, retrieval, policy, capability, and budget coordinates remain inspectable. Each model card separates provider-reported tokens from budget settlement, including upper-bound fallback, overrun, and release before dispatch.
The topology remains a recent-execution view; the history column reads owner-checked Task pages with a stable cursor so older runs can still be found and opened. A directly linked older Task appears beside the recent topology even before its history page is loaded, and an inaccessible Task reports a clear read error. An Incident dossier shows its own content without appending the INTELLIGENCE catalog and personal recommendation desk underneath it. The Incident archive rail stays visible when its index read fails and offers a retry; direct Incident links show a loading state before the dossier arrives. A failed Knowledge read no longer leaves an "opening object" skeleton beside its error.

The user flow is register/sign in → save interests → inspect evidence-based recommendations and feedback → ask/investigate → resume a recent conversation → sign out/sign in again. `/auth?mode=login|register&returnTo=...` uses a same-origin account session. Protected actions and private reads require the server session; the browser does not send a user-selected principal. Account changes clear query state and close old streams.

Submitting a free-text INTELLIGENCE search issues a request for the exact current input before opening an object. The deferred suggestion list is only a preview; pressing Enter while it is updating cannot open a result from an earlier query.

WORLD's Hot ranking presents 24 source cards per page, limited by the API's offset cap of 4096, with a separate resident total. Its page count shows the browsable ranking window rather than implying every resident record is paged. An exact CVE searches the entire resident Hot pool through `/api/v1/world/hot/search`; title or mechanism text filters only the loaded page. Both result types keep their Hot-cache identity separate from durable Knowledge.
The WORLD atlas also previews four current Hot records beside its source materials and links directly to their selected position in the paged Hot index. The preview count is editorial; the resident total and full-CVE search remain the scope indicators.
The atlas' latest knowledge-commit label distinguishes a real empty change window from loading and read failure; a failed read can be retried in place.

## Visual ownership

`src/main.tsx` imports the active CSS in order:

1. `product-foundation.css`: tokens, typography, interaction primitives, shell and shared responsive rules.
2. `product-spaces.css`: the distinct WORLD, INTELLIGENCE, INVESTIGATIONS, AGENTS and OBSERVATORY compositions.
3. `account-space.css`: the account realm and auth control surfaces.

`src/pages/questions-space.css` owns the QUESTIONS workspace and is imported only by its page component.

The retired `styles.css`, `cinematic.css`, `cinematic-seams.css`, `surface-authority.css` and `layout-authority.css` remain out of the import graph. Do not restart an override cascade. `npm run lint:css-authority` enforces active ownership. Main identity objects use shared WebGL materials with SVG fallback and reduced-motion behavior; small cards reuse the same visual identities without opening extra GL contexts. Every animated live fact must resolve to a real source, state or measurement.

Identity assets live under `src/components/instrument/`: `BrandMark` is the evidence-aperture product mark; `ProductGlyph` gives the six spaces and eight source categories distinct machined seals; `SourceSeal` combines a category seal with a source-name monogram in WORLD source inspection, without claiming to reproduce a publisher's official logo. `HeroArtifact` has separate WebGL geometry for the three roles and all eight source categories, with `RoleSigil` / `SourceArtwork` as material-matched static fallbacks. The role accents are identity cues only; active counts and source health continue to come from live reads. Selecting the vulnerability source direction can focus a real Hot vulnerability, while the Hot-only versus durable Evidence boundary remains explicit in the provenance path.

## Local integration

Question (including SSE) and Case cancellation submissions keep a client `Idempotency-Key` for the same unfinished request and clear it after a successful response. Cancellation sends the displayed Case revision in `If-Match`, so a stale tab receives a conflict instead of cancelling an updated investigation. A completed SSE replay returns its persisted final result without pretending to reproduce earlier model token deltas.

`make dev-runtime-up` starts the API as a health-checked Compose service on
`127.0.0.1:8001` alongside the durable workers. For API-only development after
infrastructure/migrations are available:

```bash
.venv/bin/uvicorn apps.api.main:app --host 127.0.0.1 --port 8001
```

Then start the Web process:

```bash
cd apps/web
npm ci
npm run dev
```

Open `http://localhost:5173/product/`. Vite proxies `/api` and `/health` to the
Compose API on `127.0.0.1:8001` by default; set `SECFUSION_API_PROXY` when the API
uses another address. Production Nginx serves the same-origin paths. Configure
`SECFUSION_AUTH_ALLOWED_ORIGINS` for the exact external HTTPS origin when the
reverse proxy changes the browser origin. The development Compose API already
allows the default local Vite origins on ports 5173 and 4173, so account writes
work through Vite without weakening the Origin/CSRF guard. An absent model provider yields an
explicit dependency error for model-backed QA; source/Knowledge reads remain
available.

The API routes are documented in [`../api/README.md`](../api/README.md); account/session and personalization behavior is specified in the [Wiki](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Product-Accounts-and-Personalization). The site has no guided competition demo, frozen-proof screen or manufactured delay.

## Focused checks

```bash
npm run build
npm run lint
make product-visual-check
make product-interaction-check
```

The browser gates read the live app at the configured local Product URL and inspect desktop/mobile geometry and controls. `uv run python scripts/check_product_decision_flow.py` covers persisted Decision → citation → Evidence → refresh without model calls. Run the relevant gate when changing shell/layout or a cross-page interaction; screenshots and runtime data stay outside Git.
