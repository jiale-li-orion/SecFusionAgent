from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from packages.intelligence.incident.contracts import (
    IncidentCandidate,
    IncidentSignalResult,
    IncidentSignalStore,
    SignalItem,
)

STRONG_ANCHORS = {
    "tx_hash",
    "address",
    "cve",
    "ghsa",
    "ioc",
    "domain",
    "ip",
    "incident_id",
    "advisory_id",
    "commit",
}


class IncidentCorrelator:
    def __init__(
        self,
        store: IncidentSignalStore,
        *,
        ttl_seconds: int = 7 * 24 * 60 * 60,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._ttl_seconds = ttl_seconds
        self._now = now or (lambda: datetime.now(UTC))

    async def accept(self, signal: SignalItem) -> IncidentSignalResult:
        existing_signal = await self._store.get_signal(signal.signal_id)
        if existing_signal is not None and existing_signal.incident_candidate_id is not None:
            candidate = await self._store.get_candidate(existing_signal.incident_candidate_id)
            if candidate is None:
                raise RuntimeError("signal references an expired incident candidate")
            return IncidentSignalResult(
                signal_id=signal.signal_id,
                incident_candidate_id=candidate.candidate_id,
                available_at=self._now(),
                material_change=False,
                source_role=signal.source_role,
                next_watch_at=candidate.next_poll_at,
            )

        candidate = await self._find_candidate(signal)
        created = candidate is None
        if candidate is None:
            candidate = IncidentCandidate(
                candidate_id=_candidate_id(signal),
                incident_type=signal.incident_type,
                last_material_change=signal.observed_at,
                unresolved_questions=list(signal.unresolved_questions),
            )

        before = candidate.model_copy(deep=True)
        candidate = _merge_signal(candidate, signal)
        now = self._now()
        candidate.next_poll_at = _next_poll_at(candidate, now)
        signal.incident_candidate_id = candidate.candidate_id
        await self._store.put_signal(signal, ttl_seconds=self._ttl_seconds)
        await self._store.put_candidate(candidate, ttl_seconds=self._ttl_seconds)
        for anchor_type, values in candidate.anchor_set.items():
            if anchor_type not in STRONG_ANCHORS:
                continue
            for value in values:
                await self._store.index_candidate_anchor(
                    candidate.candidate_id,
                    anchor_type,
                    value,
                    ttl_seconds=self._ttl_seconds,
                )
        if candidate.next_poll_at is not None:
            await self._store.schedule_watch(candidate.candidate_id, candidate.next_poll_at)
        return IncidentSignalResult(
            signal_id=signal.signal_id,
            incident_candidate_id=candidate.candidate_id,
            available_at=now,
            material_change=created or _materially_changed(before, candidate),
            source_role=signal.source_role,
            next_watch_at=candidate.next_poll_at,
        )

    async def _find_candidate(self, signal: SignalItem) -> IncidentCandidate | None:
        candidate_ids: set[str] = set()
        for anchor_type, values in signal.anchors.items():
            if anchor_type not in STRONG_ANCHORS:
                continue
            for value in values:
                candidate_ids.update(await self._store.candidate_ids_for_anchor(anchor_type, value))
        candidates = []
        for candidate_id in sorted(candidate_ids):
            candidate = await self._store.get_candidate(candidate_id)
            if candidate is not None and candidate.incident_type == signal.incident_type:
                candidates.append(candidate)
        if not candidates:
            return None
        candidates.sort(
            key=lambda item: (
                _strong_overlap_count(item, signal),
                item.independent_source_count,
                item.last_material_change,
            ),
            reverse=True,
        )
        return candidates[0]


def _merge_signal(candidate: IncidentCandidate, signal: SignalItem) -> IncidentCandidate:
    for anchor_type, values in signal.anchors.items():
        current = set(candidate.anchor_set.get(anchor_type, []))
        current.update(values)
        candidate.anchor_set[anchor_type] = sorted(current)
    if signal.signal_id not in candidate.signal_ids:
        candidate.signal_ids.append(signal.signal_id)
    diversity = set(candidate.source_diversity)
    diversity.add(signal.independence_key)
    candidate.source_diversity = sorted(diversity)
    candidate.independent_source_count = len(candidate.source_diversity)
    unresolved = set(candidate.unresolved_questions)
    unresolved.update(signal.unresolved_questions)
    candidate.unresolved_questions = sorted(unresolved)
    candidate.last_material_change = max(candidate.last_material_change, signal.observed_at)
    candidate.watch_priority = min(100, 50 + 10 * min(candidate.independent_source_count, 5))
    return candidate


def _candidate_id(signal: SignalItem) -> str:
    strong = [
        f"{anchor_type}:{value.lower()}"
        for anchor_type, values in sorted(signal.anchors.items())
        if anchor_type in STRONG_ANCHORS
        for value in sorted(values)
    ]
    seed = "|".join(strong) if strong else f"signal:{signal.signal_id}"
    return str(uuid5(NAMESPACE_URL, f"secfusion:incident-candidate:{signal.incident_type}:{seed}"))


def _strong_overlap_count(candidate: IncidentCandidate, signal: SignalItem) -> int:
    count = 0
    for anchor_type, values in signal.anchors.items():
        if anchor_type not in STRONG_ANCHORS:
            continue
        count += len(set(values) & set(candidate.anchor_set.get(anchor_type, [])))
    return count


def _next_poll_at(candidate: IncidentCandidate, now: datetime) -> datetime:
    if candidate.watch_priority >= 90:
        return now + timedelta(minutes=15)
    if candidate.watch_priority >= 70:
        return now + timedelta(hours=1)
    return now + timedelta(hours=4)


def _materially_changed(before: IncidentCandidate, after: IncidentCandidate) -> bool:
    return (
        before.anchor_set != after.anchor_set
        or before.independent_source_count != after.independent_source_count
        or before.unresolved_questions != after.unresolved_questions
        or before.signal_ids != after.signal_ids
    )
