# SecFusionAgent Product Repository Standard

English | [中文](PRODUCT-REPO-STANDARD.zh.md)

This standard defines directory responsibilities, code ownership, dependency direction, tests and benchmarks, configuration, runtime artifacts, CI/CD, version evolution, and agent-development rules for the SecFusionAgent source repository. Technical Design chooses concrete frameworks, databases, agent runtimes, and deployment platforms; this document governs how those implementations are organized once they enter the repository.

## Documentation and code authority

The Wiki owns the PRD, Technical Design, security-topic studies, research notes, solution comparisons, design decisions, runbooks, incident/postmortem records, and project evolution. The main repository owns source code, tests, benchmarks, deployment definitions, engineering scripts, CI configuration, and repository-governance files. A fact's repository determines its maintenance owner.

The root `README.md` is the code-repository entry point and contains the project identity, Wiki link, development entry point, and stable commands. `PRODUCT-REPO-STANDARD.md` / `.zh.md` define repository rules. `AGENTS.md` carries standing orders that apply to every agent session. Source comments and type declarations carry local contracts that must stay next to implementation, such as parameter semantics, exceptions, state invariants, and security preconditions.

Changes to architecture, interface semantics, evaluation protocols, or runtime behavior update code and Wiki in the same change cycle. Wiki pages record the applicable release, tag, or commit so historical checkouts can be matched to their design.

## Repository layout

Top-level directories follow long-lived responsibilities:

```text
SecFusionAgent/
├── apps/                    # runnable and deployable product entry points
│   ├── api/
│   ├── web/
│   └── worker/              # added when an independent background process exists
│
├── packages/                # product capability owners
│   ├── intelligence/        # security-intelligence domain semantics
│   ├── sources/             # external intelligence-source adapters
│   ├── monitoring/          # continuous collection, incremental updates, source health
│   ├── enrichment/          # enrichment, association, version/PoC/patch processing
│   ├── investigation/       # agent investigation and task lifecycle
│   ├── evaluation/          # eval runners, verifiers, metrics
│   ├── security_testing/    # adversarial / security regression
│   └── shared/              # shared infrastructure independent of business domains
│
├── tests/
│   ├── integration/
│   ├── e2e/
│   └── fixtures/
│
├── benchmarks/
│   ├── monitoring/
│   ├── enrichment/
│   ├── qa/
│   ├── agent/
│   └── security/
│
├── deploy/
├── scripts/
├── .github/
├── README.md
├── PRODUCT-REPO-STANDARD.md
└── PRODUCT-REPO-STANDARD.zh.md
```

Directories appear when their responsibility exists in the product. Technical Design may adjust names and language-specific organization; `apps`, capability owners, tests, benchmarks, deploy, and engineering tooling retain separate responsibilities.

`apps/` owns process startup, transport, and application bootstrap. HTTP routes, CLI entries, Web applications, and worker bootstrap live here. Reusable behavior such as intelligence association, agent investigation, and evaluation logic belongs to the owning capability package.

`packages/` is organized by domain or capability. A behavior receives an owner before it receives a file location. Incremental monitoring semantics and source health belong to `monitoring`; external-source protocols and parsing belong to `sources`; cross-source enrichment and association belong to `enrichment`; investigation state and orchestration belong to `investigation`.

A package gains sublayers such as `domain`, `application`, `adapters`, or `storage` when those areas have independent reasons to change. Directory structure follows real boundaries; file count and line count do not determine decomposition.

## Ownership and dependencies

Every stable behavior has one owner. Other modules consume that behavior through the owner's public contract. Cross-package dependencies form a directed acyclic graph; a cycle usually indicates that ownership, interface placement, or state ownership needs revision.

An interface belongs to the side that owns its semantics. Providers implement interfaces and consumers call them; provider-specific types, SDK objects, and exceptions remain at the adapter boundary. Replacing a provider preserves the domain contract.

`shared/` contains infrastructure independent of the security-intelligence domain and used by multiple stable consumers, such as generic time handling, serialization primitives, and controlled retry infrastructure. CVE version-range parsing, PoC-to-version matching, and vulnerability-severity logic belong to their domain owners.

Broad names such as `utils`, `helpers`, `common`, `misc`, and `base` require a concrete responsibility. When a file repeatedly absorbs unrelated behavior, ownership is re-evaluated and the file is split by responsibility.

## External systems and adapters

Vulnerability databases, vendor advisories, security communities, GitHub, paper sources, model providers, databases, message systems, file systems, browsers, and third-party APIs are external boundaries. Adapters translate external formats into internal contracts and own boundary-specific authentication, pagination, rate limits, cursors, retries, timestamp handling, and parsing rules.

A source adapter reliably retrieves and interprets source data. Cross-source deduplication, entity resolution, enrichment, and security analysis belong to their capability owners. When a source protocol changes, the change converges on the adapter and its contract tests.

Third-party failures are translated at the boundary into explicit project failures. Business logic consumes stable error types and states, while runtime logs retain provider context needed for diagnosis.

## State, data, and migrations

Git stores source code, schemas, migrations, fixtures, benchmark cases, gold/reference data, and snapshots that carry a contract. Runtime databases, crawl caches, real user data, local logs, temporary downloads, bulk model output, and one-off analysis results live as runtime artifacts or external storage.

Schemas and persistent formats evolve forward with releases. Published migrations retain their original contents; later corrections use new migrations. Database upgrade paths are reconstructable from migration history, and incompatible changes define an upgrade or recovery path before release.

Fixtures stay small, stable, and attributable. Real Web pages or API responses are reduced to the fields the test depends on while preserving enough provenance to explain the sample. Security-test payloads identify their purpose and execution boundary.

## Tests and benchmarks

Tests verify deterministic contracts; benchmarks measure AI and system quality. The two asset classes carry separate failure semantics, versions, and runtime costs.

Unit tests live with the capability owner and cover local rules, state transitions, boundary conditions, and failure paths. `tests/integration/` covers package boundaries, persistence, queues, and external-adapter composition. `tests/e2e/` verifies complete user paths from real product entry points. A bug fix adds a regression case that reliably reproduces the failure.

`benchmarks/` stores fixed tasks, gold/reference data, verifiers, runner configuration, and frozen inputs. Cases and gold data are versioned; semantic changes to gold create a new version and record the reason. Ordinary run results are artifacts; release baselines, competition-submission baselines, and results that carry a long-lived regression contract may be versioned.

Monitoring, enrichment, QA, agent, and security benchmarks are maintained separately because they use different samples, verifiers, and failure models. Aggregate metrics are computed from raw metrics, and raw results remain available.

Agent Eval records task success, tool selection, arguments, trajectories, recovery, timeouts, latency, and cost. Security benchmarks cover direct and indirect prompt injection, poisoned sources, malicious tool output, hallucinated evidence, tool misuse, privilege violations, and security tests for deterministic Web, backend, and storage components.

## Configuration, secrets, and environments

Values that vary by deployment enter explicit configuration. Configuration keys have stable names, types, defaults, and validation; missing critical configuration fails during startup with a direct diagnostic.

Secrets, tokens, cookies, private keys, and real accounts are injected through a secret store, environment variables, or untracked local files. `.env.example` defines the configuration interface and example formats. Test, benchmark, CI, and production environments preserve the same configuration semantics.

Security invariants and protocol constants remain in code contracts. Test doubles enter through explicit interfaces so test and production paths share the same business behavior.

## Scripts and generated artifacts

`scripts/` orchestrates existing capabilities: environment checks, code generation, migrations, fixture construction, release helpers, and benchmark orchestration. Business rules stay with their capability owners, and scripts call stable package entry points.

Frequent development actions are exposed through stable commands. CI calls the same commands so local reproduction and CI execution share an entry point. Workflow YAML owns orchestration, while repository scripts or language-native commands own the checks themselves.

Generated artifacts identify their source of truth and generation command. Rebuildable temporary output is ignored; generated output that carries a release contract, baseline, or snapshot is updated in the same change as its generator.

## CI/CD and releases

CI gates are organized by risk. Ordinary changes run formatting/linting, static analysis, type checking, unit tests, and relevant integration/security checks. Changes to package contracts, schemas, agent behavior, evaluation, or deployment run the corresponding e2e and benchmark regressions. Expensive full matrices may run on main, nightly, or release gates.

Each gate has an owner and a stable command. When a rule changes, the gate, implementation, and corresponding Wiki explanation change together. CI failures preserve their original signal while code, tests, environment, or the rule itself is corrected.

Release artifacts are produced from version-controlled source by a fixed build process. Tags, artifacts, migrations, and benchmark baselines can be correlated. Production fixes return to source and enter the next release so server state remains traceable to the repository.

Rollback depends on rollback-capable artifacts, configuration, and data compatibility together. Irreversible migrations define a forward-fix, backup-restore, or data-migration path before release.

## Observability and failures

Logs record events, states, identifiers, and error context. Collection, enrichment, agent investigation, and final answers share stable request/task/case identifiers for cross-process tracing. Secrets and sensitive content are handled before log emission.

Metrics describe long-lived system state such as source freshness, task success rate, queue backlog, provider latency, tool failures, and benchmark regression. Traces describe the component path of an individual request. Logs, metrics, and traces respectively serve event records, aggregate observation, and call-path analysis.

Failures are classified as recoverable errors, task-terminating errors, or program bugs. Network instability and rate limits enter controlled retries; invalid parameters and permission failures terminate the current operation; internal invariant violations surface immediately. Retries carry count, backoff, timeout, and idempotency semantics.

## Git and change management

A commit expresses one independently reviewable change. Refactors, behavior changes, benchmark adjustments, and large formatting changes are committed separately to preserve review clarity and regression localization. Bug fixes and their regression tests land together.

PRs are scoped by behavior or capability. Cross-package changes explain why multiple owners change together. When one feature repeatedly touches unrelated packages, capability boundaries are re-evaluated.

The main branch stays buildable, testable, and deployable. Personal branches that rewrite published history use `--force-with-lease` after checking remote state. Shared branches preserve other contributors' published history through rebase, merge, or follow-up fixes.

## Naming and source rules

Top-level packages use concrete domain names such as `monitoring`, `enrichment`, and `investigation`. Classes, functions, and files name the object or action they own. Broad names such as `manager`, `helper`, `common`, `misc`, and `base` require a concrete responsibility during review.

Each language follows its ecosystem's canonical naming. Cross-language modules keep capability names discoverable while file naming follows the local toolchain.

Comments record contracts that code alone cannot express clearly: state invariants, timing, failures, compatibility, security conditions, and external constraints. Design rationale and evolution history live in the Wiki. TODOs name the missing behavior or triggering condition and follow one repository-wide priority convention.

## Agent-assisted development

Agents read the root rules, current capability, and relevant Wiki before changing the repository. After the change, they run the smallest check set that covers the changed behavior and report the commands and results actually executed.

The root `AGENTS.md` stores repository-wide standing orders and links to their owners. Capability-specific constraints live in scoped `AGENTS.md` files under the owning subtree. Scoped rules govern local behavior while root rules retain repository-wide meaning.

Prompts, temporary plans, scratch files, handoff text, and model output are work artifacts. Stable design conclusions enter the Wiki; long-lived mechanical rules become CI gates, linters, schema verifiers, or scoped instructions.

Large agent changes are decomposed by independently verifiable behavior. When domain semantics, schemas, APIs, frontend behavior, benchmarks, and deployment change together, the change explains their product dependency; independent changes become independent review units.

## Repository evolution

A package emerges when a capability gains independent state, interfaces, tests, and lifecycle. Small local helpers stay with the existing owner until that capability exists.

The repository periodically checks growth in `shared/utils`, features that span many packages, dependency cycles, and deep imports. These signals indicate that ownership may have drifted away from real change boundaries.

Removing a capability removes its entry points, tests, benchmarks, configuration, CI gates, and deployment references in the same evolution path. Explicit compatibility layers carry compatibility periods; Git retains implementation history.

## Review baseline

Engineering changes use the same review questions:

| Question | Passing condition |
| --- | --- |
| Who owns the behavior? | One capability owner is identifiable |
| Is dependency direction stable? | Package graph is acyclic and consumers use public contracts |
| Where do external systems terminate? | Provider/source/storage details stay at adapter boundaries |
| How do failures propagate? | Error states, retries, timeouts, and termination are observable |
| How is correctness verified? | The relevant unit / integration / e2e / regression layer has coverage |
| How is AI quality compared? | Model- or agent-dependent behavior has a fixed benchmark |
| How does data evolve? | Schemas, migrations, fixtures, and upgrade paths are reproducible |
| How are secrets protected? | Source, logs, fixtures, and artifacts contain no real sensitive values |
| Can CI be reproduced locally? | Gates invoke stable repository commands |
| Who owns documentation? | Product facts live in the Wiki; repository governance lives in the main repo |
| Can a release be rebuilt? | Source, build, artifact, migration, and baseline can be correlated |

New rules require a real failure, a clear contract, or a foreseeable high-cost risk. Directory aesthetics alone do not justify a repository rule.
