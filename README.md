# SecFusionAgent

English | [中文](README.zh.md)

[![CI](https://github.com/jiale-li-orion/SecFusionAgent/actions/workflows/ci.yml/badge.svg)](https://github.com/jiale-li-orion/SecFusionAgent/actions/workflows/ci.yml) [![Pages](https://github.com/jiale-li-orion/SecFusionAgent/actions/workflows/pages.yml/badge.svg)](https://github.com/jiale-li-orion/SecFusionAgent/actions/workflows/pages.yml)

**Evidence-first AI Security Intelligence System**
**Agent-driven AI security intelligence fusion and assessment**

SecFusionAgent builds a continuously evolving intelligence system for AI security vulnerabilities, research progress and security incidents. The system continuously acquires new or changed content from public vulnerability databases, project repositories, security advisories, research papers and incident sources, fixes external data as traceable evidence, then performs normalization, correlation, enrichment, incident tracking and follow-up investigation.

The Agent here sits on top of a verifiable data plane. External reads carry acquisition provenance; important conclusions trace back to the original observation / artifact; historical revisions are retained and current views are rebuildable. Agent work then covers investigation, tool calls and reasoning; it does not replace evidence authority.

[Architecture Views](https://jiale-li-orion.github.io/SecFusionAgent/index.en.html) · [Project Wiki](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Home.en) · [Requirements](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Requirements-SPEC.en) · [Technical Design 1](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Technical-Design-1.en) · [Technical Design 2](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Technical-Design-2.en) · Website：[jiale-li-orion.github.io/SecFusionAgent](https://jiale-li-orion.github.io/SecFusionAgent/)

## Project status

SecFusionAgent is at the **M1–M3 Data Plane / M3→M4 handoff verified** stage. The data plane now covers hot vulnerability working sets, durable evidence/canonical knowledge, provider enrichment, Incident Watch, managed HTML/PDF/plain documents, GitHub development objects, materialized current views, time-bounded Internet asset observations and the Case/Trajectory/Experience storage seam. `make verify-m3` verifies the handoff with fast tests, source ownership/lifecycle checks, real PostgreSQL/pgvector/FTS, separated Redis failure domains, outbox→Celery replay/idempotency and a real S3-compatible ArtifactStore round trip. M4 task routing, query construction, retrieval/perception, investigation state, Agent runtime and M6 decision remain intentionally outside the M1–M3 data-plane implementation and are specified in Technical Design 2.

The current local quality gate:

```text
ruff        lint / import / Python correctness checks
mypy        static type checking
pytest      domain, replay, state-transition and contract tests
```

Repository CI continuously runs `ruff`, `mypy`, and `pytest`. The current fast gate is **97 passed + 6 infrastructure tests skipped by default**. `make integration-core` runs **5/5** real PostgreSQL/pgvector/FTS, Redis, outbox/Celery and M3-handoff tests; `make integration-object-store` runs the real S3-compatible ArtifactStore round trip. The last recorded live-probe snapshot is **41 OK / 10 provider-blocked / 5 transient failures / 1 rate-limited / 7 auth-required**. It is a point-in-time reachability report, not an M3 acceptance gate; anti-bot, network, rate-limit and credential handling remain later provider-hardening work. Fast SQLite/fixture tests remain useful for deterministic contracts but are not treated as infrastructure evidence.

## System overview

The public documentation site contains two interactive Archify views generated from the authoritative specifications:

- [Technical Design 1](https://jiale-li-orion.github.io/SecFusionAgent/tech-design.en.html) shows Acquisition, the four `retention_mode` lifecycles, the Evidence boundary, durable state and asynchronous consumers.
- [Technical Design 2](https://jiale-li-orion.github.io/SecFusionAgent/diagrams/tech-design-lower.en.html) shows task routing, Perception, Investigation State, bounded execution and decision flow.
- [Requirements](https://jiale-li-orion.github.io/SecFusionAgent/requirements.en.html) shows the M1–M8 product modules, C1–C3 cross-cutting constraints and acceptance semantics.

The system maintains source protocols, runtime lifecycle, canonical knowledge and derived read models separately: provider adapters interpret external protocols; the acquisition runtime records every scheduled / on-demand read; EvidenceIngress fixes the raw revision; canonical knowledge holds long-lived facts and provenance; projections, caches and later retrieval indexes are all rebuildable state.

## Implemented data paths

| Path | Current implementation | Purpose |
| --- | --- | --- |
| Hot Bug Stream | NVD + CVE Program/cvelistV5 → provider projection → Redis hot working set → durable canonical promotion | Keep high-frequency vulnerability feeds fresh without copying the full vulnerability history into the local long-term store |
| Vulnerability Enrichment | OSV / GitHub Global Advisory / CISA KEV → child AcquisitionRun → EvidenceIngress → claims / relations | Add package, fix, KEV and advisory information to vulnerabilities already promoted into durable knowledge |
| Managed Content | PDF/plain/HTML/XHTML durable document revision/chunks → lexical FTS + provider-neutral dense embedding → evidence-gated semantic extraction | Build a retrieval-ready research corpus whose semantic claims still resolve to a specific source revision and verbatim document span |
| Structured Source Index | GitHub target repositories + explicit advisory references → Repo / Issue / PullRequest / Commit / Release objects and deterministic relations | Maintain priority AI infrastructure state and a development graph without guessing fix relations from semantic similarity |
| Incident Watch | RSS / BlockBeats HTML breaking signal → deterministic anchor extraction → candidate correlation → durable incident timeline | Organize breaking reports and later independent evidence into security incidents without treating reprints as corroboration |
| Current Projection | knowledge / incident change → transactional outbox → vulnerability / affected-version / fix-status / repo-security / incident views | Provide low-cost retrieval-ready current state while preserving underlying history, evidence and conflicts |
| Internet Asset Observation | on-demand Shodan / Censys / FOFA / ZoomEye → provider-normalized AssetObservation → explicit EvidenceIngress promotion | Preserve query/provider/time provenance without turning volatile asset search results into permanent knowledge by default |
| Investigation Memory | Case → append-only Trajectory → Experience candidate / version / evaluation | Store evaluable, versioned procedural experience for later Agent investigation |

Built-in source definitions live in [`config/sources/`](config/sources/); whether a source enters the hot cache, the durable corpus, the structured index or incident staging is decided explicitly by `SourceDefinition.retention_mode`.

The concrete source commitments projected by the website are tracked in [`config/source-inventory.json`](config/source-inventory.json). The current inventory maps **99/99 website entries** to either a fixed/grouped source owner or an executable dynamic resolver. The repository currently contains **63 SourceDefinition records**, all of which have a live-probe owner; the real PostgreSQL registry also syncs all 63 definitions and source states. `make source-inventory-check` verifies Chinese-catalog identity plus bilingual catalog structural parity, while `make verify-data-sources` adds deterministic source/runtime ownership tests. `make probe-live-sources` is kept as a manual reachability report. Lifecycle tests additionally require every configured retention mode to have an executable runtime owner: `time_bounded` sources stay out of the scheduler and have an explicit downstream consumer, every Hot Bug adapter has both hot and durable normalization, and every Incident adapter has a registered signal extractor.

## Evidence and knowledge model

SecFusionAgent stores what a source published separately from the knowledge the system currently treats as usable.

`Observation` describes one acquisition of an external object revision; `EvidenceArtifact` fixes raw content that must be retained long term; `EvidenceLink` connects an object, claim or relation back to its observation/artifact and locator. Long-lived knowledge is expressed as `Object / ExternalIdentifier / Claim / Relation`, and knowledge revisions preserve its evolution history.

A new revision from a snapshot-style provider supersedes the previous current claim / relation from **the same source**; differences from other sources remain side by side, and the current projection exposes conflicts and alternatives. Corrections therefore never overwrite history, and multi-source conflicts are not silently adjudicated during ingest.

Every new external read produced by enrichment re-enters `AcquisitionRun → IngestEnvelope → EvidenceIngress`; a processor never writes an unrecorded HTTP response directly into knowledge.

## Incident intelligence

Incident Watch uses a separate lifecycle. Breaking sources first enter a short-lived `SignalItem / IncidentCandidate` working set; only incidents that meet promotion conditions enter durable incident storage.

Multi-source confirmation is computed as **independent sources supporting the same verifiable strong anchor**. `upstream_source` identifies reprint dependencies, so several outlets repeating one original report are not wrongly counted as independent corroboration. Current strong anchors include verifiable identifiers such as CVE/GHSA, transaction hash, address, IOC, domain/IP, incident/advisory ID and commit.

Once an incident enters durable state it retains an append-only timeline and source links; later official statements, forensic analysis, fund-flow changes and impact-scope updates are appended rather than repeatedly overwriting a static news record.

## Investigation experience

Investigation is modeled as `Case` plus an append-only `Trajectory`. A trajectory records provider queries, tool calls, evidence references, the experience version in use, outcome, latency and cost, giving later Agent Eval and replay their base data.

Reusable experience enters a separate versioned lifecycle:

```text
Trajectory
    ↓ extract
ExperienceCandidate
    ↓ evaluation / replay
validated
    ↓ activation
active
    ↓ superseded or invalidated
 deprecated
```

Experience stores scope, triggers, recommended actions, evidence expectations, failure modes, stop conditions and fallbacks. It is planning memory and holds no security evidence authority; a later task must still acquire current evidence before forming factual conclusions.

## Repository layout

```text
SecFusionAgent/
├── apps/
│   ├── api/                 # FastAPI application and HTTP routes
│   └── worker/              # Celery tasks, scheduler and outbox consumers
│
├── packages/
│   ├── sources/             # provider contracts, registry and source adapters
│   ├── monitoring/          # acquisition lifecycle and retention-mode collectors
│   ├── intelligence/        # evidence, canonical knowledge, incident and projections
│   ├── enrichment/          # provider-backed vulnerability enrichment
│   ├── investigation/       # Case, Trajectory and Experience lifecycle
│   └── shared/              # configuration, database and generic outbox primitives
│
├── config/
│   ├── sources/             # declarative SourceDefinition registry
│   └── env.example          # runtime configuration interface
│
├── alembic/                 # forward database migration history
├── deploy/                  # local/runtime deployment definitions
├── scripts/                 # engineering and probe entry points
├── tests/                   # repository-level architecture tests and fixtures
├── .github/                 # repository automation
├── PRODUCT-REPO-STANDARD.md
├── PRODUCT-REPO-STANDARD.zh.md
└── AGENTS.md
```

Package ownership and dependency direction are repository contracts, not directory conventions. `packages/sources` does not own scheduler state; `packages/monitoring/acquisition` owns durable acquisition lifecycle; `packages/intelligence/knowledge` owns canonical knowledge contracts and writes. [`tests/test_architecture_dependencies.py`](tests/test_architecture_dependencies.py) checks these dependency directions automatically.

## Development

### Prerequisites

- Python **3.12+**
- [`uv`](https://docs.astral.sh/uv/)
- Docker with Compose support for the local PostgreSQL / Redis / MinIO stack

The runtime has no cloud-vendor requirement. Container registry mirrors, proxies and credentials are host-level configuration and are intentionally kept outside the repository contract.

### Install dependencies

```bash
make sync
```

Equivalent command:

```bash
uv sync --dev
```

### Configure the environment

[`config/env.example`](config/env.example) defines the supported configuration surface. Export the required `SECFUSION_*` variables or load equivalent values through your local environment management.

The default development topology uses separate Redis failure domains:

- `redis-broker`: durable-ish task transport with `noeviction` policy;
- `redis-cache`: bounded LFU working set for Hot Bug and Incident staging.

API keys are optional for sources that permit unauthenticated access, but provider rate limits may be substantially lower. Secrets must never be committed to the repository.

### Start local infrastructure

```bash
make dev-up
make migrate
make sync-sources
```

`make dev-up-core` is the verified local core path for PostgreSQL/pgvector and the two Redis failure domains. `make dev-up` additionally asks for the configured MinIO deployment; that MinIO-specific image path is still tracked as an engineering blocker even though the S3-compatible ArtifactStore contract itself is verified against a pinned LocalStack Community integration provider.

Stop the local stack with:

```bash
make dev-down
```

### Run the API

```bash
uv run uvicorn apps.api.main:app --reload
```

Current HTTP surface includes:

```text
GET /health/live
GET /api/v1/vulnerabilities/{cve_id}
```

The API reads canonical knowledge/current repository state; it does not bypass the ingestion and evidence pipeline to query providers directly.

### Run collection and background workers

Start the scheduler:

```bash
make scheduler
```

The current task topology uses separate Celery queues for collection, enrichment and indexing/projection work. During full local development, run a worker subscribed to the active queues:

```bash
uv run celery -A apps.worker.celery_app:celery_app worker \
  -l INFO \
  -Q collection,enrichment,indexing
```

`make worker` currently starts the collection queue only and is useful when isolating M1 collection behavior.

### Run focused probes

Collect a small NVD modification window into the Hot Bug working set:

```bash
make probe-nvd
```

Promote one cached CVE into durable evidence and canonical knowledge:

```bash
make promote-hot CVE=CVE-YYYY-NNNN
```

Probes answer bounded integration questions. Stable product behavior belongs in packages, migrations and tests rather than accumulating in scripts.

## Quality gates

Run the fast repository gate while iterating:

```bash
make check
```

Run the complete M3 closeout gate before changing the handoff boundary:

```bash
make verify-m3
```

Focused infrastructure/source gates are also available:

```bash
make integration-core
make integration-object-store
make source-inventory-check
make verify-data-sources
make probe-live-sources
```

Individual commands are available when iterating on a focused change:

```bash
make lint
make typecheck
make test
```

`make check` is the repository-level reproducible gate used during development. Changes to persistence, queues, external adapters or deployment additionally require the relevant integration probe once the corresponding infrastructure is available.

## Engineering invariants

The current implementation is organized around several invariants that should remain visible in code review:

1. Important knowledge remains traceable to evidence.
2. Raw durable evidence is immutable; derived state is rebuildable.
3. External content is untrusted input, including content later consumed by an LLM.
4. New provider reads create observable acquisition state instead of bypassing M1/M2.
5. Replay and retry rely on stable idempotency keys and versioned state.
6. Same-source corrections preserve history; cross-source disagreement remains explicit.
7. Agent trajectories and reusable experience are observable and versioned.
8. Package dependencies follow ownership direction and remain acyclic.

The detailed rationale, failure cases and revisit conditions for these decisions are maintained in the project Wiki rather than duplicated into source comments or this README.

## Documentation

The code repository and Wiki have separate ownership:

- **Repository** — executable source, tests, migrations, deployment, scripts, CI and repository governance.
- **Wiki** — requirements, Technical Design, data-source semantics, security-domain studies, design decisions, probes, runbooks and project evolution.

Start with:

- [Requirements SPEC](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Requirements-SPEC) — product scope, constraints and acceptance semantics.
- [Technical Design 1](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Technical-Design-1) — M1–M3 runtime architecture, storage semantics, processing paths and implementation baseline.
- [Technical Design 2](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Technical-Design-2) — M4–M6 task routing, Perception, Investigation State, bounded execution and Decision contracts.
- [Data Sources and Processing](https://github.com/jiale-li-orion/SecFusionAgent/wiki/01-Data-Sources-and-Processing) — source classes, lifecycle and data semantics.
- [CTI Baseline Reuse and Ownership](https://github.com/jiale-li-orion/SecFusionAgent/wiki/02-CTI-Baseline-Reuse-and-Ownership) — CTI capability boundaries and reuse policy.
- [Normative Knowledge and Policy](https://github.com/jiale-li-orion/SecFusionAgent/wiki/03-Normative-Knowledge-and-Policy) — standards, policy and normative knowledge.
- [AI / Model / Data / Agent Security](https://github.com/jiale-li-orion/SecFusionAgent/wiki/04-AI-Model-Data-and-Agent-Application-Security) — AI-specific risk semantics.
- [Incident & News Intelligence](https://github.com/jiale-li-orion/SecFusionAgent/wiki/05-Incident-News-Intelligence) — incident source roles, correlation and event lifecycle.
- [`WEB-PRESENTATION-STANDARD.zh.md`](WEB-PRESENTATION-STANDARD.zh.md) — GitHub Pages, Archify, bilingual presentation and CI/CD rules.

Repository organization and contribution rules are defined by [`PRODUCT-REPO-STANDARD.md`](PRODUCT-REPO-STANDARD.md) and [`PRODUCT-REPO-STANDARD.zh.md`](PRODUCT-REPO-STANDARD.zh.md). Agent-assisted changes additionally follow [`AGENTS.md`](AGENTS.md).

## Roadmap

The next engineering boundary is the transition from the verified M3 handoff into the Investigation / Retrieval / Reasoning plane:

- run one live semantic+dense provider E2E once model credentials/endpoint are supplied;
- validate deterministic fix-boundary promotion on a real target-repo OSV `GIT fixed` sample when one is available;
- keep provider-access blockers explicit while preserving the closed source-lifecycle contracts;
- extend Incident primary/forensic follow-up and on-chain telemetry beyond the current source set;
- implement the Technical Design 2 fast path: `TaskSpec → ContextBinding → ExecutionProfile → L0/L1 query`;
- add M4 `InvestigationState / EvidenceNeed / StatePatch / InvestigationSnapshot` and local Perception reads over the verified M3 state;
- add dynamic capability visibility, hierarchical budgets, bounded loops and sandbox/network/identity enforcement before active Agent investigation;
- establish M6 `DecisionResult` plus fixed M7 replay/evaluation protocols for routing, perception, state integration and evidence use;
- add security regression for poisoned sources, indirect prompt injection, malicious tool output and privilege boundaries.

Requirements remain the authority for product scope; roadmap ordering follows dependency and integration risk rather than UI completeness.
