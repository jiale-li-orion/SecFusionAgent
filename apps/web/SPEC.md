# SecFusion Product Frontend Spec

> Status: **Frozen for Product v1 implementation**
> Date: 2026-10-04
> Owner: Product App (`apps/web`)
> Scope: user-facing SecFusion product frontend. This document does **not** define the Wiki/Website or the internal Workbench.

## 0. Product decision

`apps/web` becomes the **SecFusion Product App**. The old runtime-console UI is retired rather than evolved into the product.

The product frontend talks only to stable Product/Application HTTP contracts:

```text
/api/v1/questions
/api/v1/investigations
/api/v1/decisions
/api/v1/vulnerabilities
/api/v1/evidence
/health
```

It must not call `/api/v1/workbench/*`.

The Workbench backend may remain as a dev/test-only diagnostic surface while it is useful for engineering. It is not product navigation, not a product dependency, and is disabled in production.

The Wiki/Website remains a separate documentation/competition-explanation surface. No Wiki component, page hierarchy, data projection or visual layout is reused as Product UI.

---

## 1. Product promise

SecFusion is an **evidence-first security intelligence workspace**.

A user should be able to move through one continuous product flow:

```text
Ask a security question
  → get a fast evidence-grounded answer
  → inspect the supporting evidence
  → escalate an unresolved question into an Investigation
  → watch the Investigation progress
  → receive a final Decision with citations / conflicts / unknowns
```

The frontend exposes the security-intelligence object the user is working on, not the internal runtime machinery used to produce it.

### Product v1 success condition

A new user can open the deployed IP address and, without understanding `TaskRun / M4 / M6 / BenchmarkRun / ContextManifest`, complete all of the following:

1. query a CVE and understand its current facts;
2. ask a natural-language question about the CVE;
3. inspect the sources supporting the answer;
4. launch a deeper investigation when evidence is insufficient;
5. return to an investigation and see its current state;
6. understand what is confirmed, conflicting, unknown and still being investigated;
7. read the final conclusion with traceable evidence.

---

## 2. Design reference and interpretation

Primary visual/product reference:

- Skillry Opus 5.5 gallery: <https://skillry.dev/ai-videos/opus-5-5>

We borrow its **product principles**, not its page content or branding:

- content is the primary object; navigation and controls stay visually quiet;
- categories/modes are lightweight chips rather than a dashboard taxonomy;
- cards expose useful metadata without turning into dense admin tables;
- detail views keep the primary object, its comparison/evidence and its action close together;
- actions such as “copy prompt” live next to the object they act on;
- real product content is used in the UI; generic placeholder widgets are avoided;
- one coherent visual language beats many ornamental components.

### Explicit visual bans

- no “cyber security dashboard” cliché;
- no matrix rain, shields, radar sweeps or decorative network graphs;
- no glow-heavy neon chrome;
- no gradients on ordinary UI chrome;
- no fake telemetry counters that do not help the user act;
- no M1/M2/M3/M4/M5/M6 labels in user-facing copy;
- no raw JSON as the default representation;
- no giant KPI dashboard as the landing page;
- no motion for its own sake;
- no component-library look where every region is an identical card.

---

## 3. Information architecture

Product v1 has **three** primary destinations.

```text
研判 Ask
调查 Investigations
情报 Intelligence
```

No fourth “Runtime / Tasks / Sources / Evaluation” product destination is introduced.

### 3.1 研判 / Ask

Default landing surface.

Purpose: turn a question into either a synchronous evidence-grounded Decision or an asynchronous Investigation.

### 3.2 调查 / Investigations

Purpose: list durable investigations and open one as a living case file.

### 3.3 情报 / Intelligence

Purpose: inspect canonical vulnerability Knowledge directly, including claims, relations and evidence.

### 3.4 Evidence drawer

Evidence is not a primary navigation destination. It opens in context from a conclusion, finding, claim or relation.

---

## 4. Core user journeys

### Journey A — Fast fact lookup

```text
Ask
→ target CVE optional
→ mode = 快速研判
→ POST /api/v1/questions task_kind=lookup
→ Decision
→ conclusion + evidence chips
→ Evidence drawer
```

Expected response class: interactive, seconds rather than minutes.

### Journey B — Retrieval-assisted answer

```text
Ask
→ mode = 检索证据
→ POST /api/v1/questions task_kind=retrieve
→ current Knowledge + bounded retrieval context
→ Decision
→ citations
```

UI must not imply that retrieved text automatically became canonical fact.

### Journey C — Escalate to investigation

```text
Ask
→ mode = 深度验证
→ task_kind chosen from product-safe deep tasks
→ POST /api/v1/questions
→ 202 Accepted + InvestigationView
→ navigate to investigation detail
→ poll GET /api/v1/investigations/{case_id}
```

First v1 deep-verification preset:

```text
verify_version_fix
```

Additional TaskKinds may be exposed later only when product copy and lifecycle are understandable.

### Journey D — Continue an investigation

```text
Investigation detail
→ current episode terminal/waiting
→ user asks follow-up
→ POST /api/v1/questions with session_id
→ same durable Case continues
```

The UI must never create the impression that every follow-up creates a second Case.

### Journey E — Inspect canonical intelligence

```text
Intelligence
→ CVE search
→ GET /api/v1/vulnerabilities/{cve_id}
→ object summary
→ claims / relations grouped by user meaning
→ evidence chips
→ Evidence drawer
```

---

## 5. Screen contracts

## 5.1 Ask

### Empty state

The landing screen is prompt-first, not metric-first.

Composition:

```text
brand / compact product nav

What do you need to verify?
short positioning copy

[ example intent ] [ example intent ] [ example intent ]

mode chips                  optional target CVE
┌─────────────────────────────────────────────────────┐
│ Ask a security intelligence question…        Send │
└─────────────────────────────────────────────────────┘
```

Example intents must be backed by real supported workloads, e.g.:

- “这个 CVE 的 CVSS 分数是多少？”
- “该版本是否受影响？”
- “哪个版本首次包含修复？”

### Conversation state

Conversation is intentionally narrow. It shows user turns and SecFusion results, not a general chat transcript.

A synchronous result renders as a **Decision block**:

```text
Answer
  concise answer payload

Supported conclusions
  proposition                             [Evidence 2]
  proposition                             [Evidence 1]

Conflicts          Unknowns
...

stop reason / timestamp kept secondary
```

If the result becomes an Investigation, render an **Investigation launch block** with current phase and one clear action: `查看调查`.

### Session

`session_id` lives in browser session/local state and is shown only as subtle continuity state, not as an opaque UUID in the main UI.

“新建研判会话” clears local conversation and current session binding. It does not delete server-side durable records.

---

## 5.2 Investigations list

No runtime-table layout.

Each investigation card contains:

- goal;
- target identity where available;
- status;
- current activity / phase;
- count of open evidence needs;
- updated time;
- compact evidence-state summary where useful.

Filters:

```text
全部 / 进行中 / 等待 / 已完成
```

Filters remain chips/tabs, never a multi-row admin filter form in v1.

---

## 5.3 Investigation detail

This is the primary “product proof” screen.

Layout on desktop:

```text
┌──────────────── main case file ────────────────┬──── context rail ────┐
│ goal + status                                  │ current activity      │
│                                                │ evidence gaps         │
│ CONFIRMED FINDINGS                             │ timestamps            │
│ finding [Evidence]                             │                      │
│ finding [Evidence]                             │                      │
│                                                │                      │
│ CONFLICTS / UNKNOWNS                           │                      │
│                                                │                      │
│ LATEST DECISION                                │                      │
│ conclusions + citations                        │                      │
└────────────────────────────────────────────────┴──────────────────────┘
```

The page uses four user-facing semantic states:

- 已确认 Confirmed
- 有冲突 Conflict
- 未知 Unknown
- 待补证据 Evidence needed

Internal `tentative/hypothesis/state revision` concepts appear only where they materially help the user.

### Activity representation

Do not expose TaskEvent logs as the default product timeline.

`InvestigationActivitySummaryView` becomes the default lifecycle line:

```text
正在验证修复版本
InvestigationRole · verify_version_fix
updated 16:31
```

A future “technical details” disclosure may show runtime coordinates for debugging/demo, but is collapsed and non-essential.

---

## 5.4 Intelligence detail

The page starts with the vulnerability identity and a compact current summary derived only from returned Knowledge fields.

Primary structure:

```text
CVE identity
external identifiers / canonical object

Facts
  severity
  CVSS
  KEV
  EPSS
  weakness
  ...

Applicability & remediation
  affected / fixed / not affected
  product / version / justification

Development & references
  PR / commit / release / advisory

Evidence
```

The frontend does not invent a new semantic ontology. Grouping is presentation-only over canonical predicate/relation names.

Unknown predicates remain accessible under “其他事实” rather than being dropped.

---

## 5.5 Evidence drawer

Clicking an Evidence chip opens a right-side drawer on desktop and a full-height sheet on mobile.

Required fields:

- source;
- external object/revision;
- observed/published/updated time;
- canonical URL when present;
- source locator rendered structurally;
- evidence reference identity in technical detail.

The first Product v1 backend addition is a read-only endpoint:

```text
GET /api/v1/evidence/{evidence_ref}
```

It resolves an existing `EvidenceLink → Observation` only. It creates no new authority or duplicate evidence model.

If the canonical URL is safe/present, expose `查看原始来源`.

---

## 6. Visual system

## 6.1 Direction

The product should feel like a **research/editorial intelligence workspace**, not a SOC appliance.

Default theme: warm neutral light surface with dark typography and one controlled acid-green accent.

```text
Canvas          #F3F1EA
Surface         #FCFBF7
Text            #111318
Muted text      #70736E
Border          #D8D6CF
Accent          #C8F04A
Accent text     #111318
Dark emphasis   #17191D
```

Semantic colors are reserved for meaning:

```text
confirmed       green
conflict        amber/red
unknown         neutral violet/gray
evidence need   blue
```

Accent green is **not** used as “everything successful”. It is brand/action color.

## 6.2 Typography

- preferred: Geist / Inter-like grotesk;
- system fallbacks required;
- body 14–16px;
- dense metadata 11–12px;
- headings use weight/size, not uppercase everywhere;
- monospace only for CVE IDs, hashes, refs and exact source coordinates.

## 6.3 Shape

- radius: 12–18px for large interactive containers;
- chips: pill radius;
- ordinary information does not need a bordered card;
- use whitespace and type hierarchy before adding boxes;
- borders are 1px quiet neutral, never glowing.

## 6.4 Motion

Motion exists to explain state change.

- page/view transition: 140–200ms;
- drawer: 180–240ms;
- list insert/status update: opacity + small translate only;
- no bounce easing;
- no particle effects;
- no perpetual ambient motion;
- `prefers-reduced-motion` must disable non-essential transitions.

Polling updates should avoid layout jumps; changed values briefly highlight, then settle.

---

## 7. Interaction rules

### 7.1 One primary action per region

Examples:

- Ask composer → `发送`
- Investigation launch → `查看调查`
- Evidence drawer → `查看原始来源`

Secondary actions stay visually quiet.

### 7.2 User language over architecture language

User-facing:

```text
正在验证修复版本
需要更多一手证据
已确认 4 条事实
存在 1 项来源冲突
```

Avoid by default:

```text
M4 State
TaskRun
ContextManifest
ExecutionEnvelope
ModelAttempt
BenchmarkRun
```

### 7.3 Evidence always in context

Do not create an “Evidence table” disconnected from the conclusion it supports.

Every visible citation starts from a conclusion/finding/fact and opens the evidence detail from there.

### 7.4 Honest async behavior

A `202 Accepted` response is not rendered as a finished answer.

The UI immediately shows:

- investigation created;
- current status/activity;
- what evidence gap is being pursued;
- latest update time;
- a link into the durable investigation.

---

## 8. API mapping

| Product interaction | HTTP contract |
|---|---|
| Ask quick fact | `POST /api/v1/questions`, `task_kind=lookup` |
| Ask with retrieval | `POST /api/v1/questions`, `task_kind=retrieve` |
| Deep verify | `POST /api/v1/questions`, `task_kind=verify_version_fix` |
| Follow-up | `POST /api/v1/questions` + `session_id` |
| List investigations | `GET /api/v1/investigations` |
| Investigation detail/poll | `GET /api/v1/investigations/{case_id}` |
| Decision deep link | `GET /api/v1/decisions/{decision_id}` |
| CVE Knowledge | `GET /api/v1/vulnerabilities/{cve_id}` |
| Evidence detail | `GET /api/v1/evidence/{evidence_ref}` |
| Availability | `GET /health/ready`, `/health` |

### Product frontend hard rule

```text
rg '/api/v1/workbench' apps/web
```

must return no Product-App callsite.

---

## 9. Error / empty / loading states

### API unavailable

Show one concise global status and preserve typed input. Do not dump fetch exceptions into the canvas.

### Model unavailable

For LOOKUP/RETRIEVE, map dependency failure to a product message:

> 当前研判模型不可用。已有情报仍可查看；稍后可重试智能研判。

### CVE not in Knowledge

Do not fabricate an empty object.

> 当前 Knowledge 中没有该漏洞的 durable record。

A future explicit acquisition action may be added through a Product API. The frontend must not call Workbench enrichment as a hidden fallback.

### Investigation empty list

Explain what creates one and offer a link back to Ask.

### Loading

Use skeleton/text placeholders matching final geometry. Avoid a full-screen spinner after initial app load.

---

## 10. Responsive behavior

Desktop target: 1280–1600px.

Tablet/mobile remains functional for demo and review:

- primary nav collapses to top/bottom compact navigation;
- investigation master/detail becomes stacked navigation;
- evidence drawer becomes full-screen sheet;
- composer remains pinned near bottom on Ask view;
- no horizontal data tables in Product v1.

---

## 11. Frontend implementation boundary

### v1 implementation strategy

Optimize for finishing the product, not frontend-framework depth.

`apps/web` stays a self-contained first-party SPA that can be served as static assets. The first implementation may remain dependency-light HTML/CSS/JavaScript as long as it obeys this Spec and has clear component/render boundaries in code.

A framework migration is justified only by concrete product complexity, not by aesthetics.

Required internal modules/concepts in `app.js` or later split files:

```text
api client
router/view state
session state
Ask renderer
Decision renderer
Investigation list/detail renderer
Knowledge renderer
Evidence drawer
polling lifecycle
problem-detail mapping
```

No domain/business rule is implemented in the browser.

---

## 12. Production deployment contract

Target topology after a public IP/server is available:

```text
Internet
  → reverse proxy (80/443)
      → /              Product static frontend
      → /api/*         FastAPI
      → /health/*      FastAPI

FastAPI
  → PostgreSQL
  → Redis roles
  → ArtifactStore
  → worker / scheduler / task-event services
```

Production defaults:

- same-origin frontend/API;
- Workbench disabled;
- PostgreSQL/Redis ports not publicly exposed;
- only reverse proxy exposes host ports;
- model/provider credentials remain server-side env/secrets;
- TLS termination at reverse proxy once hostname/domain is available;
- before public exposure, product/API access gets an explicit demo authentication or access-control layer. `X-Principal` is not treated as authentication.

---

## 13. Product v1 acceptance gate

A frontend build is not “done” because it renders.

### Functional

- [ ] Product App makes zero Workbench API calls.
- [ ] CVE lookup works against real Knowledge.
- [ ] synchronous LOOKUP renders a Decision.
- [ ] RETRIEVE renders a Decision without upgrading passages to fake facts.
- [ ] deep verification creates an Investigation and navigates into it.
- [ ] Investigation list/detail works from stable Product read models.
- [ ] Investigation detail polls without duplicating Cases.
- [ ] follow-up reuses product `session_id`.
- [ ] Decision citations open Evidence drawer.
- [ ] Knowledge claim/relation evidence opens the same Evidence drawer.
- [ ] 202 / 404 / 422 / 503 ProblemDetail states are product-readable.

### Visual

- [ ] no runtime dashboard landing page;
- [ ] no raw JSON in the default path;
- [ ] no Wiki/Website UI reused;
- [ ] user actions are attached to the object they affect;
- [ ] desktop and mobile both remain usable;
- [ ] loading/error/empty states are intentionally designed;
- [ ] reduced-motion preference respected.

### Deployment

- [ ] Product frontend available at `/`.
- [ ] Product API same-origin under `/api/v1`.
- [ ] Workbench not reachable in production.
- [ ] database/Redis not bound publicly.
- [ ] reverse-proxy health path available.
- [ ] one compose command can start the deployable product stack.

---

## 14. Implementation order

Do not implement by visual section. Implement by user-complete vertical slice.

```text
P1  App shell + Ask LOOKUP + Decision + citation
P2  Evidence drawer + Intelligence Knowledge detail
P3  Deep verify → Investigation + polling
P4  Investigation list/detail + follow-up session
P5  production static serving + reverse proxy + compose
P6  responsive/polish/error states + end-to-end product gate
```

After P6, Workbench UI is deleted/retired. The Workbench backend is kept only if it still saves engineering time; otherwise remove it separately without coupling that cleanup to Product delivery.
