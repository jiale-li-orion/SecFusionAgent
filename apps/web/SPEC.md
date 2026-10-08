# SecFusion Product Frontend Spec v2

> Status: **Production product contract, updated 2026-10-08**
> Date: 2026-10-04
> Owner: Product App (`apps/web`)
> Supersedes: 2026-10-04 narrow Ask/Investigation/Intelligence draft

## 2026-10-08 product direction

The user requires a real operating product. This supersedes earlier competition presentation requirements: no demo routes/guided paths, no frozen proof view, no manufactured waiting sequence. Evaluation remains backend-owned and outside Product navigation. OBSERVATORY is live operations; all animations must support actual focus, state changes or traceable runtime events. The UI-design-cache remains the art-direction authority for the distinct six spaces.

## 0. Product contract

`apps/web` is the user-facing SecFusion product. It is independent from the Wiki/Website and does not use the old Workbench UI as its product shell.

The product must make the system's real capabilities visible:

```text
External sources
  → Data Plane / Evidence World
  → Evidence + Knowledge + Incident + Insight + Experience
  → Task / Agent Runtime
  → Investigation State
  → Decision / QA
  → Live Operations
```

The frontend may introduce presentation aliases, visual grouping and derived read models. It must not introduce a second source of business truth.

### Anti-toy rule

Anything rendered as a live system fact must resolve to an existing runtime owner, read model, metric or event. Hard-coded demo telemetry, fake Agent activity, fake source health, fake Skill status and fake streaming are prohibited.

---

## 1. Requirements / competition alignment

The product exposes the complete M1–M8 story rather than only the final QA surface.

| Requirement | Product proof |
|---|---|
| M1 monitoring / multi-source automation | WORLD + OBSERVATORY live source/runtime views |
| M2 evidence preservation / normalization | Evidence inspector + source/revision/locator |
| M3 enrichment / association | Intelligence dossier, 12 enrichment dimensions, graph |
| M4 investigation context | Investigation confirmed/conflict/unknown/evidence-gap state |
| M5 Agent investigation | AGENTS, Task/activity/delegation/Capability/Skill |
| M6 decision / QA | START + continuous session + Decision/citations |
| M7 evaluation | internal engineering capability; outside user navigation |
| M8 operations | OBSERVATORY / LIVE + health/degraded/recovery |
| C1 traceability | every visible conclusion/fact has evidence drill-down |
| C2 external content untrusted | evidence/source semantics remain visible; no source text becomes authority in the UI |
| C3 bounded execution | Task state, budget/deadline/stop reason where reliable |

The competition explicitly scores Agent usage, automation/engineering and demonstration quality. Those capabilities are therefore first-class product surfaces, not hidden engineering diagnostics.

---

## 2. Information architecture

Keep the navigation short: five real spaces plus one global action.

```text
WORLD           live Evidence World / Data Plane
INTELLIGENCE    dossiers, relationships and evidence
INVESTIGATIONS  durable cases and continuous user interaction
AGENTS          Role / Task / Capability / Skill / Experience
OBSERVATORY     live runtime / health / service state

                [ START ]
```

`WORLD` is the default landing surface. `START` is globally available and visually distinctive; it is not a sixth list page.

The legacy `/api/v1/workbench/*` surface has been retired. Product/Application routes are the browser-facing contract.

---

## 3. Global START — five execution modes

The Product maps directly to TD2's canonical execution profiles.

| User mode | Canonical profile | Behavior |
|---|---|---|
| 快速回答 | `DIRECT` | answer from current confirmed world |
| 证据检索 | `RETRIEVE` | bounded local retrieval + synthesis |
| 精准核验 | `VERIFY` | bounded active verification, durable Investigation |
| 深度调查 | `INVESTIGATE` | multi-step Agent investigation / delegation |
| 持续守望 | `WATCH` | durable waiting Case, wake on world/time/source change |

### START interaction

Use a five-mode spatial selector, inspired by priority-reveal / inspect-split motion grammar, not ordinary radio buttons.

Each mode exposes, on focus:

- what it does;
- expected interaction class (interactive / async / waiting);
- whether it creates or continues a durable Case;
- relevant capability classes;
- simplified target/question inputs;
- optional advanced source/budget/deadline controls only when the user expands them.

`START` produces one of two honest outcomes:

```text
completed → Decision
accepted  → Investigation
```

A `202 Accepted` result is never rendered as a finished answer.

---

## 4. WORLD — Evidence World

### 4.1 Purpose

WORLD answers:

> What is SecFusion observing now, how is information flowing through the system, what is hot, what is being enriched, and what has become durable evidence/knowledge?

The opening composition puts a real source object in the foreground and other observed objects in depth. Source processing and retained evidence are inspectable from that object.

### 4.2 Stable topology

The topology is grounded in TD1 and the source registry.

#### Outer source taxonomy

Eight product source categories:

```text
vulnerability
development
academic
vendor
independent
normative
assets
incidents
```

#### Processing layer

Four main processing paths plus one side path:

```text
Bug Stream
Structured Development Index
Insight Corpus
Incident Watch
Asset Observation (on-demand side path)
```

#### Hot layer

```text
Hot Bug working set
Incident signal / candidate working set
```

#### Durable inner world

```text
Evidence
Knowledge
Incident
Insight
Experience
```

### 4.3 Spatial focus and source facts

WORLD uses DOM text and an SVG depth field. One observed object occupies the foreground;
real peers occupy orbital positions. Clicking a peer changes the narrative and visual focus.
Motion follows focus changes, respects reduced motion, and never impersonates ingestion,
promotion, new observations or execution. The eight source directions expose individual
source inspection; they are not status cards or dashboard totals.

`GET /api/v1/world/stories` returns heterogeneous source facts, original excerpts,
publication/observation times and exact revision/observation/locator coordinates. The query
chooses the latest document revision, bounds reads per source, and interleaves categories
and sources. Broad independent/news feeds require a typed link to the managed corpus,
unless their registered authority scope already covers AI/model/Agent material. Original
source abstracts have priority over document bodies. No keyword scoring, fabricated
importance paragraphs, title special cases or backend language templates are used.

The initial story query is independent of Hot, source health, candidate and measurement
reads. The Application read service merges concurrent cold reads, warms at bootstrap within
a five-second deadline, and retains the original generated_at in a 15-second snapshot. Hot refresh starts after story data arrives; source health starts when inspected.
Coordinates stay in inspection. Original content keeps its language; Product actions and
inspection labels support Chinese and English. `进入对象` opens the existing dossier and
`继续调查` carries the object/incident/question into START. Hot state stays distinct from
durable Evidence/Knowledge.

### 4.4 Hot Pool

The existing Redis Hot Bug contract is the truth source. Product adds a read seam, not a new Hot entity.

Target API:

```text
GET /api/v1/world/hot
GET /api/v1/world/hot/{source_id}/{external_object_id}
```

`HotItemView` should expose current source/revision/timestamps, `changed_fields`, `priority_signals`, access/activity/pin state and a compact projection summary.

Selected Hot CVE opens a dossier and may jump into INTELLIGENCE.

### 4.5 Enrichment view

For one selected vulnerability, reveal the registered enrichment dimensions and their current semantic status:

```text
identity
severity
weakness
product/package
version applicability
fix/remediation
exploit state
exploit likelihood
advisory/reference
asset exposure
research/paper
incident context
```

`resolved / conflict / unknown / missing` is more important than decorative completeness rings.

The UI separately represents:

- Data Plane processing path (retention/lifecycle);
- M3 enrichment processor (`deterministic / graph / semantic / provider-backed`).

They must never be conflated visually.

### 4.6 WORLD live metrics

The existing data-plane measurement contract is Product data:

```text
1h / 6h / 24h / 168h rolling windows
hourly_series
category_hourly_series
source_health
pipeline_state
storage
```

WORLD keeps a compact live strip. Full charts live in OBSERVATORY.

---

## 5. INTELLIGENCE — evidence-first dossiers

### 5.1 Primary objects

Product eventually supports:

- Vulnerability;
- Incident;
- ResearchWork / Document;
- Normative document / Requirement / Control;
- Repo / PR / Commit / Release;
- Product / Package / SoftwareVersion;
- InternetAsset.

Product v1 makes Vulnerability and Incident strongest first.

### 5.2 Vulnerability dossier

Group canonical facts/relations into user-readable sections without inventing a new ontology:

```text
Identity & Severity
Weakness
Affected Product / Version Applicability
Fix / Remediation
Exploit / KEV / PoC
EPSS / Likelihood
Advisories
Internet Exposure
Research / Paper
Incident Context
Other canonical facts
```

Every fact/relation keeps its Evidence control adjacent.

### 5.3 Focused knowledge graph

Use a bounded neighborhood around the selected object, inspired by Project Knowledge Graph / Interactive System Map.

Typical vulnerability neighborhood:

```text
CVE
 ↔ Product / SoftwareVersion
 ↔ Weakness
 ↔ Advisory
 ↔ Repo / PR / Commit / Release
 ↔ ExploitArtifact
 ↔ ResearchWork
 ↔ SecurityIncident
 ↔ InternetAsset
```

Requirements:

- stable typed nodes/edges;
- search/focus/filter;
- current object remains the visual anchor;
- selected-node dossier is available without hover;
- canonical/source-specific/exploratory layers are distinguishable;
- the graph never implies completeness beyond the loaded neighborhood.

### 5.4 Evidence inspector

Target Product API:

```text
GET /api/v1/evidence/{evidence_ref}
```

It resolves the existing EvidenceLink/Observation/Artifact coordinate and exposes only safe Product fields:

- source identity/class/authority where known;
- external object/revision;
- published/updated/observed/fetched timestamps;
- locator;
- safe excerpt/media metadata where available;
- canonical URL where safe;
- evidence identity.

Internal storage URI/path/credential never leaks.

---

## 6. INVESTIGATIONS — case file + continuous interaction

### 6.1 Layout

Desktop uses a case-file / session split:

```text
Case dossier                         Continuous interaction
┌────────────────────────────┐      ┌────────────────────────────┐
│ target / goal / status     │      │ session turns              │
│ current activity           │      │ user follow-up             │
│ confirmed findings         │      │ Decision / citations       │
│ conflicts                  │      │ investigation launch       │
│ unknowns                   │      │ SSE activity               │
│ open evidence needs        │      │ composer                   │
│ latest decision            │      └────────────────────────────┘
└────────────────────────────┘
```

### 6.2 User-facing states

Primary semantic buckets:

- 已确认 / Confirmed;
- 有冲突 / Conflict;
- 未知 / Unknown;
- 待补证据 / Evidence needed.

Progress is never a model-invented percentage. Use phase, EvidenceNeed state and Task terminal state.

### 6.3 Session continuity

A Product session that owns an active/waiting Investigation continues the same durable Case when allowed by the backend lifecycle contract.

The UI explicitly says “继续当前调查” rather than making every turn look like a new bot request.

### 6.4 Runtime activity

TD2A's Product-safe `RuntimeActivityView` must be implemented and used here.

Allowed activity vocabulary:

```text
task_started
evidence_need_selected
retrieval_planned
capability_selected
external_observation
child_task_started
child_task_completed
state_updated
decision_ready
waiting
completed
failed
```

Do not expose chain-of-thought, raw PolicyDecision, full prompt, credential or unredacted tool output.

### 6.5 ProductEvent / SSE

Target contract:

```text
GET /api/v1/investigations/{case_id}/events
Accept: text/event-stream
Last-Event-ID: ...
```

Product event types:

```text
investigation.started
investigation.status_changed
investigation.progress
investigation.finding_added
investigation.conflict_changed
investigation.evidence_need_changed
investigation.decision_ready
investigation.waiting
investigation.completed
investigation.failed
investigation.canceled
```

SSE powers real activity/message reveal. It must reconnect from durable state when transient delivery is unavailable.

### 6.6 Text streaming boundary

Current model execution returns a structured completed response. Until a real streaming provider/runtime contract exists, progressive rendering of a completed Decision is visual reveal only and must not be described as token streaming.

If true token streaming is later implemented, it gets its own explicit ProductEvent/ModelExecution contract.

---

## 7. AGENTS — visible runtime, no fake personas

The code has exactly three canonical Roles. Product aliases are 1:1 presentation identities.

### ORACLE / 判谕者

```text
Canonical: DecisionRole@1
Mission: evidence-bounded Decision and citations
Profiles: DIRECT / RETRIEVE
```

Visual signature: eclipse/concentric focus axis; evidence converges into a bounded conclusion.

### ARGUS / 百眼调查者

```text
Canonical: InvestigationRole@1
Mission: EvidenceNeed-driven investigation, Skill/Capability choice,
         delegation, wait/recovery/stop
Profiles: VERIFY / INVESTIGATE / WATCH
```

Visual signature: multi-aperture / multi-focus observation sigil.

### ALCHEMIST / 炼证者

```text
Canonical: EnrichmentRole@1
Mission: fill M3 evidence gaps using deterministic/graph/semantic/provider operators
```

Visual signature: segmented processing ring; segments light only for real processor/operator activity.

Canonical role ID/version stays visible in the technical dossier.

### 7.1 Task field

Tasks are shown as a parent/child execution field, not as an arbitrary workflow animation.

State grammar:

```text
queued/submitted       low-energy pending
running                active pulse
waiting_*              stable suspended orbit
completed              settled/stable
failed                  broken but retained
canceled                sealed/archived
```

Parent-child links exist only when durable parent/delegation facts exist.

Selected Task dossier should expose, where available:

- Task kind/profile/status;
- EvidenceNeed;
- selected Skill;
- selected Capability / invocation;
- current activity;
- budget/deadline summary;
- stop/failure reason;
- child Task refs;
- evidence/result refs;
- technical coordinates under an expandable section.

### 7.2 Skill Codex

Existing seed skills:

```text
VerifyFixBoundary
ResolveSourceConflict
TraceIncidentEvidence
AssessAffectedDeployment
AssessApplicability
```

Product reads real Skill status (`candidate / validated / active / ...`). It never promotes seeded candidates visually.

Selected Skill detail may expose applicability, semantic procedure, guards, fallbacks, stop conditions, capability classes and deeper provenance/validation refs.

### 7.3 Experience / evolution

Visualize the existing evolution path:

```text
Trajectory
  → ExperienceCandidate
  → ExperiencePattern
  → SkillPatchCandidate / SkillCandidate
  → M7 replay / regression
  → validated / active SkillVersion
```

Support and counterexample trajectories remain visible. Experience is presented as procedural prior, never factual Evidence authority.

---

## 8. OBSERVATORY — live operations

One live view with explicit refresh and measurement windows.

### 8.1 LIVE

Data Plane live metrics include:

- source health and category distribution;
- observations / fresh changes / backfill;
- canonical writes;
- document growth;
- scheduled run success;
- provider-boundary vs runtime-owned failures;
- queue delay / execution p95;
- fresh Knowledge latency where evaluable;
- source/category contribution and concentration;
- artifact integrity;
- 1h / 6h / 24h / 7d selection.

Use charts appropriate to the data (spectrum monitor, line/trend, event bars, activity calendar, balance chart) rather than one generic chart component.

Agent live data may include:

- Task status/role distribution;
- capability invocation;
- model attempts/retries;
- stop/failure reasons;
- wake/recovery state;
- budget facts only where measurement is authoritative.

System live data includes readiness/degraded components, outbox/task-event lag and worker/dependency health as they become available through stable read models.

### 8.2 Evaluation boundary

Formal benchmark and competition records remain available to engineering through existing backend contracts. Product does not fetch or render these records, including when a historical URL contains `mode=proof` or `guide=frozen`.

---

## 9. Visual direction

### 9.1 Core art direction

**Cinematic Scientific Instrument** — an active research/security instrument with spatial depth, restrained illumination and editorially clear dossiers.

Avoid generic “cybersecurity dashboard” motifs such as matrix rain, shield wallpaper and arbitrary neon wiring.

Suggested semantic palette:

```text
Void            #07090D
Deep surface    #0D1117
Raised surface  #131923
Primary text    #F2F1EA
Secondary       #9299A5
Hairline        rgba(255,255,255,.10)

Live / brand    acid-lime #C9F45B
Data / source   ice-cyan  #72D7FF
Agent / reason  violet    #A88BFF
Conflict        amber     #FFB35C
Failure         coral     #FF6B72
```

Colors encode semantic channels. The eight source categories do not become eight saturated colors.

### 9.2 Layering

Translucency / blur is allowed only where it communicates spatial layering. Ordinary lists and dossiers use strong typography and spacing before borders/effects.

Glow is state/focus/activity dependent, not permanent decoration.

### 9.3 Typography

- modern grotesk for Product text;
- monospace for CVE, source, revision, hash and technical coordinates;
- large display type used sparingly;
- body/dossier information remains selectable DOM text.

---

## 10. Motion system

Motion is planned before page polish.

### Ambient

Slow world drift / depth only. No business meaning.

### State transition

Triggered by real fresh change, promotion, Task start/wait/complete, finding, Decision, failure/recovery.

### Focus transition

Camera/layout focuses selected source/CVE/Agent/Task while preserving orientation.

### Narrative transition

START → result, Evidence → conclusion, Task → child Task may use a more visible velocity-matched reveal.

### Rules

- do not animate hundreds of DOM elements simultaneously;
- graph/world uses LOD/clustering;
- no bounce-heavy UI;
- live updates should not cause layout jumps;
- `prefers-reduced-motion` removes camera drift/particle transit/progressive reveal while preserving status meaning;
- an animation cannot imply a runtime operation that did not occur.

---

## 11. Product API gap contract

Status:

- `A` — Product API exists;
- `B` — backend fact/store exists, stable Product read model/API missing;
- `C` — TD2A/PRD contract exists, runtime implementation missing;
- `D` — presentation projection over existing facts.

| Capability | Status | Owner / action |
|---|---|---|
| Question DIRECT/RETRIEVE | A | `/api/v1/questions` |
| VERIFY/INVESTIGATE/WATCH start | A | questions/investigations |
| Product session continuation | A | AskQuestionUseCase |
| Decision read | A | `/api/v1/decisions/{id}` |
| Investigation list/detail | A | `/api/v1/investigations` |
| Vulnerability Knowledge | A | `/api/v1/vulnerabilities/{cve}` |
| Evidence view | A | `/api/v1/evidence/{evidence_ref}` |
| Intelligence search | A | `/api/v1/intelligence/search` |
| Incident Product detail | A | `/api/v1/incidents/{incident_id}` |
| RuntimeActivityView | A | Product Task detail projects TaskEvent / Capability / PromptAssembly / Budget |
| Investigation SSE | A | `/api/v1/investigations/{case_id}/events` |
| cancel/resume | A | explicit cancel; durable Case/session continuation; dependency wake remains runtime-owned |
| source/System overview | A | `/api/v1/world/overview` + `/api/v1/observatory/system` |
| data-plane metrics | A | WORLD / OBSERVATORY consume measured operational windows |
| Hot Pool list/detail | A | `/api/v1/world/hot` + ranked detail read |
| Evidence World topology | A/D | source registry + Product snapshot + bounded visual projection |
| Agent Role/Task status | A | `/api/v1/agents/runtime` + `/api/v1/tasks*` |
| Capability activity | A | CapabilityInvocation projected through Agent runtime/task detail |
| Skill read | A | `/api/v1/agents/learning` |
| Experience read | A | `/api/v1/agents/learning` |
| Trajectory read | A/D | Experience support records expose bounded trajectory coordinates; raw trace stays backend-owned |
| model attempt/retry read | A | persisted ModelRequest / ModelAttempt projection in Agent runtime |
| true token streaming | C | new provider/runtime stream contract required |
| Agent regression / competition evaluation | engineering-only | remains backend-owned; not rendered in Product navigation |

Product implementation closes these seams through Product/Application read models rather than a parallel diagnostic transport.

---

## 12. Frontend technology

The previous dependency-free HTML/CSS/JS constraint is removed. Product complexity now justifies a real app stack.

Recommended v1:

```text
React + TypeScript + Vite
React Router
TanStack Query
Motion
ECharts
Three.js / React Three Fiber for WORLD only
Lucide
```

No large generic UI component framework is required; the product needs a custom visual grammar.

Rules:

- WebGL is limited to spatial WORLD / selected Agent visualization;
- dossiers/forms/tables/text remain DOM;
- graphs/metrics must have accessible labels/summary;
- WORLD has a 2D/static reduced-motion fallback;
- business logic remains backend-owned.

---

## 13. Product flow

WORLD source/Hot object → INTELLIGENCE dossier/evidence → START question → durable INVESTIGATION and AGENT execution → cited Decision → Evidence inspector. The asynchronous M5 completion automatically enters bounded M6 finalization through the existing M4 gate. Insufficient evidence creates a durable EvidenceNeed and waiting Case; user continuation preserves the session target. OBSERVATORY shows live service and task state.

There is no separate guided or demo path.

---

## 14. Delivery order

### P0 — product truth surface — closed

1. React/Vite Product shell and five-space navigation + START;
2. existing Product API integration;
3. Evidence Product read endpoint;
4. Data Plane Product snapshot/source overview endpoints;
5. Hot Pool read seam;
6. Task/Role/RuntimeActivity read seam;
7. ProductEvent/SSE;
8. real vertical path: `WORLD → START → Investigation → Decision → Evidence`.

### P1 — full competition capability exposure — active polish

- intelligence search / incident / graph;
- Skill / Experience / Trajectory read surfaces;
- Agent task/delegation/capability visuals;
- Observatory full curves;
- explicit cancel; resume remains split between runtime dependency wake and durable Case/session continuation;
- degraded/fallback/recovery UX.

### P2 — cinematic finish and deployment — active polish

- Evidence World 2.5D/WebGL refinement;
- Role sigil motion system;
- responsive/reduced-motion/accessibility;
- reverse proxy / production Compose / TLS seam;
- performance/visual regression checks.

Current closure evidence:

- `make product-check` owns static Product contract checks, build/bundle budgets, deploy checks and Product/API/runtime regression tests;
- `make product-live-gate` validates the live Product data path against the running API;
- `make product-visual-check` resolves current Product objects and browser-checks all six spaces at desktop, projector, tablet and mobile viewports, plus reduced-motion WORLD;
- Nginx/Compose deployment remains fail-closed behind Basic Auth, with `/healthz` as the sole unauthenticated health route;
- worker availability uses bounded Celery control probes; worker-process uptime remains unavailable; true provider token streaming stays outside Product v1 until the runtime exposes a real stream contract.

---

## 15. Acceptance gate

A Product view is complete only when:

- its live facts come from a named runtime owner;
- the retired Workbench API is absent; Product UI uses Product/Application routes only;
- loading/empty/error/degraded states work;
- primary interactions are real and navigable;
- conclusions/facts/metrics can be drilled into evidence or technical coordinates;
- animation carries an explicit state/focus/relationship meaning;
- user copy is understandable without reading TD2;
- expert coordinates remain inspectable;
- the view maps to a Requirements/competition value;
- reduced-motion remains fully informative.

Repository hard gate:

```text
rg '/api/v1/workbench' apps/web/src
```

must return no Product callsite.

The standard Product completion gates are:

```text
make product-check
make product-live-gate
make product-visual-check
```

---

## 16. Never fake

Never fabricate:

- source/runtime health;
- Hot CVE state;
- Agent Role or Task delegation;
- Skill activation/promotion;
- tool/provider invocation;
- token streaming;
- private chain-of-thought;
- live success metrics from frozen benchmark data;
- external success rate from controlled Agent regression;
- monetary cost from token count × public pricing;
- an animated processing path without a runtime fact owner.

Presentation aliases and cinematic abstraction are encouraged. Business truth remains singular.

---

## 17. Visual ambition — bold by default

Product v1 is allowed to be cinematic, spatial and visually assertive. The frontend must communicate the real scale of the system; reducing SecFusionAgent to a conventional admin shell would hide engineering work that is directly relevant to competition scoring.

The visual goal is not restraint for its own sake. It is **high-impact, high-information presentation with semantic discipline**.

### 17.1 Required WOW moments

Each primary product space should have one memorable visual event:

- `WORLD`: live source constellation → Hot object → durable Evidence/Knowledge promotion;
- `START`: selected execution mode moves forward and initiates a real Product action;
- `AGENTS`: Role accepts Task / delegation appears / recovery episode resumes;
- `INVESTIGATIONS`: ProductEvent stream changes Case state and a Decision converges from Evidence;
- `INTELLIGENCE`: focused graph expands around a selected object and evidence remains inspectable;
- `OBSERVATORY`: source/task/service state changes redraw the live instrument without leaving the operational surface.

These moments may use stronger camera movement, masking, parallax, line-draw, particle transit, digit-roll and spatial transitions than ordinary enterprise software.

### 17.2 Text and number motion

Motion intensity is hierarchical:

```text
hero/system-state     strong reveal / scan / mask-in
live ProductEvent     short slide/fade/highlight
metric change         count-up / digit-roll / line-draw
ordinary prose        stable
technical coordinate restrained instrument-style reveal
```

Do not animate every label. Visual impact comes from contrast between stable information and decisive state changes.

### 17.3 The product may look expensive

Allowed:

- 2.5D / WebGL world space;
- particle/evidence transit;
- orbital relationships;
- live task links;
- role sigils;
- controlled glow;
- layered translucent surfaces;
- cinematic route transitions;
- animated data curves;
- spatial focus and dossier reveal;
- high-impact START interaction.

The product should feel like a live scientific/security instrument, not a cautious CRUD application.

### 17.4 What still cannot be theatricalized

Visual ambition does not relax truthfulness:

- no fake processing event;
- no fake Task/Role activity;
- no fake streaming;
- no fake Skill promotion;
- no fake runtime metric;
- no fake source health;
- no fake evidence edge;
- no fake success state.

The rule is:

> **Be loud about what the system really did. Never invent something merely because it looks impressive.**


## 18. Product reading and runtime boundaries (2026-10-08)

WORLD places source convergence in the main canvas, keeps selected source material alongside it, and exposes four explicit views: signals, source paths, Hot browsing, and processing/retention. Hot displays the actual resident count separately from the ranked 64-item reading window. A successful ProcessingRun is shown as a knowledge commit only when a linked KnowledgeRevision exists. Source/view/Hot coordinates remain URL-addressable.

START uses an explicit task selector, a natural question, real intelligence search for targets, and persisted outcomes. INTELLIGENCE opens an object chosen by the user or a recent heterogeneous source item, rather than auto-selecting a CVE. The latest document revision exposes an exact source chunk excerpt and locator; index details are disclosed on demand. Empty graphs do not fill the reading view.

INVESTIGATIONS uses natural document flow and truthful terminal states. Follow-ups retain the session and follow the existing continuation contract. AGENTS exposes role ownership and real tasks with bounded recent history; technical coordinates wrap. OBSERVATORY does not label a pending runtime read as offline or substitute zero for an unknown capability count.

QA deadline failures terminate the actual run and return a retryable problem. Research/document investigations use the non-vulnerability planner schema and local perception instead of CVE-only enrichment delegation. Runtime schema and evidence gates remain authoritative.

调查的 INSPECT 感知同时读取对象的结构化事实和当前 DocumentRevision 的正文片段；正文使用独立 document 物理读取算子，保持片段、版本、来源与对应 Observation 的 EvidenceLink 引用。未分块的新版本不会回退到历史正文。正文不是新生成的 Knowledge；确认事实仍须经过 StatePatch 和既有证据校验。

真实论文联调已验证同一 Case/Session 的继续调查、正文感知、确认事实和自动 M6 finalization：Case resolved、持久研判和来源引用可查询。引用读取同时接受既有裸 Evidence ID 和 evidence: 前缀，保持与对应状态投影一致；缺失的 EvidenceLink 仍不能生成引用。

## 19. Six-space visual composition (2026-10-08)

The six spaces are designed as one instrument, with a consistent navigation frame and readable DOM typography. WORLD now gives the source constellation and layered evidence core the primary canvas; the selected source material stays in an adjacent reading panel. Eight source ports expose actual health. Route curves describe configured topology, and the revision transition is keyed to an actual KnowledgeChange. The ranked Hot window and full residency remain separate measures.

START presents five mission pods with a shared selection transition and the selected canonical role sigil. INTELLIGENCE presents heterogeneous source covers and a focused dossier. INVESTIGATIONS keeps the continuing conversation beside its evidence state; historical execution events expand on demand. AGENTS gives ORACLE, ARGUS and ALCHEMIST distinct dark sphere, optical lens and layered processor portraits; task ownership, history, skills and experience retain their actual reads. Empty memory no longer invents seed records or promotion stages. OBSERVATORY presents two measured hourly waveforms with independent, explicitly labelled peaks and actual source health.

CSS geometry and visual semantics remain in their authority layers. Old WORLD, START, role and shell rules and the superseded source-row layout are removed. Narrow screens use a source grid, compact source covers, stacked workspaces and bottom navigation; the task launcher remains available in the top bar. Reduced-motion users receive immediate state reveals. Visual work takes priority in this pass; the existing API contracts and real runtime outcomes remain connected.


## 20. Material identity and product symbols (2026-10-08)

All six spaces share an obsidian and smoked-glass palette, platinum hairlines and restrained cyan, violet and warm metal accents. The brand monogram and semantic navigation/source/mission symbols are authored SVG geometry; familiar search, close and directional controls retain their standard affordances. Manrope is self-hosted as a 161 KB variable font, with native CJK sans fallbacks and its SIL OFL license distributed with the Web app.

ORACLE, ARGUS and ALCHEMIST use material portraits: an orbital dark sphere, optical aperture and layered evidence processor. Category covers use separate folio, lattice, fissure, seal and coordinate compositions. WORLD uses a layered archive sculpture, while source health, KnowledgeChange and Hot counts remain real reads. These visual assets represent product identity and source categories; they do not create runtime events or inferred relationships. Hover elevation is brief and disabled for reduced motion. Previous flat role sigils, intersecting cover rectangles and fluorescent primary actions are retired, including stale selected-case overrides.

## 21. Object-led composition (2026-10-08)

This composition supersedes the equal-card layouts recorded in sections 19–20. The material portraits and self-hosted typography remain; the primary page structure changes.

- WORLD gives the selected, genuinely retained material the primary headline and source excerpt. A spatial material stage supplies click-to-focus neighbours, with no hover-driven story replacement. The eight source directions remain unboxed controls. The full Hot residency count opens the existing bounded, paginated Hot read; it is not the size of the current story projection. Artwork represents categories, not processing activity.
- INTELLIGENCE uses a selected folio and a horizontally browsable collection shelf. Selecting a shelf item previews its original title and excerpt; the explicit dossier action opens its canonical object or incident. The loaded projection is not presented as a complete archive.
- START composes the five genuine execution profiles as an approach rail, their actual assigned role as a material portrait, and the existing question/target controls as the adjoining desk. Profile submission, restored results and Session continuity keep their existing backend contracts.
- AGENTS lets the focused role, or otherwise the selected Task owner, occupy the main portrait. Other canonical roles remain available through smaller selectors. Execution and memory are separate rendered workspaces. Opening a referenced Skill switches to memory before reading the corresponding family. Live accents still require measured active Tasks.
- INVESTIGATIONS collapses historical case selection into an optional index. The current goal, editorial findings and actual decision occupy the reading space; continuous conversation remains adjacent through the existing portal. Evidence controls still resolve actual source material. Technical revision labels are removed from individual finding prose.
- OBSERVATORY gives the two independently scaled, measured curves a continuous stage, followed by the source health spectrum. Source/data/agent/service selectors render one corresponding detail surface at a time. Window selection updates the actual hourly series and window totals.

The shared navigation is a compact rail on desktop and a top navigation on narrow screens. Mobile status reads have the full available width. Category artwork never supplies fabricated source facts, and role artwork never fabricates runtime events. Obsolete atlas, card catalogue, role-card and mission-card selectors are removed from the final style authorities.


## 22. Independent editorial visual system (2026-10-08)

This is the current visual implementation contract. It supersedes the style stack, palette and navigation arrangements described in sections 19–21. `main.tsx` loads `product-foundation.css`, `product-spaces.css`, and the dedicated `account-space.css`. The five legacy stylesheets are not part of the application bundle. The first file owns the reset, typography, navigation and shared primitives; the second owns the six spaces and their dossier, memory, evidence and narrow-screen compositions. Account forms and conversation lists own their separate space styles; do not reintroduce a legacy cascade or override layer. The CSS authority check validates these imports and disallows specificity escalation through `!important` outside reduced-motion accessibility.

The visual frame uses warm ivory, forest ink, copper accents and generous type. Desktop navigation is horizontal. WORLD and AGENTS use dark material stages; INTELLIGENCE is an editorial collection; START places execution approach and question desk side by side; INVESTIGATIONS is a reading workspace with a continuous conversation; OBSERVATORY uses measured curves and a genuine source-health spectrum. Narrow WORLD brings its material stage before the long source headline. Empty dossier sidebars do not reserve a blank column. Original document excerpts precede structured object facets.

`HeroArtifact` renders category and role identity as real WebGL material sculptures, with category/role SVG fallback. These are decorative identities, not evidence edges, activity indicators or runtime events. Offscreen rendering and hidden tabs pause; reduced motion produces a still image. Camera framing adapts to narrow portraits. Actual status, residency, source health, records, revisions, tasks and citations continue to come from Product API reads.

The skills memory is a codex with version headers, readable procedures and folded validation/provenance. Search results and evidence inspection have explicit overlay ownership. The deployed backend contracts, profile routing, existing Case/Session continuity, evidence gate and event streaming are unchanged by this visual implementation.


## 23. Material studio (2026-10-08)

`HeroArtifact` owns one decorative WebGL canvas per primary material stage. `artifactShader` owns bounded SDF geometry and procedural studio lighting: paired orbital rings and a ceramic core, convex optical lens and eight iris blades, four framed glass folios with a central spine, interlocking development frames, a bevelled asset crystal, and fractured vulnerability columns. Optical surfaces trace the inner non-glass structure and combine transmission with Fresnel reflection; platinum, ceramic and copper remain separate materials. The render is not a runtime state read or activity signal.

The portrait preserves canvas aspect ratio and caps render size at 720×480 with a maximum 1.5 pixel ratio. Motion draws at most every 80ms; elapsed visible time drives subtle pose changes. Offscreen/hidden tabs pause, reduced motion draws a still pose, and pointer parallax ignores touch. Shader/context failure uses the corresponding category/role SVG; context loss returns to that fallback. Small source covers and role selectors remain SVG so a collection does not create one GL context per item.

Warm ivory, forest ink and copper material controls remain owned by the existing foundation/spaces files. Navigation, selected roles, catalogue covers, action hover and input focus have restrained surface highlights and depth. The account space has its own component styles; no legacy cascade or decorative fake processing is introduced. The Nginx authentication prompt uses the product name; its access boundary and existing credential configuration are unchanged.

Finals readiness is reviewed outside normal product flows in the dated Wiki report, against all eleven finals rubric rows. Historical numeric target checks are not a current deployment score or a complete finals assessment.

## 24. Accounts and completed product actions (2026-10-08)

Accounts are a Product/Application authority, added at the user's request. `/auth` uses the same ivory, forest and glass material language; its styles live in the dedicated `account-space.css`, alongside the foundation and six-space styles. It does not import or override the retired CSS stack.

Registration, sign-in, current account and sign-out use `/api/v1/auth/{register,login,me,logout}`. The browser stores no password or token in localStorage. A random HttpOnly, SameSite=Lax cookie resolves to a hashed, expiring, revocable PostgreSQL session; the server derives `user:{id}`. `X-Principal` is not an identity source. Mutations require the same-origin CSRF header and origin checks. Account and private API responses are not cacheable. Production cookies require HTTPS.

WORLD, public dossiers and aggregate operations remain readable without an account. START, investigations, private runtime/task reads, enrichment submission, interests and recommendations require sign-in. Case, question-session, Decision, task, model-attempt and A2A reads enforce durable ownership. System tasks acting for another account are private. Public procedural memory excludes user-derived provenance. Existing anonymous/local records are not automatically assigned to a new account.

Account changes clear query/mutation caches and remount page state. A 401 expires the frontend session; a response from an older account epoch cannot erase a newer login. START lists the account's recent conversations from `/questions/sessions`; each link restores the persisted session/turn/target/outcome. Sign-out revokes the server session, including continued SSE access.

INTELLIGENCE persists explicit keywords, followed objects and interested/ignored/neutral feedback. Recommendations use current accepted, evidence-backed canonical matches; each item explains its match and provides source links. Ignoring supports undo. There is no inferred demographic profile or claim of learned personalization.

For vulnerabilities, selected enrichment dimensions submit a real idempotent EnrichmentRole task. The UI follows its actual lifecycle and refreshes the dossier after termination. The production composition binds FIRST EPSS and Red Hat CSAF/VEX providers. Dimension details resolve authoritative accepted_fact_refs rather than guessing their coverage from predicate names.

START treats persisted URL coordinates and current queries as the outcome authority. New conversation clears prior session/result coordinates; restored history retains its target. An accepted or failed Case is never rendered as a completed answer.

OBSERVATORY worker health now reports bounded Celery ping and active-queue replies with measured time, consumer names and available/unobserved/unknown queue states. It is a control-plane availability probe, not a durable worker heartbeat or process uptime. WORLD operational aggregation uses bounded historical reads, a shared refresh and a 60-second maximum successful overview age; a refresh timeout returns unavailable without retimestamping old data.

Public system-task and procedural-memory links can read a pure system Case and its decision after sign-in. The controller must be system-owned and every linked task must exclude user ownership/delegation. This read permission does not add the Case to personal lists or permit cancel/continuation. Account changes notify other tabs through BroadcastChannel without transmitting identity or credentials; window focus always rechecks the session.
