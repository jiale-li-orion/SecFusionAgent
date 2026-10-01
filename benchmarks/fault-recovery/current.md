<!-- GENERATED from fault-recovery benchmark JSON; DO NOT EDIT BY HAND. -->
# Engineering fault/recovery benchmark

- Benchmark run: `e8cb92f6-42fd-4492-8284-863e9afca0b8`
- Deployment: `deployment:f518d9f8fd7a776996354d34afa7f299`
- Suite: `engineering-fault-recovery@2`
- Fault-recovery success: 100.0%

| Case | Success | Mechanism | Diagnostics |
| --- | --- | --- | --- |
| `engineering-stale-acquisition-requeue` | `true` | stale acquisition run -> queued + collection.requested outbox | `outbox_count=1`; `recovered_count=1`; `run_status=queued` |
| `engineering-outbox-fail-once-retry` | `true` | publisher failure -> pending retry -> delivered | `first_delivered=0`; `first_pending=True`; `second_delivered=1`; `second_delivered_state=True` |

The probes execute against the real database state-transition code but scope every injected row by an explicit run/event ID and roll the injected operational rows back through a savepoint. Only TD3 benchmark rows persist.
