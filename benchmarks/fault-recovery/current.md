<!-- GENERATED from fault-recovery benchmark JSON; DO NOT EDIT BY HAND. -->
# Engineering fault/recovery benchmark

- Benchmark run: `ec8557e7-50f8-442c-be4b-92a680bbd2d2`
- Deployment: `deployment:a811b6b5d5316d9d23d28d2ff132a73f`
- Suite: `engineering-fault-recovery@5`
- Fault-recovery success: 100.0%

| Case | Success | Mechanism | Diagnostics |
| --- | --- | --- | --- |
| `engineering-stale-acquisition-requeue` | `true` | stale acquisition run -> queued + collection.requested outbox | `control_outbox_count=0`; `control_run_status=running`; `outbox_count=1`; `recovered_count=1`; `run_status=queued` |
| `engineering-outbox-fail-once-retry` | `true` | publisher failure -> pending retry -> delivered | `first_delivered=0`; `first_pending=True`; `second_delivered=1`; `second_delivered_state=True` |
| `engineering-legacy-artifact-replay-recovery` | `true` | legacy s3:// Evidence URI + missing blob -> filesystem exact replay recovery | `content_hash_exact=True`; `legacy_uri_immutable=True`; `legacy_uri_readable=True`; `missing_before_replay=True` |

The probes execute against the real database state-transition code but scope every injected row by an explicit run/event ID and roll the injected operational rows back through a savepoint. Only TD3 benchmark rows persist.
