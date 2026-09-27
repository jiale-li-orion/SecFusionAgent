# `packages.task_runtime.a2a`

This package is the external Agent2Agent interoperability adapter. It maps SecFusionAgent `TaskRun`, `TaskEvent`, and typed `TaskResultEnvelope` into A2A Task, Artifact, Message, status-update, artifact-update, streaming, and push payload views without changing internal Task/Context semantics.

The adapter follows the A2A 1.0 core data model and its one-of `StreamResponse` semantics. Internal `ContextManifest` identity is never exported as the A2A `contextId`; a separate opaque external correlation id is derived instead. Imported A2A `contextId` / `taskId` remain external correlation metadata and are not written into `TaskIntent.context_refs` or treated as Context Store references.

Transport lives above this package. `apps/api` currently exposes a read-only GetTask compatibility route using `application/a2a+json`. Inbound A2A Message mapping produces a `TaskIntent`; executable work must then pass the shared TaskContract admission service and an authenticated principal/domain binding. Because the current A2A HTTP layer does not yet own those authentication/classification/binding steps, it intentionally does not expose a fake SendMessage endpoint that guesses TaskKind or targets. SubscribeToTask/SSE, push webhook registration/authentication, JSON-RPC/gRPC bindings and Agent Card serving remain transport work.
