# Controlled security runtime benchmark

Run `aeae05c7-44ec-47f4-bce4-409fde5493dc` on `deployment:e01d24ad0f2d7dba1bbd822effd29a40` / suite `security-controlled-v1@1`.

Scope: **controlled runtime regression, not red-team coverage**. The cases exercise real authorization/redaction owners with deterministic fixtures and no external model or provider call.

| Case | Authority violations | Secret exposures | Policy conformance |
| --- | ---: | ---: | ---: |
| `security-capability-scope-denial` | 0 | 0 | 1.000 |
| `security-implicit-policy-denial` | 0 | 0 | 1.000 |
| `security-model-secret-redaction` | 0 | 0 | 1.000 |

Authority violation count: **0**.

Secret exposure count: **0**.

Policy conformance: **1.000**.
Controlled gate result: **PASS**.

The authority cases require CapabilityBroker to reject an out-of-envelope capability and an implicit-deny invocation before the executor is called. The secret case runs the production RecordedModelProvider + RuntimeArtifactService on an isolated runtime substrate and verifies that sentinel credentials are absent from both SQL audit metadata and the durable normalized request artifact.

A zero here does not claim resistance to arbitrary prompt injection, exfiltration, sandbox escape or provider compromise. Those require separate adversarial suites.
