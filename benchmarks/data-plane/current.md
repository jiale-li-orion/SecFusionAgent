# Data-plane runtime metrics

Snapshot `2026-10-08T19:18:08.614492+00:00`. Public continuous-monitoring epoch: `2026-10-02T04:19:42+08:00`; earlier rows are bootstrap/corpus-prefill and are excluded from public runtime throughput.

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
| healthy | 36 |
| degraded | 1 |
| blocked | 2 |
| warming | 0 |
| healthy rate | 92.3% |
| overdue | 0 |
| backfill pending | 1 |

Health is current-state operational evidence: latest scheduled run + durable SourceState/backoff/overdue state. It is not a competition benchmark score.

## Rolling scheduled-monitoring throughput

| Window | Runs OK | Provider fail | Runtime fail | Fresh | Fresh src/cat | Queue p95 | Exec p95 | Fresh p95 → Knowledge | Writes/obs | Evidence | Top-1 share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1h | 85.7% | 14.3% | 0.0% | 25 | 5/3 | 1.70min | 1.80min | 3.01h | 2.93 | 45.45 MiB | 56.0% |
| 6h | 76.6% | 23.4% | 0.0% | 26 | 6/3 | 10.9s | 2.92min | 3.01h | 29.07 | 51.30 MiB | 53.8% |
| 24h | 78.6% | 21.4% | 0.0% | 204 | 7/3 | 15.4s | 1.26min | 1.47h | 18.97 | 137.06 MiB | 89.2% |
| 168h | 58.1% | 40.9% | 1.0% | 684 | 9/4 | 18.8s | 31.0s | 1.85h | 17.51 | 271.68 MiB | 87.1% |

Current conversion detail: 1.00 KnowledgeRevision/Observation; fresh Knowledge commit closure 100.0%; 2.93 canonical writes/Observation; 15.20 chunks/document revision. The same window contains 0 backfill Observations and 20 unclocked first-seen Observations, both kept separate from fresh-change latency. Terminal status mix: `{'fetch_failed': 5, 'no_change': 8, 'provider_blocked': 1, 'success': 28}`. Provider-boundary failures and runtime-owned failures are reported separately so external 403/quota/network conditions do not masquerade as scheduler/storage failures.

## Eight-category runtime view

Window `2026-10-07T19:18:08.614492+00:00` → `2026-10-08T19:18:08.614492+00:00`. Physical sources have exactly one measurement category, so category rows add back to physical totals without double counting.

| Category | Catalog | Exec | Scheduled | Fresh | Backfill | Writes | Chunks | Text | Evidence | Run OK | Provider fail | Runtime fail |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `vulnerability` | 8 | 8 | 2 | 0 | 0 | 0 | 0 | 0 B | 0 B | 77.9% | 22.1% | 0.0% |
| `development` | 17 | 2 | 1 | 182 | 0 | 2002 | 0 | 0 B | 1.13 MiB | 54.5% | 45.5% | 0.0% |
| `academic` | 11 | 5 | 1 | 0 | 0 | 38 | 1661 | 3.86 MiB | 71.62 MiB | 100.0% | 0.0% | 0.0% |
| `vendor` | 9 | 12 | 10 | 0 | 0 | 798 | 381 | 631.5 KiB | 37.52 MiB | 77.3% | 22.7% | 0.0% |
| `independent` | 12 | 12 | 10 | 19 | 0 | 4341 | 340 | 1022.3 KiB | 10.95 MiB | 91.2% | 8.8% | 0.0% |
| `normative` | 19 | 6 | 6 | 3 | 0 | 0 | 191 | 648.7 KiB | 1.76 MiB | 50.0% | 50.0% | 0.0% |
| `assets` | 4 | 5 | 0 | 0 | 0 | 0 | 0 | 0 B | 0 B | — | — | — |
| `incidents` | 21 | 16 | 9 | 0 | 0 | 48 | 90 | 115.6 KiB | 14.08 MiB | 81.4% | 18.6% | 0.0% |

## Source-level runtime drill-down

| Source | Category | Fresh | Backfill | Observations | Writes | Chunks | Evidence | Run OK | Provider fail | Runtime fail |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `github-target-repos` | `development` | 182 | 0 | 182 | 2002 | 0 | 1.13 MiB | 54.5% | 45.5% | 0.0% |
| `oss-security` | `independent` | 10 | 0 | 11 | 298 | 14 | 82.4 KiB | 100.0% | 0.0% | 0.0% |
| `hiddenlayer-reports` | `independent` | 7 | 0 | 12 | 0 | 14 | 2.43 MiB | 80.0% | 20.0% | 0.0% |
| `owasp-genai` | `independent` | 2 | 0 | 3 | 0 | 3 | 2.09 MiB | 50.0% | 50.0% | 0.0% |
| `eu-ai-act` | `normative` | 1 | 0 | 2 | 0 | 187 | 1.51 MiB | 50.0% | 50.0% | 0.0% |
| `nist-ai-rmf` | `normative` | 1 | 0 | 1 | 0 | 1 | 91.6 KiB | 50.0% | 50.0% | 0.0% |
| `nist-genai-profile` | `normative` | 1 | 0 | 1 | 0 | 1 | 81.6 KiB | 100.0% | 0.0% | 0.0% |
| `talos-research` | `independent` | 0 | 0 | 41 | 3355 | 192 | 4.79 MiB | 75.0% | 25.0% | 0.0% |
| `arxiv-ai-security` | `academic` | 0 | 0 | 39 | 38 | 1661 | 71.62 MiB | 100.0% | 0.0% | 0.0% |
| `trailofbits-research` | `independent` | 0 | 0 | 25 | 670 | 115 | 1.32 MiB | 100.0% | 0.0% | 0.0% |
| `microsoft-security-ai` | `vendor` | 0 | 0 | 11 | 0 | 11 | 3.07 MiB | 80.0% | 20.0% | 0.0% |
| `anthropic-news` | `vendor` | 0 | 0 | 10 | 380 | 38 | 1.60 MiB | 100.0% | 0.0% | 0.0% |
| `chainalysis-research` | `incidents` | 0 | 0 | 10 | 43 | 10 | 2.76 MiB | 100.0% | 0.0% | 0.0% |
| `aws-security-bulletins` | `vendor` | 0 | 0 | 9 | 342 | 10 | 2.60 MiB | 75.0% | 25.0% | 0.0% |
| `openai-deployment-safety` | `vendor` | 0 | 0 | 8 | 73 | 8 | 4.57 MiB | 100.0% | 0.0% | 0.0% |
| `bytedance-seed-research` | `vendor` | 0 | 0 | 5 | 0 | 21 | 623.5 KiB | 80.0% | 20.0% | 0.0% |
| `certik-security-dashboard` | `incidents` | 0 | 0 | 4 | 4 | 4 | 943.9 KiB | 100.0% | 0.0% | 0.0% |
| `anthropic-system-cards` | `vendor` | 0 | 0 | 2 | 2 | 292 | 24.90 MiB | 60.0% | 40.0% | 0.0% |
| `china-ai-standards` | `normative` | 0 | 0 | 2 | 0 | 2 | 82.2 KiB | 50.0% | 50.0% | 0.0% |
| `unit42-research` | `independent` | 0 | 0 | 1 | 18 | 2 | 241.6 KiB | 100.0% | 0.0% | 0.0% |
| `meta-ai-safety` | `vendor` | 0 | 0 | 1 | 1 | 1 | 198.9 KiB | 20.0% | 80.0% | 0.0% |
| `slowmist-reports` | `incidents` | 0 | 0 | 1 | 1 | 76 | 10.40 MiB | 50.0% | 50.0% | 0.0% |
| `anthropic-research` | `vendor` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `bleepingcomputer-news` | `incidents` | 0 | 0 | 0 | 0 | 0 | 0 B | 80.0% | 20.0% | 0.0% |
| `blockbeats-newsflash` | `incidents` | 0 | 0 | 0 | 0 | 0 | 0 B | 95.9% | 4.1% | 0.0% |
| `cac-ai-regulations` | `normative` | 0 | 0 | 0 | 0 | 0 | 0 B | 50.0% | 50.0% | 0.0% |
| `certcc-vulnerability-notes` | `independent` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `certik-incident-analysis` | `incidents` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `cve-program-cvelist-v5` | `vulnerability` | 0 | 0 | 0 | 0 | 0 | 0 B | 53.1% | 46.9% | 0.0% |
| `cyvers-reports` | `incidents` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `deepmind-safety` | `vendor` | 0 | 0 | 0 | 0 | 0 | 0 B | 75.0% | 25.0% | 0.0% |
| `foresight-timeline` | `incidents` | 0 | 0 | 0 | 0 | 0 | 0 B | 0.0% | 100.0% | 0.0% |
| `hiddenlayer-security-advisories` | `independent` | 0 | 0 | 0 | 0 | 0 | 0 B | 75.0% | 25.0% | 0.0% |
| `iso-ai-standards` | `normative` | 0 | 0 | 0 | 0 | 0 | 0 B | 0.0% | 100.0% | 0.0% |
| `mitre-atlas` | `independent` | 0 | 0 | 0 | 0 | 0 | 0 B | 50.0% | 50.0% | 0.0% |
| `nvd-cves-2` | `vulnerability` | 0 | 0 | 0 | 0 | 0 | 0 B | 90.6% | 9.4% | 0.0% |
| `nvidia-ai-security` | `vendor` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |
| `slowmist-hacked` | `incidents` | 0 | 0 | 0 | 0 | 0 | 0 B | 91.7% | 8.3% | 0.0% |
| `wiz-research` | `independent` | 0 | 0 | 0 | 0 | 0 | 0 B | 100.0% | 0.0% | 0.0% |

## Evidence/storage integrity

| Public runtime scope | Referenced artifacts | Present objects | Integrity |
| --- | ---: | ---: | ---: |
| Since monitoring epoch | 1360 | 1360 | 100.0% |

Current `filesystem` evidence store: 1408 physical objects / 423.57 MiB. PostgreSQL database size: 157.06 MiB. Pre-epoch bootstrap artifact history is retained as an internal diagnostic and is outside public runtime claims.

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
