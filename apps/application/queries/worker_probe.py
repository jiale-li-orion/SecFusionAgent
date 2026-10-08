"""Bounded Celery control observations; no durable heartbeat or offline inference."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from time import monotonic
from typing import Any, Literal

from apps.application.views.system import (
    SystemWorkerProbeView,
    SystemWorkerQueueView,
    SystemWorkerView,
)
from apps.worker.celery_app import celery_app

REQUIRED_QUEUES = ("collection", "enrichment", "investigation", "indexing")
CONTROL_REPLY_TIMEOUT_SECONDS = 1.0
PROBE_TIMEOUT_SECONDS = 4.0
CACHE_TTL_SECONDS = 15.0
MAX_MEASUREMENT_AGE_SECONDS = 60.0


def _control_snapshot(
    pongs: dict[str, Any],
    queues: dict[str, Any],
    checked_at: datetime,
) -> SystemWorkerProbeView:
    workers: list[SystemWorkerView] = []
    for name in sorted(set(pongs) | set(queues)):
        ping_responded = isinstance(pongs.get(name), dict) and pongs[name].get("ok") == "pong"
        queue_response_received = isinstance(queues.get(name), list)
        names = (
            sorted(
                {
                    item["name"]
                    for item in queues.get(name, [])
                    if isinstance(item, dict) and isinstance(item.get("name"), str)
                }
            )
            if queue_response_received
            else []
        )
        failure_code = (
            None
            if ping_responded and queue_response_received
            else "ping_not_observed"
            if not ping_responded
            else "active_queues_not_observed"
        )
        workers.append(
            SystemWorkerView(
                name=name,
                availability="responding" if failure_code is None else "partial_response",
                ping_responded=ping_responded,
                queue_response_received=queue_response_received,
                queue_names=names,
                checked_at=checked_at,
                failure_code=failure_code,
            )
        )
    any_queue_response = any(worker.queue_response_received for worker in workers)
    queue_views: list[SystemWorkerQueueView] = []
    for queue in REQUIRED_QUEUES:
        consumers = [worker.name for worker in workers if queue in worker.queue_names]
        queue_views.append(
            SystemWorkerQueueView(
                queue_name=queue,
                availability=(
                    "available" if consumers else "unobserved" if any_queue_response else "unknown"
                ),
                consumer_names=consumers,
                checked_at=checked_at,
                failure_code=(
                    None
                    if consumers
                    else "no_consumer_response"
                    if any_queue_response
                    else "active_queues_not_observed"
                ),
            )
        )
    status: Literal["healthy", "degraded", "unavailable"]
    failure: str | None
    if not workers:
        status, failure = "unavailable", "no_control_response"
    elif not all(queue.consumer_names for queue in queue_views):
        status, failure = "degraded", "required_queue_consumer_unobserved"
    elif any(worker.availability == "partial_response" for worker in workers):
        status, failure = "degraded", "partial_control_response"
    else:
        status, failure = "healthy", None
    return SystemWorkerProbeView(
        status=status,
        checked_at=checked_at,
        completed_at=datetime.now(UTC),
        failure_code=failure,
        workers=workers,
        queues=queue_views,
    )


def probe_celery_workers() -> SystemWorkerProbeView:
    checked_at = datetime.now(UTC)
    # Reuse the application's broker and control configuration. The explicit
    # connection limits transport work without mutating Celery's worker settings.
    with celery_app.connection_for_read(
        connect_timeout=CONTROL_REPLY_TIMEOUT_SECONDS,
        transport_options={
            **celery_app.conf.broker_transport_options,
            "socket_connect_timeout": CONTROL_REPLY_TIMEOUT_SECONDS,
            "socket_timeout": CONTROL_REPLY_TIMEOUT_SECONDS,
            "max_retries": 0,
        },
    ) as connection:
        connection.ensure_connection(max_retries=0, timeout=CONTROL_REPLY_TIMEOUT_SECONDS)
        inspect = celery_app.control.inspect(
            connection=connection,
            timeout=CONTROL_REPLY_TIMEOUT_SECONDS,
        )
        queues = inspect.active_queues() or {}
        # A broadcast waits an idle timeout after its last reply. Once queue
        # responders are known, Celery can stop the directed ping collector as
        # soon as those real destinations reply; no worker inventory is inferred.
        ping_inspect = celery_app.control.inspect(
            connection=connection,
            timeout=CONTROL_REPLY_TIMEOUT_SECONDS,
            destination=sorted(queues) or None,
        )
        return _control_snapshot(ping_inspect.ping() or {}, queues, checked_at)


def _failed_probe(code: str, checked_at: datetime) -> SystemWorkerProbeView:
    snapshot = _control_snapshot({}, {}, checked_at)
    return snapshot.model_copy(update={"failure_code": code})


class CeleryWorkerProbe:
    """One shared refresh, short cache, and a hard measurement-age boundary."""

    def __init__(self, probe: Callable[[], SystemWorkerProbeView] = probe_celery_workers) -> None:
        self._probe = probe
        self._cache: tuple[float, SystemWorkerProbeView] | None = None
        self._refresh_task: asyncio.Task[SystemWorkerProbeView] | None = None

    def _age(self, cached_at: float, snapshot: SystemWorkerProbeView) -> float:
        return max(
            monotonic() - cached_at, (datetime.now(UTC) - snapshot.checked_at).total_seconds()
        )

    def _refresh(self) -> asyncio.Task[SystemWorkerProbeView]:
        if self._refresh_task is None or self._refresh_task.done():
            self._refresh_task = asyncio.create_task(self._measure())
        return self._refresh_task

    async def read(self) -> SystemWorkerProbeView:
        if self._cache is not None:
            cached_at, snapshot = self._cache
            age = self._age(cached_at, snapshot)
            if age < CACHE_TTL_SECONDS:
                return snapshot
            if age < MAX_MEASUREMENT_AGE_SECONDS:
                self._refresh()
                return snapshot
        measured = await asyncio.shield(self._refresh())
        if (datetime.now(UTC) - measured.checked_at).total_seconds() >= MAX_MEASUREMENT_AGE_SECONDS:
            return _failed_probe("measurement_too_old", datetime.now(UTC))
        return measured

    async def _measure(self) -> SystemWorkerProbeView:
        checked_at = datetime.now(UTC)
        try:
            snapshot = await asyncio.wait_for(asyncio.to_thread(self._probe), PROBE_TIMEOUT_SECONDS)
        except TimeoutError:
            snapshot = _failed_probe("control_probe_timeout", checked_at)
        except Exception:
            # Provider exception text can contain the broker URL or credentials.
            snapshot = _failed_probe("control_probe_failed", checked_at)
        self._cache = (monotonic(), snapshot)
        return snapshot


worker_probe = CeleryWorkerProbe()
