# SecFusion Product Frontend Spec v2

> Status: **Frozen for Product v1 implementation**
> Date: 2026-10-04
> Owner: Product App (`apps/web`)
> Supersedes: 2026-10-04 narrow Ask/Investigation/Intelligence draft

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
  → Evaluation / Operations proof
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
| M7 evaluation | OBSERVATORY / PROOF |
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
OBSERVATORY     live runtime + frozen proof

                [ START ]
```

`WORLD` is the default landing surface. `START` is globally available and visually distinctive; it is not a sixth list page.

The internal `/api/v1/workbench/*` surface is dev/test only and is never a dependency of Product UI.

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

This is the main visual proof of M1–M3 automation.

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

### 4.3 Live motion semantics

The WORLD canvas may use 2.5D/WebGL, but animation is state-driven.

| Motion / visual state | Fact source |
|---|---|
| source pulse | scheduled acquisition success/no-change |
| incoming particle | fresh external change / observation |
| dashed/ghost trail | backfill observation |
| path transit | source retention/processing path |
| hot-object elevation | recency/access/workflow/domain-priority signals |
| active/pinned orbit | active/pinned Hot Bug state |
| field flash | `changed_fields` |
| processor branch lights | actual deterministic/graph/semantic/provider-backed execution |
| crystallization into center | promotion / durable Evidence or Knowledge commit |
| core ripple | KnowledgeChange / canonical write |
| source flicker | degraded health |
| dim/lock | blocked source |
| fallback edge | actual provider/capability fallback |

Ambient drift may exist only to communicate that the system is online; it cannot impersonate a processing event.

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

## 8. OBSERVATORY — live operations and frozen proof

One top-level view, two explicit modes:

```text
LIVE | PROOF
```

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

### 8.2 PROOF

Frozen competition/evaluation evidence is visually separate from LIVE.

Current formal headline facts:

```text
CompetitionReport 2735331f-1f7d-419c-80d2-72c4ce157b5f
6 formal BenchmarkRuns completed
37/37 CaseRuns passed

M1
12/12 latency-evaluable
within 6h = 100%
source_delivery_coverage = 61.538%

M3
292 TP / 1 FP / 1 FN
precision = recall = 99.659%

M6 Product QA
14 cases
core correctness metrics = 1.0
latency avg 2.517s / max 4.032s

Session QA
context/target/retrieval reuse metrics = 1.0

Evaluation substrate
85/87 core metrics observed
only exact monetary provider/capability costs unavailable
```

The 61.538% coverage weakness remains visible. Passing CaseRun status must not be used to hide an imperfect business metric.

Controlled Agent-runtime benchmark is labeled as controlled regression evidence, not live external success rate.

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
| Evidence view | B/C | EvidenceLink + Observation; add Product read route |
| Intelligence search | B/C | retrieval kernel; add Application query |
| Incident Product detail | B/C | incident durable state; add Product read route |
| RuntimeActivityView | B/C | TaskEvent/Trajectory; add projection |
| Investigation SSE | C | ProductEvent projector + SSE |
| cancel/resume | B/C | task lifecycle; add Product command |
| source/System overview | B/C | SourceState/data-plane; add Product aggregate |
| data-plane metrics | B | existing metric generator/state; add live Product read route |
| Hot Pool list/detail | B | Redis hot cache; add ranked read seam |
| Evidence World topology | B/D | source registry + TD1 topology + runtime overlays |
| Agent Role/Task status | B | Role registry + TaskRun |
| Capability activity | B | CapabilityInvocation |
| Skill read | B | SkillStore |
| Experience read | B | ExperienceStore |
| Trajectory read | B | TrajectoryService |
| model attempt/retry read | B | ModelRequest/ModelAttempt |
| true token streaming | C | new provider/runtime stream contract required |
| Agent regression proof | B | agent-runtime benchmark |
| formal competition proof | B | benchmark/competition runtime |

Product implementation must close these seams instead of calling Workbench from the browser.

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

## 13. Demo path

A competition demo should tell one continuous story:

```text
WORLD
  → see 8 source domains and live runtime truth
  → focus a Hot CVE

INTELLIGENCE
  → inspect enrichment dimensions / graph / evidence

START / VERIFY
  → launch a fix-boundary verification

INVESTIGATION + AGENTS
  → ARGUS selects evidence gap / Skill / Capability
  → optional ALCHEMIST child enrichment
  → real activity arrives over ProductEvent/SSE

ORACLE / Decision
  → evidence-bounded answer
  → citation opens source Evidence

AGENT evolution
  → Skill / Experience / trajectory proof

OBSERVATORY / PROOF
  → live runtime curves
  → formal M1/M3/M6/Agent/fault evidence
```

This path deliberately covers monitoring, enrichment, QA, Agent architecture, automation, engineering and demonstration value.

---

## 14. Delivery order

### P0 — product truth surface

1. React/Vite Product shell and five-space navigation + START;
2. existing Product API integration;
3. Evidence Product read endpoint;
4. Data Plane Product snapshot/source overview endpoints;
5. Hot Pool read seam;
6. Task/Role/RuntimeActivity read seam;
7. ProductEvent/SSE;
8. real vertical path: `WORLD → START → Investigation → Decision → Evidence`.

### P1 — full competition capability exposure

- intelligence search / incident / graph;
- Skill / Experience / Trajectory read surfaces;
- Agent task/delegation/capability visuals;
- Observatory full curves;
- benchmark proof drill-down;
- cancel/resume;
- degraded/fallback/recovery UX.

### P2 — cinematic finish and deployment

- Evidence World 2.5D/WebGL refinement;
- Role sigil motion system;
- responsive/reduced-motion/accessibility;
- reverse proxy / production Compose / TLS seam;
- explicit demo access control;
- curated frozen demo cases;
- performance/visual regression checks.

---

## 15. Acceptance gate

A Product view is complete only when:

- its live facts come from a named runtime owner;
- no Workbench API is used by Product UI;
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
