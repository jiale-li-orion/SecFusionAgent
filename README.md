# SecFusionAgent

English | [中文](README.zh.md)

[![CI](https://github.com/jiale-li-orion/SecFusionAgent/actions/workflows/ci.yml/badge.svg)](https://github.com/jiale-li-orion/SecFusionAgent/actions/workflows/ci.yml) [![Pages](https://github.com/jiale-li-orion/SecFusionAgent/actions/workflows/pages.yml/badge.svg)](https://github.com/jiale-li-orion/SecFusionAgent/actions/workflows/pages.yml)

**Evidence-first AI Security Intelligence System**
**Agent-driven AI security intelligence fusion and assessment**

SecFusionAgent builds a continuously evolving intelligence system for AI security vulnerabilities, research progress and security incidents. The system continuously acquires new or changed content from public vulnerability databases, project repositories, security advisories, research papers and incident sources, fixes external data as traceable evidence, then performs normalization, correlation, enrichment, incident tracking and follow-up investigation.

The Agent here sits on top of a verifiable data plane. External reads carry acquisition provenance; important conclusions trace back to the original observation / artifact; historical revisions are retained and current views are rebuildable. Agent work then covers investigation, tool calls and reasoning; it does not replace evidence authority.

[Architecture Views](https://jiale-li-orion.github.io/SecFusionAgent/index.en.html) · [Project Wiki](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Home.en) · [Requirements](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Requirements-SPEC.en) · [Technical Design](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Technical-Design.en) · Website：[jiale-li-orion.github.io/SecFusionAgent](https://jiale-li-orion.github.io/SecFusionAgent/)

## Project status

SecFusionAgent is at the **M1–M3 Data Plane first-pass implementation / integration probe** stage. The first implementation round covers multiple source lifecycles, canonical knowledge, provider-backed enrichment, Incident Watch, managed documents, current projections and the storage boundary of Investigation Experience; real infrastructure integration with PostgreSQL, Redis, MinIO and Celery is still being verified.

The current local quality gate:

```text
ruff        lint / import / Python correctness checks
mypy        static type checking
pytest      domain, replay, state-transition and contract tests
```

Repository CI continuously runs `ruff`, `mypy`, and `pytest`. Fast tests mostly use fixtures and a lightweight local database to verify deterministic contracts; they do not replace integration tests for PostgreSQL transactions, queue recovery, object storage, concurrency or deployment.

## System overview

The public documentation site contains two interactive Archify views generated from the authoritative specifications:

- [Technical Design — Data Plane](https://jiale-li-orion.github.io/SecFusionAgent/tech-design.en.html) shows Acquisition, the four `retention_mode` lifecycles, the Evidence boundary, durable state and asynchronous consumers.
- [Requirements — Module Flow](https://jiale-li-orion.github.io/SecFusionAgent/requirements.en.html) shows the M1–M8 product modules, C1–C3 cross-cutting constraints and acceptance semantics.

The system maintains source protocols, runtime lifecycle, canonical knowledge and derived read models separately: provider adapters interpret external protocols; the acquisition runtime records every scheduled / on-demand read; EvidenceIngress fixes the raw revision; canonical knowledge holds long-lived facts and provenance; projections, caches and later retrieval indexes are all rebuildable state.

## Implemented data paths

| Path | Current implementation | Purpose |
| --- | --- | --- |
| Hot Bug Stream | NVD CVE API → normalization → Redis hot working set → durable promotion | Keep high-frequency vulnerability feeds fresh without copying the full vulnerability history into the local long-term store |
| Vulnerability Enrichment | OSV / GitHub Global Advisory / CISA KEV → child AcquisitionRun → EvidenceIngress → claims / relations | Add package, fix, KEV and advisory information to vulnerabilities already promoted into durable knowledge |
| Managed Content | arXiv Atom discovery → versioned PDF artifact → document revision → page-oriented chunks | Build a research corpus that evolves over the long term and traces back to a specific revision / page |
| Structured Source Index | GitHub target repositories → repo revision cursor → `Repo` object / claims | Continuously maintain structured state for priority AI infrastructure repositories |
| Incident Watch | RSS breaking source → strong-anchor correlation → candidate watch → durable incident timeline | Organize breaking reports and later independent evidence into security incidents that keep accumulating enrichment |
| Current Projection | knowledge / incident change → transactional outbox → projection rebuild | Provide a low-cost current view for the API and later retrieval while preserving underlying history and conflicts |
| Investigation Memory | Case → append-only Trajectory → Experience candidate / version / evaluation | Store evaluable, versioned procedural experience for later Agent investigation |

Built-in source definitions live in [`config/sources/`](config/sources/); whether a source enters the hot cache, the durable corpus, the structured index or incident staging is decided explicitly by `SourceDefinition.retention_mode`.

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

This starts the local PostgreSQL/pgvector, Redis Broker, Redis Hot Cache and MinIO services, applies Alembic migrations, then synchronizes declarative source definitions into runtime state.

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

Run the complete local gate before submitting a change:

```bash
make check
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
- [Technical Design](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Technical-Design) — runtime architecture, storage semantics, M1–M3 processing paths and implementation baseline.
- [Data Sources and Processing](https://github.com/jiale-li-orion/SecFusionAgent/wiki/01-Data-Sources-and-Processing) — source classes, lifecycle and data semantics.
- [CTI Baseline Reuse and Ownership](https://github.com/jiale-li-orion/SecFusionAgent/wiki/02-CTI-Baseline-Reuse-and-Ownership) — CTI capability boundaries and reuse policy.
- [Normative Knowledge and Policy](https://github.com/jiale-li-orion/SecFusionAgent/wiki/03-Normative-Knowledge-and-Policy) — standards, policy and normative knowledge.
- [AI / Model / Data / Agent Security](https://github.com/jiale-li-orion/SecFusionAgent/wiki/04-AI-Model-Data-and-Agent-Application-Security) — AI-specific risk semantics.
- [Incident & News Intelligence](https://github.com/jiale-li-orion/SecFusionAgent/wiki/05-Incident-News-Intelligence) — incident source roles, correlation and event lifecycle.
- [`WEB-PRESENTATION-STANDARD.zh.md`](WEB-PRESENTATION-STANDARD.zh.md) — GitHub Pages, Archify, bilingual presentation and CI/CD rules.

Repository organization and contribution rules are defined by [`PRODUCT-REPO-STANDARD.md`](PRODUCT-REPO-STANDARD.md) and [`PRODUCT-REPO-STANDARD.zh.md`](PRODUCT-REPO-STANDARD.zh.md). Agent-assisted changes additionally follow [`AGENTS.md`](AGENTS.md).

## Roadmap

The next engineering boundary is the transition from a first-pass Data Plane to verified runtime and retrieval infrastructure:

- complete PostgreSQL / Redis / MinIO / Celery integration probes and recovery tests;
- expand GitHub monitoring from repository metadata to issue / PR / commit / release relations;
- add primary and forensic Incident sources beyond the first RSS breaking-source path;
- extend Managed Content to HTML sources and semantic extraction;
- implement rebuildable sparse + dense retrieval and query construction over current/canonical knowledge;
- connect Investigation Case / Trajectory state to the Agent runtime;
- establish fixed M7 evaluation protocols for enrichment, retrieval, QA, Agent trajectories and Experience activation;
- add security regression for poisoned sources, indirect prompt injection, malicious tool output and privilege boundaries.

Requirements remain the authority for product scope; roadmap ordering follows dependency and integration risk rather than UI completeness.
