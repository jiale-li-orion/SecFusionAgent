# `apps.web` — SecFusion Product Web

`apps.web` is the six-space user product. [`SPEC.md`](SPEC.md) defines behavior; the project Wiki and the 2026-10-08 UI design cache define the evidence-led visual direction. Product facts come from Application/API read models, never presentation fixtures or benchmark snapshots. Evaluation remains an engineering capability outside user navigation.

## Spaces and user flow

| Space | Product question | Live contract |
| --- | --- | --- |
| WORLD | What is entering and changing now? | Source material, Evidence/Knowledge formation, incidents, Hot resident count and bounded ranking window |
| INTELLIGENCE | What is known about this object? | Dossier, relations, source excerpt, twelve enrichment dimensions, selected-dimension EnrichmentRole task, personal recommendations |
| QUESTIONS | What can the system answer, and why? | Complete account-owned conversation, real model SSE, optional provider reasoning, Decision/citation/Evidence view and context/model/tool/task audit |
| INVESTIGATIONS | What is being followed? | Durable Case, state, activity, citations and continuation |
| AGENTS | What did the system do? | Role/Task/Capability/Skill/Experience read models with measured state |
| OBSERVATORY | Is the service operating? | Measured source/runtime health, queues, Celery worker control probe and explicit unavailable states |

WORLD's Hot resident total is distinct from the bounded displayed ranking window; a list of 64 is not a claim that only 64 CVEs exist. A source story retains the original headline/excerpt and has an evidence/source path. The INTELLIGENCE catalog keeps its retained-document selection separate from the live Hot vulnerability window: the Vulnerabilities filter displays up to 16 real Hot CVEs and the resident total, and its action opens the CVE view with the original Hot coordinate. This does not promote a cache item into durable Evidence. Missing, unknown and conflicting enrichment dimensions remain explicit. QUESTIONS at `/start` renders the entire session turn by turn. DIRECT/RETRIEVE use `POST /api/v1/questions/stream` for actual provider deltas; the draft is visibly unvalidated until the durable Decision arrives. In dialogue, structured answer fields and conclusions lead, while raw supporting facts remain expandable with their citations; narrow screens wrap long source fields instead of clipping the answer. Provider reasoning is opt-in and appears only when emitted by the provider; the current page keeps each emitted stream beside its completed turn through URL updates and turn selection until reload, while the durable audit stores usage/counts and context metadata rather than raw reasoning. VERIFY/INVESTIGATE/WATCH retain the accepted Case and follow its existing investigation SSE. A resolved Case contributes its final citations to the audit rail, which loads every owner-checked TaskRun linked by the Case activity feed: InvestigationRole and DecisionRole model calls, contexts, prompt-fragment metadata and runtime events remain separately inspectable. Clicking citations opens the Evidence record. A session URL restores the same Decision or Case after refresh and resolves the target object's human-readable identifier. New conversation clears the prior target and result.

Long account conversations and sessions load older entries on demand through owner-checked cursor pages. When a Case has a final Decision, its report leads with generated natural paragraphs and paragraph-level Evidence links; the complete structured Decision remains expandable for audit and QA. Decisions without retained paragraphs clearly say so and keep their validated conclusions available in the audit section.

The INTELLIGENCE Incidents filter shows a separate candidate watch from live incident signals. Its count screens out obvious general news from the broader raw signal pool, and every card remains visibly a candidate until durable Incident promotion. Selecting a candidate opens its WORLD signal/source path and original link rather than an empty Incident dossier. WORLD uses the same projection in its Incidents direction, including source-filtered neighboring materials.

WORLD only offers the multi-step investigation action when the focused material has a canonical object or CVE target. A candidate without one opens its signal/provenance detail and original source instead of sending the user to an unlaunchable investigation form. The SPA router keeps the configured base URL's trailing slash, so returning to WORLD at `/product/` survives a browser refresh in development.

The user flow is register/sign in → save interests → inspect evidence-based recommendations and feedback → ask/investigate → resume a recent conversation → sign out/sign in again. `/auth?mode=login|register&returnTo=...` uses a same-origin account session. Protected actions and private reads require the server session; the browser does not send a user-selected principal. Account changes clear query state and close old streams.

Submitting a free-text INTELLIGENCE search issues a request for the exact current input before opening an object. The deferred suggestion list is only a preview; pressing Enter while it is updating cannot open a result from an earlier query.

## Visual ownership

`src/main.tsx` imports the active CSS in order:

1. `product-foundation.css`: tokens, typography, interaction primitives, shell and shared responsive rules.
2. `product-spaces.css`: the distinct WORLD, INTELLIGENCE, INVESTIGATIONS, AGENTS and OBSERVATORY compositions.
3. `account-space.css`: the account realm and auth control surfaces.

`src/pages/questions-space.css` owns the QUESTIONS workspace and is imported only by its page component.

The retired `styles.css`, `cinematic.css`, `cinematic-seams.css`, `surface-authority.css` and `layout-authority.css` remain out of the import graph. Do not restart an override cascade. `npm run lint:css-authority` enforces active ownership. Main identity objects use shared WebGL materials with SVG fallback and reduced-motion behavior; small cards reuse the same visual identities without opening extra GL contexts. Every animated live fact must resolve to a real source, state or measurement.

Identity assets live under `src/components/instrument/`: `BrandMark` is the evidence-aperture product mark; `ProductGlyph` gives the six spaces and eight source categories distinct machined seals; `SourceSeal` combines a category seal with a source-name monogram in WORLD source inspection, without claiming to reproduce a publisher's official logo. `HeroArtifact` has separate WebGL geometry for the three roles and all eight source categories, with `RoleSigil` / `SourceArtwork` as material-matched static fallbacks. The role accents are identity cues only; active counts and source health continue to come from live reads. Selecting the vulnerability source direction can focus a real Hot vulnerability, while the Hot-only versus durable Evidence boundary remains explicit in the provenance path.

## Local integration

Start the API after infrastructure/migrations are available:

```bash
.venv/bin/uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

Then start the Web process:

```bash
cd apps/web
npm ci
npm run dev
```

Open `http://localhost:5173/product/`. Set `SECFUSION_API_PROXY=http://127.0.0.1:8001` if the API is on another port. Vite proxies `/api`; production Nginx serves the same-origin paths. Configure `SECFUSION_AUTH_ALLOWED_ORIGINS` for the exact external HTTPS origin when the reverse proxy changes the browser origin. An absent model provider yields an explicit dependency error for model-backed QA; source/Knowledge reads remain available.

The API routes are documented in [`../api/README.md`](../api/README.md); account/session and personalization behavior is specified in the [Wiki](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Product-Accounts-and-Personalization). The site has no guided competition demo, frozen-proof screen or manufactured delay.

## Focused checks

```bash
npm run build
npm run lint
make product-visual-check
make product-interaction-check
```

The browser gates read the live app at the configured local Product URL and inspect desktop/mobile geometry and controls. `uv run python scripts/check_product_decision_flow.py` covers persisted Decision → citation → Evidence → refresh without model calls. Run the relevant gate when changing shell/layout or a cross-page interaction; screenshots and runtime data stay outside Git.
