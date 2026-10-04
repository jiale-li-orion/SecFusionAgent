# `apps.web` — SecFusion Product App

`apps.web` is the user-facing SecFusionAgent product frontend.

The authoritative Product UI contract is [`SPEC.md`](SPEC.md). Product v1 exposes the complete Evidence Plane + Agent Runtime + Investigation/Decision + Operations/Evaluation story required by the competition and project Requirements.

## Boundary

The Product App is independent from:

- the project Wiki/Website, which explains the architecture and competition evidence;
- the retired Runtime Workbench surface; Product UI uses Product/Application contracts only;
- A2A transport DTOs, which are protocol compatibility rather than Product presentation contracts.

The Product browser must use stable Product/Application routes and Product-safe read models. It must not query internal persistence models or depend on Workbench responses.

## Product spaces

```text
WORLD           Evidence World / Data Plane
INTELLIGENCE    dossiers, graph and evidence
INVESTIGATIONS  durable cases and continuous interaction
AGENTS          Role / Task / Capability / Skill / Experience
OBSERVATORY     live operations + frozen proof

                START
```

`START` exposes the canonical DIRECT / RETRIEVE / VERIFY / INVESTIGATE / WATCH interaction modes.

## Current product state

The former Runtime Workbench UI and `/api/v1/workbench/*` transport have been retired. Runtime facts required by the competition are exposed through Product-safe read models used by WORLD, INTELLIGENCE, INVESTIGATIONS, AGENTS and OBSERVATORY.

## Truthfulness rule

Live visuals must be driven by runtime facts. Frozen benchmark results must be labeled as frozen proof. The frontend may add presentation aliases and cinematic motion, but it may not fabricate source health, Hot CVEs, Agent activity, Skill status, tool calls, token streaming, or monetary cost.
