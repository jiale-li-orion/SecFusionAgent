# SecFusionAgent

English | [中文](README.zh.md)

[![CI](https://github.com/jiale-li-orion/SecFusionAgent/actions/workflows/ci.yml/badge.svg)](https://github.com/jiale-li-orion/SecFusionAgent/actions/workflows/ci.yml) [![Pages](https://github.com/jiale-li-orion/SecFusionAgent/actions/workflows/pages.yml/badge.svg)](https://github.com/jiale-li-orion/SecFusionAgent/actions/workflows/pages.yml)

**Agent-driven AI security intelligence fusion and assessment.** SecFusionAgent collects vulnerabilities, research, code, advisories and security incidents, retains traceable evidence, and supports intelligence reading, event timelines, document discovery and cited questions/investigations.

`main` contains the M1–M3 data plane, M4–M6 investigation and reasoning, task execution controls, evaluation infrastructure and account-owned Product Web. This guide describes the current product. See the [acceptance register](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Current-Acceptance) for verified scope and remaining work.

## Product spaces

| Space | Current behavior |
| --- | --- |
| World | Eight source directions, source health, material discovery and Hot exploration; featured incidents/tools and paged CVEs keep cache residency distinct from durable evidence |
| Intelligence | Public briefing summaries, recommendations/following, event timelines and a library filtered by category, publisher and multi-label subject; expandable sources and evidence |
| Ask | Natural questions, multi-turn sessions and cited reports; evidence gaps enter investigation with immutable per-turn reports and evidence/model/task audit |
| Workspace | Account, interests, conversations and investigations; Operations exposes task execution and service health |

The app lives at `/product/`. Shared material and public briefings support anonymous reading; private conversations, investigations, reports and tasks enforce account ownership. A public HTML report requires an explicit publication record. Private investigations do not become public automatically.

The interface uses local fonts, open reading compositions and page-specific pigment-development/diffusion motion, with reduced-motion support, offscreen suspension, keyboard controls and mobile layouts. Events follow a timeline. Library subject groupings are lexical browsing facets, not claims of model-derived semantic clustering. Hot discovery lives in World.

## Operating mode

Local Compose and the example configuration default to pausing unattended model calls:

```dotenv
SECFUSION_BACKGROUND_LLM_ENABLED=false
SECFUSION_EDITORIAL_ENABLED=false
```

| Continues | Automatic work paused |
| --- | --- |
| Collection, raw evidence retention, lexical indexing, deterministic enrichment and projections | Document embeddings, semantic/normative model extraction, editorial and new WATCH wakeups |
| User-requested QA, investigation and explicit operator report generation | Unattended invocation of the stages above |
| Existing public/private HTML report reads through deterministic rendering | Browsing retained content is unaffected |

Set both flags explicitly for standalone processes: base `Settings` preserves the compatible enabled background-model default. Recreate/restart the scheduler, worker and Task Event scheduler after changes; in-flight model requests may finish. Resuming does not automatically backfill skipped work. No daily monetary cap is introduced; interactive requests still consume tokens. See [worker operations](apps/worker/README.md).

## Data and report path

```text
Registered source → AcquisitionRun → raw Observation / Artifact
                  → Evidence / Knowledge / DocumentRevision
                  → lexical index, structured enrichment, incidents and projections
                  → intelligence reading / controlled investigation / cited decision
                  → separate summary, review and controlled HTML rendering
```

- External content is data. Model proposals pass citation and state gates before becoming decisions.
- Source revisions remain retained; same-source corrections preserve history and cross-source conflicts remain explicit.
- Material quality gates reject error pages, delivery templates and missing bodies; maintenance can reparse retained evidence.
- Investigation composes local perception, official NVD reads, registered public HTML and exact development records for configured GitHub repositories through policy, budget, acquisition and evidence promotion.
- Reports lead with a separately cited summary, then sourced prose and analysis. Reviewed structured output feeds a deterministic HTML renderer; reading invokes no model and model output cannot introduce scripts or widen access.
- Task Runtime owns idempotency, cancellation, events/SSE, delegation, recovery and budget traces. Complete historical-world re-execution remains open.

## Local development

Requires Python 3.12, uv, Node.js 22 and Docker Compose. Inject credentials through the environment or untracked local configuration.

```bash
uv sync --dev --frozen
# Configure local values from config/env.example; start PostgreSQL and Redis roles.
make dev-up
make migrate
make sync-sources
uv run uvicorn apps.api.main:app --reload
```

In another terminal:

```bash
cd apps/web
npm ci
npm run dev
```

Vite proxies `/api` to the local API; configure `SECFUSION_API_PROXY` for another port. `make data-plane-up` starts the long-running collection/task stack; inspect it with `make data-plane-status` and `make data-plane-logs`. Volumes and `.local/secfusion-artifacts` retain durable state after the shell closes. `make data-plane-down` stops runtime processes; `make dev-down` stops local services. See [deployment](deploy/PRODUCT-DEPLOY.md) for production contracts.

## Verification

```bash
make check
cd apps/web && npm run lint && npm run build
# Return to the repository root:
python scripts/check_product_gate.py --static-only
python scripts/check_product_deploy.py
make evidence-doc-check
```

PostgreSQL/Redis and S3-compatible integration use `make integration-core` and `make integration-object-store`. `make source-inventory-check` checks the source catalog. Network probes and paid model evaluations are explicit operations outside these offline gates.

The 2026-10-16 baseline `6654199` passed 890 non-integration tests (12 integration tests excluded), Ruff, mypy, frontend build/deployment gates and remote CI. This does not constitute a fresh model-quality benchmark, production disaster-recovery drill or proof that every provider is reachable today.

## Module guides

| Module | Ownership |
| --- | --- |
| [apps/web](apps/web/README.md) | Product Web, components and motion |
| [apps/api](apps/api/README.md) | HTTP, accounts, SSE and access control |
| [apps/application](apps/application/README.md) | Question, investigation, intelligence and briefing use cases |
| [apps/worker](apps/worker/README.md) | Collection/task processes and background-model controls |
| [packages/sources](packages/sources/README.md) | Source definitions and adapters |
| [packages/monitoring](packages/monitoring/README.md) | Acquisition scheduling, retries and cursors |
| [packages/intelligence](packages/intelligence/README.md) | Evidence, knowledge, documents, incidents and projections |
| [packages/enrichment](packages/enrichment/README.md) | Structured, semantic and normative enrichment |
| [packages/task_runtime](packages/task_runtime/README.md) | Task, context, event and delegation protocols |
| [packages/runtime](packages/runtime/README.md) | Policy, budget, execution and model accounting |
| [packages/investigation](packages/investigation/README.md) | Investigation state, perception, skills and replay |
| [packages/reasoning](packages/reasoning/README.md) | Cited decisions, summaries, editorial review and HTML |
| [packages/evaluation](packages/evaluation/README.md) | Frozen cases, evaluation and evidence closure |
| [packages/shared](packages/shared/README.md) | Configuration, database and infrastructure protocols |

## Retained evaluation and source configuration

`current.json` means the latest saved result, not live health or a new evaluation of HEAD. The following evidence retains its deployment, samples and measurement window; a code update does not rewrite those results.

<!-- BEGIN GENERATED SCOREBOARD -->
## Retained evaluation and current source configuration

| Metric | Retained formal result |
| --- | ---: |
| Source category coverage | **8/8** (target ≥7) |
| M1 monitoring latency | **p50 357.709s (5.96min) / p95 7241.893s (2.01h) / ≤6h 100.000% (12/12)** |
| M3 enrichment Precision / Recall | **99.659% / 99.659% (TP=292, FP=1, FN=1)** |
| Controlled fault recovery | **100.000% (3/3)** |
| M6 QA | **Accuracy 100.000% / interactive max 3.655s** |

**Current source configuration (not live health): 106 catalog entries → 71 executable sources → 43 scheduled monitors; 8 product categories, with active scheduled monitoring in 7/8 categories and `assets` intentionally query-time.**
**Saved runtime snapshot: `2026-10-08T19:18:08.614492+00:00`; monitoring epoch: `2026-10-02T04:19:42+08:00`; scheduled-source health 36 healthy / 1 degraded / 2 blocked; epoch Evidence integrity 100.000%.**
**Hour preceding that snapshot: Run OK 85.714%; provider-boundary fail 14.286%; runtime-owned fail 0.000%; queue p95 102.077s (1.70min); execution p95 108.106s (1.80min).**

Every value above is generated from benchmark/source configuration rather than copied by hand; run/deployment/provenance details remain in the formal evidence section below.
<!-- END GENERATED SCOREBOARD -->

<details>
<summary>Evaluation provenance and reproduction</summary>

<!-- BEGIN GENERATED EVALUATION STATUS -->
## Retained formal evaluation evidence (generated)

This block is rendered from `benchmarks/**/current*.json`. Run `make evidence-doc` after benchmark changes; `make evidence-doc-check` fails when Markdown drifts from structured evidence.

| Retained numeric target | Metric | Observed | Threshold | Status |
| --- | --- | ---: | ---: | --- |
| `source_category_coverage` | `m1.source_category_count` | 8 | >= 7 | **pass** |
| `enrichment_precision` | `m3.micro_precision` | 99.659% | >= 95.000% | **pass** |
| `enrichment_recall` | `m3.micro_recall` | 99.659% | >= 95.000% | **pass** |
| `qa_accuracy` | `m6.answer_accuracy` | 100.000% | >= 95.000% | **pass** |
| `qa_interactive_latency` | `m6.interactive_latency_seconds` | 3.655s | <= 5.000s | **pass** |

Retained CompetitionReport: `eb0a1c43-a786-434e-904a-fd976d751105` on `deployment:2713f58f83915b2d0d0a9621ed4b7ac7`, generated `2026-10-08T15:37:32.851706Z`; not a re-evaluation of current HEAD.

M1 fixed window `2026-10-01T10:00:00+00:00` → `2026-10-01T14:02:00+00:00`: 12/12 evaluable samples, p50 357.709s (5.96min), p95 7241.893s (2.01h), within 6h 100.000%; source categories=8.

Selected M3 runs aggregate to TP=292, FP=1, FN=1, precision=99.659%, recall=99.659%. Controlled engineering recovery `engineering-fault-recovery@6` is 100.000% across 3 cases.

Evaluation areas not selected into the current CompetitionReport: `M2 parser/entity/evidence diagnostics`, `Agent runtime`, `Long Investigation completion`, `Security adversarial hard gates`, `Security adversarial breadth`. Their separate controlled/diagnostic evidence is not mixed into the report's six-run formal profile.

Across the evaluation infrastructure, 85/87 core metrics have durable observations at the current MetricDefinition revision; 15 metric groups are observed and 2 are partial. The only unobserved core metrics are `runtime.capability_external_cost`, `runtime.model_provider_cost`; both are exact monetary costs that remain absent when the provider/executor does not report them and are never inferred from token counts or public price tables.

Query the durable rows with `make benchmark-query METRIC=m3.micro_precision`; reproduce the report projection with `make competition-render-doc`; refresh every maintained evidence projection with `make evidence-doc`; verify without writes with `make evidence-doc-check`.
<!-- END GENERATED EVALUATION STATUS -->

</details>

## Remaining acceptance boundaries

Complete historical Knowledge reads/Agent re-execution, real OpenShell/Firecracker isolation acceptance, full A2A write/subscription transport, M3 model-budget settlement, production restore/alert drills and broader live difficult-question/external-capability denominators remain open. Email verification, password recovery and OAuth are unimplemented; generic manual resume and semantic non-exact retrieval reuse are not delivered.

Evidence, closure criteria and priorities are maintained in the [acceptance register](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Current-Acceptance), rather than duplicated as stale TODO lists across README files.

## Design and contribution

[Wiki](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Home.en) · [PRD](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Requirements-SPEC.en) · [TD1 data plane](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Technical-Design-1.en) · [TD2 investigation](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Technical-Design-2.en) · [TD2A application](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Technical-Design-2A) · [TD3 evaluation](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Technical-Design-3) · [Engineering portal](https://jiale-li-orion.github.io/SecFusionAgent/)

This repository owns code, tests, migrations, configuration, module contracts and reproducible commands. The Wiki owns requirements, cross-module design, acceptance and historical reviews. Follow the [repository standard](PRODUCT-REPO-STANDARD.md) and [AGENTS](AGENTS.md). Secrets, runtime databases, downloaded corpora and model output stay outside Git.

Local competition deliverables (technical report, slides and source ZIP) are stored once under `../SecFusionAgent.wiki/交付成果/`; video masters, original captures and the editing workspace live under `.local/video-production/` here. Both directories are Git-ignored and are not copied into either public repository.
