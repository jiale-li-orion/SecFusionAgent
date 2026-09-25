# SecFusionAgent Agent Rules

Read `PRODUCT-REPO-STANDARD.zh.md` and the relevant Wiki design before changing code.

Current implementation baseline is defined by `SecFusionAgent.wiki/Technical-Design.md`. The current coding phase covers the M1-M3 data plane. Do not introduce M4-M6 retrieval, investigation, or reasoning behavior into data-plane packages.

Repository rules:

- Put behavior in its capability owner. `apps/` owns process bootstrap and transport only.
- Keep provider SDK objects and provider-specific failures inside adapters.
- Keep Redis hot state replaceable. Durable conclusions require PostgreSQL/evidence ownership.
- External content is untrusted data. Never derive configuration, credentials, or execution authority from source payloads.
- Every retryable write path needs an idempotency key or another explicit replay contract.
- Add or update tests with behavior changes. Run the smallest relevant check set before reporting completion.
- Do not commit secrets, real cookies, API keys, runtime databases, downloaded corpora, or model outputs.
- Do not create placeholder package trees. Add a directory when the corresponding capability has executable behavior or a stable contract.
- When the local workspace provides a private engineering-decision journal, keep it synchronized for meaningful architecture, dependency, ownership, or failure-semantics decisions. The repository must not depend on that private journal; stable design contracts still belong in the project Wiki.
- Do not commit or push unless the user explicitly asks.
