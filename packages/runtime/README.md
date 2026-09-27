# `packages.runtime`

`packages.runtime` owns shared execution-control enforcement below Task/Role logic. Technical Design 2 fixes Capability/Policy/Budget/Identity/Network/Sandbox boundaries; this package implements those runtime contracts without owning domain investigation or evidence semantics.

## Capability

`capability/` defines provider-neutral ToolImplementation, CapabilityContract, CapabilityBinding, CapabilityCard/SchemaView, requests, invocation plans/results and EphemeralObservation. Capability visibility is distinct from invocation authorization: a tool can be discoverable for planning while a concrete resource/action invocation is denied later.

`CapabilityRegistry` resolves healthy bindings and detects native schema drift. `CapabilityBroker` revalidates TaskContract/ExecutionEnvelope ceilings, invokes the Policy engine, reserves/commits budget, maps canonical arguments to the selected implementation, bounds timeout by the absolute execution deadline and persists `capability_invocations`. Tool output becomes an EphemeralObservation; it does not enter Evidence/Knowledge automatically. Provider SDK schemas stay behind binding/executor adapters.

## Budget and execution

`budget/` owns durable account/reservation state with parent-child ceiling propagation and idempotent reserve/commit/release. `execution/` owns durable ExecutionEnvelope lifecycle and bounded-loop stop semantics. Runtime migration `0017` persists budget/capability audit; `0019` persists execution and sandbox audit state.

`artifacts/` owns execution-produced runtime blobs and metadata. Runtime artifacts remain distinct from Evidence: a tool/sandbox output can be replayable and inspectable without acquiring factual authority. Promotion into Evidence is an explicit higher-level operation.

## Policy

`policy/` defines typed PolicyRequest/PolicyDecision and obligation handling. Authorization is separate from obligations. The v1 combining baseline is implicit deny with explicit deny precedence; indeterminate evaluation remains a fail-closed signal rather than silently becoming permit.

Prompt/Role text cannot bypass PolicyDecision. Side-effect commit, credential issuance, network egress, sandbox selection and child execution remain explicit decision points.

`WATCH_RESUME` is enforced before a relevant world change can create a fresh WATCH TaskRun. The production runtime policy catalog is loaded from `config/runtime-policy.json`; policy revision must match the TaskContract revision, implicit deny remains the default for unmatched decision points, and unmet obligations prevent TaskRun creation. Capability visibility/invocation policies still require a production Capability catalog before active external observation can be enabled in the worker-side Investigation composition.

## Sandbox

`sandbox/` owns sandbox profile contracts and selection. Process-restricted/container/microVM profiles express isolation, filesystem, network, credential and teardown requirements. High-risk `microvm_untrusted` requires Firecracker plus hardware virtualization and uses fail-closed fallback; it cannot silently downgrade to an ordinary container.

`SandboxBroker` enforces profile selection, PolicyDecision, network/credential grants, ExecutionEnvelope deadlines, ArtifactRef-only ingress/egress, operation replay and teardown while persisting sandbox instance/execution audit. Backend implementations remain behind the `SandboxBackend` protocol.

Current host probe finds Docker and `/dev/kvm`; OpenShell and Firecracker binaries are not installed. Process/container profiles therefore remain unavailable through production substrate detection until an OpenShell backend is installed/configured. `microvm_untrusted` remains fail-closed unless Firecracker plus KVM are available; it is never downgraded to an OCI container.

## Current boundary

Capability/Policy/Budget/Execution/Sandbox control-plane contracts and durable audit state exist. WATCH wake now creates a fresh BudgetAccount and ExecutionEnvelope in the same transaction as the TaskRun, inheriting the prior episode's capability/identity/network/sandbox ceilings while refreshing deadline and trace provenance. TD2's planned `runtime/identity/`, `runtime/network/`, and independent `runtime/audit/` owners have not yet been split out: identity/network constraints currently travel through ExecutionEnvelope, Policy and Sandbox contracts, while audit records live beside the owning runtime services. Do not create empty packages merely to match the design map; split these owners when a concrete credential/network/audit lifecycle requires independent state or enforcement.

## Dependency boundary

Allowed dependencies: `shared`, `task_runtime`, `runtime`. Execution-control code does not import enrichment/investigation domain facts. Domain Roles request capabilities/policy decisions through public runtime contracts.

## Verification

```bash
uv run pytest tests/test_task_capability_policy_conformance.py -q
uv run pytest packages/runtime -q
SECFUSION_RUN_INTEGRATION=1 uv run pytest tests/integration/test_runtime_control_plane.py -q
```
