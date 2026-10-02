# Data-plane runtime metrics

Snapshot `2026-10-02T11:11:39.568989+00:00`. Public continuous-monitoring epoch: `2026-10-02T04:19:42+08:00`; earlier rows are bootstrap/corpus-prefill and are excluded from public runtime throughput.

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
| healthy | 29 |
| degraded | 8 |
| blocked | 2 |
| warming | 0 |
| healthy rate | 74.4% |
| overdue | 0 |
| backfill pending | 0 |

Health is current-state operational evidence: latest scheduled run + durable SourceState/backoff/overdue state. It is not a competition benchmark score.

## Rolling scheduled-monitoring throughput

| Window | Runs OK | Provider fail | Runtime fail | Fresh | Fresh src/cat | Queue p95 | Exec p95 | Fresh p95 → Knowledge | Writes/obs | Evidence | Top-1 share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1h | 82.4% | 8.8% | 8.8% | 19 | 1/1 | 10.9s | 9.4s | 5.22h | 7.24 | 3.22 MiB | 100.0% |
| 6h | 75.0% | 20.0% | 5.0% | 19 | 1/1 | 7.4s | 22.8s | 5.22h | 7.24 | 3.22 MiB | 100.0% |
| 24h | 73.2% | 19.2% | 7.5% | 19 | 1/1 | 7.4s | 19.9s | 5.22h | 7.06 | 3.22 MiB | 100.0% |
| 168h | 73.2% | 19.2% | 7.5% | 19 | 1/1 | 7.4s | 19.9s | 5.22h | 7.06 | 3.22 MiB | 100.0% |

Current conversion detail: 1.00 KnowledgeRevision/Observation; fresh Knowledge commit closure 100.0%; 7.24 canonical writes/Observation; 0.92 chunks/document revision. The same window contains 0 backfill Observations and 3 unclocked first-seen Observations, both kept separate from fresh-change latency. Terminal status mix: `{'fetch_failed': 3, 'internal_error': 3, 'no_change': 19, 'success': 9}`. Provider-boundary failures and runtime-owned failures are reported separately so external 403/quota/network conditions do not masquerade as scheduler/storage failures.

## Eight-category runtime view

Window `2026-10-01T20:19:42+00:00` → `2026-10-02T11:11:39.568989+00:00`. Physical sources have exactly one measurement category, so category rows add back to physical totals without double counting.

| Category | Catalog | Exec | Scheduled | Fresh | Backfill | Writes | Chunks | Text | Evidence | Run OK | Provider fail | Runtime fail |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `vulnerability` | 8 | 8 | 2 | 0 | 0 | 0 | 0 | 0 B | 0 B | 77.0% | 23.0% | 0.0% |
| `development` | 17 | 2 | 1 | 19 | 0 | 242 | 0 | 0 B | 139.1 KiB | 12.5% | 56.2% | 31.2% |
| `academic` | 11 | 5 | 1 | 0 | 0 | 0 | 0 | 0 B | 0 B | 100.0% | 0.0% | 0.0% |
| `vendor` | 9 | 12 | 10 | 0 | 0 | 3 | 9 | 12.3 KiB | 2.58 MiB | 64.5% | 19.4% | 16.1% |
| `independent` | 12 | 12 | 10 | 0 | 0 | 1 | 1 | 20 B | 20 B | 91.9% | 0.0% | 8.1% |
| `normative` | 19 | 6 | 6 | 0 | 0 | 0 | 0 | 0 B | 0 B | 0.0% | 100.0% | 0.0% |
| `assets` | 4 | 5 | 0 | 0 | 0 | 0 | 0 | 0 B | 0 B | — | — | — |
| `incidents` | 21 | 16 | 9 | 0 | 0 | 1 | 2 | 118 B | 524.1 KiB | 76.2% | 17.1% | 6.7% |

## Source-level runtime drill-down

| Source | Category | Fresh | Backfill | Observations | Writes | Chunks | Evidence | Run OK | Provider fail | Runtime fail |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `github-target-repos` | `development` | 19 | 0 | 22 | 242 | 0 | 139.1 KiB | 12.5% | 56.2% | 31.2% |
| `aws-security-bulletins` | `vendor` | 0 | 0 | 9 | 3 | 9 | 2.58 MiB | 33.3% | 0.0% | 66.7% |
| `chainalysis-research` | `incidents` | 0 | 0 | 1 | 1 | 1 | 278.3 KiB | 0.0% | 0.0% | 100.0% |
| `mitre-atlas` | `independent` | 0 | 0 | 1 | 1 | 1 | 20 B | 100.0% | 0.0% | 0.0% |
| `certik-security-dashboard` | `incidents` | 0 | 0 | 1 | 0 | 1 | 234.7 KiB | 33.3% | 0.0% | 66.7% |
| `cyvers-reports` | `incidents` | 0 | 0 | 1 | 0 | 0 | 11.1 KiB | 33.3% | 0.0% | 66.7% |
| `anthropic-news` | `vendor` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `anthropic-research` | `vendor` | 0 | 0 | 0 | 0 | 0 | 0 B | 0.0% | 0.0% | 100.0% |
| `anthropic-system-cards` | `vendor` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `arxiv-ai-security` | `academic` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `bleepingcomputer-news` | `incidents` | 0 | 0 | 0 | 0 | 0 | 0 B | 0.0% | 100.0% | 0.0% |
| `blockbeats-newsflash` | `incidents` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `bytedance-seed-research` | `vendor` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `certcc-vulnerability-notes` | `independent` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `certik-incident-analysis` | `incidents` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `cve-program-cvelist-v5` | `vulnerability` | 0 | 0 | 0 | 0 | 0 | 0 B | 0.0% | 100.0% | 0.0% |
| `deepmind-safety` | `vendor` | 0 | 0 | 0 | 0 | 0 | 0 B | 33.3% | 66.7% | 0.0% |
| `foresight-timeline` | `incidents` | 0 | 0 | 0 | 0 | 0 | 0 B | 0.0% | 100.0% | 0.0% |
| `hiddenlayer-reports` | `independent` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `hiddenlayer-security-advisories` | `independent` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `iso-ai-standards` | `normative` | 0 | 0 | 0 | 0 | 0 | 0 B | 0.0% | 100.0% | 0.0% |
| `meta-ai-safety` | `vendor` | 0 | 0 | 0 | 0 | 0 | 0 B | 0.0% | 100.0% | 0.0% |
| `microsoft-security-ai` | `vendor` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `nvd-cves-2` | `vulnerability` | 0 | 0 | 0 | 0 | 0 | 0 B | 95.0% | 5.0% | 0.0% |
| `nvidia-ai-security` | `vendor` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `openai-deployment-safety` | `vendor` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `oss-security` | `independent` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `slowmist-hacked` | `incidents` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `slowmist-reports` | `incidents` | 0 | 0 | 0 | 0 | 0 | 0 B | 0.0% | 100.0% | 0.0% |
| `talos-research` | `independent` | 0 | 0 | 0 | 0 | 0 | 0 B | 0.0% | 0.0% | 100.0% |
| `trailofbits-research` | `independent` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `unit42-research` | `independent` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `wiz-research` | `independent` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |

## Evidence/storage integrity

| Public runtime scope | Referenced artifacts | Present objects | Integrity |
| --- | ---: | ---: | ---: |
| Since monitoring epoch | 35 | 35 | 100.0% |

Current `filesystem` evidence store: 38 physical objects / 3.77 MiB. PostgreSQL database size: 64.52 MiB. Pre-epoch bootstrap artifact history is retained as an internal diagnostic and is outside public runtime claims.

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
