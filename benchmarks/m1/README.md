# M1 Monitoring Benchmark

`scripts/run_m1_benchmark.py` owns the executable M1 denominator for source-category coverage, scheduled monitoring latency and source-delivery coverage.

## Monitoring latency

Latency is measured only for durable observations created by `trigger=scheduled` and committed into Knowledge:

```text
Observation.published_at -> earliest KnowledgeRevision.committed_at
```

On-demand queries, manual promotion and bootstrap-only probes do not enter this denominator. The fixed window is defined over Knowledge commit time. Samples with no reliable `published_at` remain visible in `evaluable_coverage` but are excluded from numeric p50/p95/max aggregation.

## Source delivery coverage

Delivery coverage requires an **independent expected-event manifest**. The runner never generates expected keys from SecFusionAgent's own Observation rows.

Manifest shape:

```json
{
  "manifest_id": "provider-window-20261001T1000Z",
  "provider_snapshot_ref": "provider-snapshot:<sha256>",
  "captured_at": "2026-10-01T11:00:00Z",
  "window_start": "2026-10-01T10:00:00Z",
  "window_end": "2026-10-01T11:00:00Z",
  "events": [
    {
      "source_id": "oss-security",
      "external_object_id": "2026/10/01/1",
      "external_revision": "<provider revision>"
    }
  ]
}
```

`provider_snapshot_ref` must use `provider-snapshot:` or `artifact:` and represent a baseline obtained independently of the accepted Observation set. `captured_at` must be at or after `window_end`, so the snapshot can contain the complete provider-side event set for that window. The manifest window must exactly equal the benchmark window.

`SourceDeliveryKey` identity is:

```text
source_id + external_object_id + (external_revision OR content_hash)
```

Accepted keys come only from `trigger=scheduled` Observations whose `observed_at` is inside the same fixed window. An Observation may match the expected key by provider revision or content hash. Unexpected accepted observations are reported separately and never increase the coverage numerator.

Without an independent expected-event manifest, `m1.source_delivery_coverage` remains `not_evaluated` by design.

## Commands

Latency/source taxonomy only:

```bash
uv run python scripts/run_m1_benchmark.py \
  --window-start 2026-10-01T10:00:00Z \
  --window-end 2026-10-01T11:00:00Z \
  --suite-revision 1
```

With frozen delivery gold:

```bash
uv run python scripts/run_m1_benchmark.py \
  --window-start 2026-10-01T10:00:00Z \
  --window-end 2026-10-01T11:00:00Z \
  --suite-revision 1 \
  --expected-events-manifest /path/to/provider-window.json
```

The runner persists the provider snapshot ref, expected-manifest digest, expected/matched/missed/unexpected counts and `m1.source_delivery_coverage` into TD3 BenchmarkCase/Suite/MetricObservation provenance.
