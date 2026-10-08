from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from threading import Event
from time import monotonic

import pytest

from apps.application.queries.worker_probe import CeleryWorkerProbe, _control_snapshot


def test_worker_probe_pings_only_current_queue_responders(monkeypatch) -> None:
    from types import SimpleNamespace

    import apps.application.queries.worker_probe as module

    calls: list[str | tuple[str, list[str]]] = []
    queues = {
        "collection-worker": [{"name": "collection"}],
        "processing-worker": [
            {"name": name} for name in ("enrichment", "investigation", "indexing")
        ],
    }

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def ensure_connection(self, **kwargs):
            assert kwargs["max_retries"] == 0

    class Inspector:
        def __init__(self, destination):
            self.destination = destination

        def active_queues(self):
            calls.append("active_queues")
            return queues

        def ping(self):
            calls.append(("ping", self.destination))
            return {name: {"ok": "pong"} for name in queues}

    app = SimpleNamespace(
        conf=SimpleNamespace(broker_transport_options={}),
        connection_for_read=lambda **kwargs: Connection(),
        control=SimpleNamespace(inspect=lambda **kwargs: Inspector(kwargs.get("destination"))),
    )
    monkeypatch.setattr(module, "celery_app", app)
    snapshot = module.probe_celery_workers()
    assert calls == ["active_queues", ("ping", sorted(queues))]
    assert snapshot.status == "healthy"
    assert all(queue.availability == "available" for queue in snapshot.queues)


def test_worker_control_response_scope_and_missing_queue_are_explicit() -> None:
    now = datetime.now(UTC)
    partial = _control_snapshot(
        {"collection-worker": {"ok": "pong"}, "busy-worker": {"ok": "pong"}},
        {"collection-worker": [{"name": "collection"}]},
        now,
    )
    assert partial.status == "degraded"
    assert partial.workers[0].availability == "partial_response"
    assert partial.workers[0].failure_code == "active_queues_not_observed"
    queues = {queue.queue_name: queue for queue in partial.queues}
    assert queues["collection"].consumer_names == ["collection-worker"]
    assert queues["enrichment"].availability == "unobserved"
    assert queues["enrichment"].failure_code == "no_consumer_response"
    absent = _control_snapshot({}, {}, now)
    assert absent.status == "unavailable"
    assert absent.failure_code == "no_control_response"
    assert all(queue.availability == "unknown" for queue in absent.queues)
    assert absent.checked_at == now


@pytest.mark.asyncio
async def test_worker_probe_shares_offloaded_read_and_rejects_old_measurement() -> None:
    started, finish = Event(), Event()
    calls = 0

    def measure():
        nonlocal calls
        calls += 1
        started.set()
        assert finish.wait(timeout=1)
        return _control_snapshot({}, {}, datetime.now(UTC))

    probe = CeleryWorkerProbe(measure)
    first = asyncio.create_task(probe.read())
    try:
        assert await asyncio.to_thread(started.wait, 0.5)
        second = asyncio.create_task(probe.read())
        # The API loop can continue while the control read blocks in another thread.
        await asyncio.sleep(0)
        assert not first.done()
        assert not second.done()
        finish.set()
        result, concurrent = await asyncio.gather(first, second)
        assert result is concurrent
        assert calls == 1
        assert await probe.read() is result
        old = result.model_copy(update={"checked_at": datetime.now(UTC) - timedelta(minutes=2)})
        probe._cache = (monotonic(), old)
        assert (await probe.read()).checked_at > old.checked_at
        assert calls == 2
    finally:
        finish.set()
        await first


@pytest.mark.asyncio
async def test_worker_probe_timeout_and_failure_do_not_leak_broker_details(monkeypatch) -> None:
    import apps.application.queries.worker_probe as module

    started, finish = Event(), Event()

    def slow_measure():
        started.set()
        assert finish.wait(timeout=1)
        return _control_snapshot({}, {}, datetime.now(UTC))

    monkeypatch.setattr(module, "PROBE_TIMEOUT_SECONDS", 0.01)
    try:
        timeout = await CeleryWorkerProbe(slow_measure).read()
        assert timeout.status == "unavailable"
        assert timeout.failure_code == "control_probe_timeout"
    finally:
        finish.set()

    def broken_measure():
        raise RuntimeError("redis://username:secret-value@private-broker/0")

    broken = await CeleryWorkerProbe(broken_measure).read()
    assert broken.failure_code == "control_probe_failed"
    assert "secret-value" not in broken.model_dump_json()
    assert "private-broker" not in broken.model_dump_json()
