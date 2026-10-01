# Data-plane runtime metrics

Snapshot `2026-10-01T21:00:32.746406+00:00`. Public continuous-monitoring epoch: `2026-10-02T04:19:42+08:00`; earlier rows are bootstrap/corpus-prefill and are excluded from public runtime throughput.

## Source portfolio contract

| Metric | Current |
| --- | ---: |
| Portfolio categories | 8 |
| Catalog entries | 101 |
| Executable sources | 66 |
| Scheduled monitors | 39 |
| Categories with scheduled monitoring | 7/8 |

`assets` is intentionally query-time/on-demand; it remains part of 8-category product coverage and outside scheduled-monitor throughput.

## Current source health

| State | Sources |
| --- | ---: |
| healthy | 32 |
| degraded | 5 |
| blocked | 2 |
| warming | 0 |
| healthy rate | 82.1% |
| overdue | 0 |
| backfill pending | 0 |

Health is current-state operational evidence: latest scheduled run + durable SourceState/backoff/overdue state. It is not a competition benchmark score.

## Rolling scheduled-monitoring throughput

| Window | Runs OK | Provider fail | Runtime fail | Fresh | Fresh src/cat | Queue p95 | Exec p95 | Fresh p95 → Knowledge | Writes/obs | Evidence | Top-1 share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1h | 56.2% | 43.8% | 0.0% | 0 | 0/0 | 12.5s | 30.1s | — | 1.00 | 20 B | — |
| 6h | 56.2% | 43.8% | 0.0% | 0 | 0/0 | 12.5s | 30.1s | — | 1.00 | 20 B | — |
| 24h | 56.2% | 43.8% | 0.0% | 0 | 0/0 | 12.5s | 30.1s | — | 1.00 | 20 B | — |
| 168h | 56.2% | 43.8% | 0.0% | 0 | 0/0 | 12.5s | 30.1s | — | 1.00 | 20 B | — |

Current conversion detail: 1.00 KnowledgeRevision/Observation; fresh Knowledge commit closure —; 1.00 canonical writes/Observation; 1.00 chunks/document revision. The same window contains 0 backfill Observations and 1 unclocked first-seen Observations, both kept separate from fresh-change latency. Terminal status mix: `{'fetch_failed': 4, 'no_change': 5, 'provider_blocked': 2, 'rate_limited': 1, 'success': 4}`. Provider-boundary failures and runtime-owned failures are reported separately so external 403/quota/network conditions do not masquerade as scheduler/storage failures.

## Eight-category runtime view

Window `2026-10-01T20:19:42+00:00` → `2026-10-01T21:00:32.746406+00:00`. Physical sources have exactly one measurement category, so category rows add back to physical totals without double counting.

| Category | Catalog | Exec | Scheduled | Fresh | Backfill | Writes | Chunks | Text | Evidence | Run OK | Provider fail | Runtime fail |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `vulnerability` | 8 | 8 | 2 | 0 | 0 | 0 | 0 | 0 B | 0 B | 75.0% | 25.0% | 0.0% |
| `development` | 17 | 2 | 1 | 0 | 0 | 0 | 0 | 0 B | 0 B | 0.0% | 100.0% | 0.0% |
| `academic` | 11 | 5 | 1 | 0 | 0 | 0 | 0 | 0 B | 0 B | — | — | — |
| `vendor` | 9 | 12 | 10 | 0 | 0 | 0 | 0 | 0 B | 0 B | 0.0% | 100.0% | 0.0% |
| `independent` | 12 | 12 | 10 | 0 | 0 | 1 | 1 | 20 B | 20 B | 100.0% | 0.0% | 0.0% |
| `normative` | 19 | 6 | 6 | 0 | 0 | 0 | 0 | 0 B | 0 B | 0.0% | 100.0% | 0.0% |
| `assets` | 4 | 5 | 0 | 0 | 0 | 0 | 0 | 0 B | 0 B | — | — | — |
| `incidents` | 21 | 16 | 9 | 0 | 0 | 0 | 0 | 0 B | 0 B | 57.1% | 42.9% | 0.0% |

## Source-level runtime drill-down

| Source | Category | Fresh | Backfill | Observations | Writes | Chunks | Evidence | Run OK | Provider fail | Runtime fail |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `mitre-atlas` | `independent` | 0 | 0 | 1 | 1 | 1 | 20 B | 100.0% | 0.0% | 0.0% |
| `bleepingcomputer-news` | `incidents` | 0 | 0 | 0 | 0 | 0 | 0 B | 0.0% | 100.0% | 0.0% |
| `blockbeats-newsflash` | `incidents` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `cve-program-cvelist-v5` | `vulnerability` | 0 | 0 | 0 | 0 | 0 | 0 B | 0.0% | 100.0% | 0.0% |
| `foresight-timeline` | `incidents` | 0 | 0 | 0 | 0 | 0 | 0 B | 0.0% | 100.0% | 0.0% |
| `github-target-repos` | `development` | 0 | 0 | 0 | 0 | 0 | 0 B | 0.0% | 100.0% | 0.0% |
| `iso-ai-standards` | `normative` | 0 | 0 | 0 | 0 | 0 | 0 B | 0.0% | 100.0% | 0.0% |
| `meta-ai-safety` | `vendor` | 0 | 0 | 0 | 0 | 0 | 0 B | 0.0% | 100.0% | 0.0% |
| `nvd-cves-2` | `vulnerability` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `oss-security` | `independent` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `slowmist-hacked` | `incidents` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `slowmist-reports` | `incidents` | 0 | 0 | 0 | 0 | 0 | 0 B | 0.0% | 100.0% | 0.0% |

## Evidence/storage integrity

| Public runtime scope | Referenced artifacts | Present objects | Integrity |
| --- | ---: | ---: | ---: |
| Since monitoring epoch | 1 | 1 | 100.0% |

Current `filesystem` evidence store: 1 physical objects / 20 B. PostgreSQL database size: 61.09 MiB. Pre-epoch bootstrap artifact history is retained as an internal diagnostic and is outside public runtime claims.

## Metric contract

- **Catalog entry**: one product-facing source commitment in `config/source-inventory.json`.
- **Executable source**: one concrete `SourceDefinition` with adapter/runtime ownership.
- **Scheduled monitor**: executable source with runtime `enabled=true` and `schedule_policy.enabled != false`.
- **Fresh external change**: scheduled Observation outside backfill whose `updated_at ?? published_at` is within the configured fresh horizon when observed.
- **Backfill**: Observation produced by a run whose input or output cursor has `backfill_pending=true`.
- **Run success rate**: `(success + no_change) / terminal scheduled runs`; provider failures remain in the denominator.
- **Provider-boundary failure rate**: `fetch_failed + rate_limited + auth_failed + schema_changed + provider_blocked` divided by terminal scheduled runs; it measures upstream access/transport/protocol availability.
- **Runtime-owned failure rate**: `dependency_unavailable + internal_error + generic failed` divided by terminal scheduled runs; it isolates SecFusionAgent-owned execution/dependency failures.
- **Queue delay**: AcquisitionRun creation → worker start; this isolates scheduler/worker backlog from provider latency.
- **Execution time**: worker start → terminal AcquisitionRun; this surfaces slow or blocking providers.
- **Change poll yield**: change-producing `success` runs divided by successful scheduled runs; this measures useful poll density, not correctness.
- **Write amplification**: canonical Object/Claim/Relation writes per Observation; it measures knowledge conversion, not model accuracy.
- **Fresh knowledge commit rate**: fresh scheduled changes that reached a KnowledgeRevision; this is the data-plane conversion closure ratio.
- **Top-1 traffic share**: largest source's share of fresh scheduled changes; lower concentration indicates broader live-source participation.
- **Evidence integrity**: distinct `EvidenceArtifact.storage_uri` values whose physical object exists in the active durable artifact store.

`hourly_series` and `category_hourly_series` in `current.json` are the chart-ready time series for live/fresh/backfill/write/chunk/run-health curves.
