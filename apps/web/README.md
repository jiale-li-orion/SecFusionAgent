# `apps.web` — SecFusion Product App

`apps.web` is the user-facing SecFusionAgent product frontend.

The authoritative Product UI contract is [`SPEC.md`](SPEC.md). Product v1 exposes the complete Evidence Plane + Agent Runtime + Investigation/Decision + Operations/Evaluation story required by the competition and project Requirements.

## Boundary

The Product App is independent from:

- the project Wiki/Website, which explains the architecture and competition evidence;
- `/api/v1/workbench/*`, which remains an internal dev/test diagnostic API while it is useful to engineering;
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

## Current migration state

`index.html`, `app.js` and `styles.css` are the previous Runtime Workbench console and are **legacy implementation slated for replacement in Product P0**. Do not extend that UI or treat its `/api/v1/workbench/*` calls as Product contracts.

P0 replaces the legacy static console with the React/TypeScript Product App and closes the first Product read/event seams described in `SPEC.md`:

- Evidence read;
- live Data Plane/source overview;
- Hot Pool read;
- Product-safe Task/Role/RuntimeActivity projection;
- Investigation ProductEvent/SSE.

Until that replacement lands, the old console remains useful only as a local engineering aid.

## Truthfulness rule

Live visuals must be driven by runtime facts. Frozen benchmark results must be labeled as frozen proof. The frontend may add presentation aliases and cinematic motion, but it may not fabricate source health, Hot CVEs, Agent activity, Skill status, tool calls, token streaming, or monetary cost.
