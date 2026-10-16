# SecFusion Product Frontend Contract

Current implementation contract, 2026-10-16. This replaces the former six-space,
mode-selector and material-studio proposals. The current implementation is on `main`.
[README](README.md) owns component/API maintenance details;
[MASTER](design-system/MASTER.md) owns visual execution;
[Wiki acceptance](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Current-Acceptance)
owns verified scope and remaining work. PRD and TD1/2/2A/3 retain domain authority.

## Product purpose

A researcher can discover retained security material, inspect its source, connect
objects and incidents, ask a natural question, continue an investigation and read a
cited report. Content comes from Product API reads. Fixtures, benchmark snapshots,
model drafts and decorative animation cannot stand in for live evidence or task state.

## Navigation

| Primary space | Route under `/product` | Content and actions |
| --- | --- | --- |
| World | `/` | Eight source directions, material discovery, source inspection, processing results, featured incidents/tools and paged Hot CVEs |
| Intelligence | `/intelligence` | Public summaries, recommended/following feeds, Events and Library, object/incident dossiers |
| Ask | `/start` | Natural question, optional scope, saved sessions and per-turn cited report/audit |
| Workspace | `/workspace` | Profile, interests, recent conversations/investigations and Operations |

Investigation, Agent and Observatory routes remain deep links under Workspace.
They are not extra primary spaces. `channel=hot` redirects to World Hot.
Channel, source, object, evidence, session, turn, task and return coordinates survive
URL navigation where supported. Back returns to the originating reading context.

## World and public intelligence

The initial story read is independent of secondary Hot/health/measurement reads.
Loading or failure of one does not erase usable material from another. Source nodes
are labeled keyboard controls; WebGL is supplementary. Source inspection uses a
side panel on desktop and a Sheet on mobile. Processing results distinguish direct
writes, affected objects, accepted facts and unavailable commit detail.

Hot pages show 24 ranked records, an independent resident total and the bounded
ranking offset window. Exact CVE lookup searches the resident pool; free text filters
the loaded page. Cache residency never implies durable Knowledge. Featured incidents
and tools may share the World discovery surface with vulnerabilities.

A source excerpt expands in place instead of repeating below itself. Publication,
date-only publication, observation and acquisition time retain their own semantics.
Missing dates, empty datasets and failed reads are distinct states.

Intelligence recommendations/following use meaningful activity, explicit interests,
source-backed reasons and account-owned feedback. Anonymous discovery is not labeled
personalization. Cursor pagination retains query scope; a library's `as_of` snapshot
is not a complete historical Knowledge reader.

The material library filters eligible public retained documents by type, publisher,
query and multi-label lexical subject. Subject groupings aid browsing and make no
claim of model-derived semantic clustering. Events render evidence-backed chronology
with explicit date basis and curated milestones; tool/research milestones do not
assert an attack occurred. Independent corroboration follows source provenance.

Object dossiers expose Facts, Relationships, Sources and applicable Enrichment.
The graph is bounded, lazy-loaded and evidence-linked, with mobile/keyboard fallback.
Its relationship-lifetime playback is not arbitrary historical-world reconstruction.
Incident revision and Knowledge revision remain different coordinates.

## Questions, investigations and reports

The composer accepts natural language without requiring a mode or CVE. Optional
scope does not create an alternate evidence authority. Suggestions fill the composer;
they do not start a model call. The backend owns routing and bounded query planning.

Question SSE may stream real provider draft bytes and optional transient reasoning.
A draft is visibly unvalidated until the persisted Decision replaces it. No artificial
provider output or delay is used. Stopping receipt aborts the browser connection and
must not claim that server-side work was cancelled.

Each conversation turn reads its immutable Decision reference. A later Case decision
does not overwrite older turns. History uses owner-checked pagination and loading
older content preserves reading position. A selected older turn can load preceding
pages. New conversation clears previous scope and outcome.

Investigation shows findings, sources, activity and any confirmed partial report.
Active, waiting, resolved, cancelled and failed states remain distinguishable. Continue
question retains its owned session/Case path. Concurrent Case writers are rejected by
the backend. Cancel sends the displayed revision; generic manual resume is not shipped.

Reports lead with readable sourced prose and independent summaries where available.
Structured conclusions and technical coordinates remain available in disclosures.
Evidence controls open the exact citation's source, version and permitted passage;
public excerpts require source/artifact visibility. Unavailable reads offer retry.

Private HTML enforces account ownership. Public HTML requires a published briefing
record and revalidates material rights/current revisions. Rendering is deterministic,
escaped and script-denying; reading cannot trigger generation. Model output chooses
validated content/layout fields, never executable HTML or access policy.

## Account and execution boundaries

Identity comes from a server-owned HttpOnly session cookie. Writes use Origin/CSRF;
the browser cannot select another principal. Switching accounts clears cached private
reads, closes streams and refreshes other tabs. Login, profile and preference forms
have loading/error/success states. Email verification, password recovery and OAuth
are not implemented.

Question/create/cancel commands carry stable Idempotency-Key across transport retries;
a deliberate new retry after a terminal failure uses a new key. Cancel includes
If-Match; stale state is a conflict. SSE command replay returns the persisted terminal
result without fabricating the original token stream.

Operations presents actual Task/Role families, per-turn model attempts, local Perception
and external Capability calls separately. Model usage, reserved budget, settlement and
estimated money are distinct. Unknown usage is not zero. Observatory timestamps its
reads and distinguishes configured providers, control ping responses and durable health.
A successful ping does not imply measured uptime or alert delivery.

## Visual and interaction contract

Use local Manrope/Noto Sans SC, shared theme tokens, Phosphor functional icons and
Radix semantics for tabs, dialogs and menus. Reading hierarchy uses typography and
space. Repeated nested boxes, default technical-field labels, glass lighting and
trailing arrows are not the shared art direction.

Abstract pigment development/diffusion uses page-specific composition. It must not
form title glyphs, copied audio waveforms, fake data curves or fabricated progress.
Actual graph relationships and measured trends retain their semantic visualizations.
Respect reduced motion, hidden-tab/offscreen suspension and cleanup on unmount.
Animation cannot remount a conversation or alter model calls, permissions or SSE.

Dark embedded panels set their foreground and background together; selected, hover,
focus and disabled states remain legible. Keyboard focus, dialog containment/return,
Escape, semantic tab navigation and readable mobile widths are required. Graph and
motion engines load on demand without relaxing the static bundle budget.

## Verification and open acceptance

Run from `apps/web`:

```bash
npm run lint
npm run build
node scripts/test-library-presentation.mjs
node scripts/test-material-catalog.mjs
node scripts/test-product-vocabulary.mjs
```

From the repository root, run `scripts/check_product_gate.py --static-only` and
`scripts/check_product_deploy.py`. Live visual/interaction checks need a running stack
and authorized records. Existing desktop/mobile acceptance does not imply a new paid
QA/SSE test or user approval of every page's aesthetic. Remaining product and backend
acceptance is maintained in the Wiki register, not a second outdated delivery checklist.
