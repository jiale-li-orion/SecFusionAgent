# Controlled Security Benchmark

This directory owns deterministic runtime-security regression evidence for TD3 hard-gate metrics.
It does **not** claim red-team or adversarial-model coverage.

`scripts/run_security_benchmark.py` currently freezes three controlled cases:

- execution-envelope scope denial: a capability outside `ExecutionEnvelope.capability_scope` must be
  rejected by `CapabilityBroker` before the executor is called;
- implicit policy deny: a valid in-scope capability invocation with no permitting policy must fail
  closed before the executor is called;
- model payload redaction: `RecordedModelProvider` is given sentinel values under
  secret/credential-shaped keys and must persist neither the sentinel in `ModelRequest.metadata_json`
  nor in the normalized request RuntimeArtifact.

The first two cases run the production CapabilityBroker/Policy contracts on an isolated SQL runtime
with a never-call executor. The redaction case runs production RecordedModelProvider and
RuntimeArtifactService on isolated SQLite + in-memory artifact bytes. The main PostgreSQL benchmark
substrate persists only the frozen case/suite/run/metric verdicts; isolated artifact IDs are not
pretended to be production-resolvable refs.

The suite records:

- `security.authority_violation_count` — executor calls that occurred despite a required deny;
- `security.secret_exposure_count` — sentinel exposure across the SQL audit metadata and durable
  request-artifact surfaces under test;
- `security.policy_conformance` — expected controlled enforcement/redaction outcomes satisfied.

The checked-in `current.json` / `current.md` are reviewed pointers for this controlled suite. Zero
violations here means these named runtime gates behaved correctly for the frozen cases. Broader
prompt/content poisoning, tool/inter-agent/memory trust, sandbox/network and capability-escalation
coverage belongs to the separate adversarial denominator below rather than being inferred from
these three hard-gate cases.

`adversarial-current.json` / `adversarial-current.md` own the separate TD3 v1 adversarial-class
coverage denominator. The profile freezes eleven classes from TD3 section 22. A class contributes to
`security.adversarial_class_coverage` only when a production-boundary probe exists; an uncovered
class remains `NOT_EVALUATED` rather than being counted as failure or success. Revision 4 currently
has 11/11 class coverage and 11/11 passing boundary probes across indirect prompt injection,
malicious documents/tool output, peer-Agent and Experience poisoning, MCP schema drift, capability/
network/filesystem/credential/side-effect escalation. These are deterministic production-boundary
regressions; stronger attack variants require a new suite revision and are not implied by the 1.0
result.
