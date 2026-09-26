from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.incident.contracts import (
    IncidentCandidate,
    IncidentSignalStore,
    SignalItem,
)
from packages.intelligence.ingestion.evidence import EvidenceIngress, ObservationAck
from packages.intelligence.storage.incident_models import (
    IncidentRevisionModel,
    IncidentSourceLinkModel,
    IncidentTimelineEventModel,
    SecurityIncidentModel,
)
from packages.shared.storage.models import OutboxEventModel
from packages.sources.contracts import (
    AcquisitionTrigger,
    IngestEnvelope,
    SourceDefinition,
    SourceRole,
)

DIRECT_EVIDENCE_ANCHORS = {
    "tx_hash",
    "ioc",
    "advisory_id",
    "commit",
}


class IncidentNotPromotable(ValueError):
    pass


class IncidentPromotionDecision(BaseModel):
    eligible: bool
    reason: str | None = None


class IncidentPromotionResult(BaseModel):
    incident_id: str
    incident_revision: int
    observation_ids: list[str]
    timeline_event_ids: list[str]
    replay: bool = False


class IncidentPromotionPolicy:
    def decide(
        self,
        candidate: IncidentCandidate,
        signals: list[SignalItem],
    ) -> IncidentPromotionDecision:
        if candidate.pinned:
            return IncidentPromotionDecision(eligible=True, reason="analyst_pin")
        if any(
            signal.source_role in {SourceRole.PRIMARY, SourceRole.AUTHORITY} for signal in signals
        ):
            return IncidentPromotionDecision(eligible=True, reason="primary_or_authority")
        if any(
            anchor_type in DIRECT_EVIDENCE_ANCHORS and values
            for signal in signals
            for anchor_type, values in signal.anchors.items()
        ):
            return IncidentPromotionDecision(eligible=True, reason="direct_evidence_anchor")
        if _has_independent_anchor_corroboration(signals):
            return IncidentPromotionDecision(eligible=True, reason="independent_corroboration")
        return IncidentPromotionDecision(eligible=False)


class IncidentPromotionService:
    def __init__(
        self,
        store: IncidentSignalStore,
        evidence_ingress: EvidenceIngress,
        policy: IncidentPromotionPolicy,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._evidence_ingress = evidence_ingress
        self._policy = policy
        self._now = now or (lambda: datetime.now(UTC))

    async def promote(
        self,
        session: AsyncSession,
        *,
        candidate_id: str,
        sources: dict[str, SourceDefinition],
    ) -> IncidentPromotionResult:
        candidate = await self._store.get_candidate(candidate_id)
        if candidate is None:
            raise LookupError(f"incident candidate not found: {candidate_id}")
        signals = await self._load_signals(candidate)
        decision = self._policy.decide(candidate, signals)
        if not decision.eligible or decision.reason is None:
            raise IncidentNotPromotable(f"incident candidate is not promotable: {candidate_id}")

        existing = await session.scalar(
            select(SecurityIncidentModel).where(
                SecurityIncidentModel.candidate_id == candidate.candidate_id
            )
        )
        if existing is not None:
            return await self._append_to_existing_incident(
                session,
                incident=existing,
                candidate=candidate,
                signals=signals,
                sources=sources,
            )

        selected = _select_supporting_signals(signals, decision.reason)
        observation_pairs: list[tuple[SignalItem, ObservationAck]] = []
        for signal in selected:
            source = sources.get(signal.source_id)
            if source is None:
                raise ValueError(
                    f"missing source definition for incident signal {signal.source_id}"
                )
            envelope = _signal_envelope(signal)
            observation = await self._evidence_ingress.accept(session, source, envelope)
            observation_pairs.append((signal, observation))

        now = self._now()
        first_observation_id = observation_pairs[0][1].observation_id if observation_pairs else None
        revision = IncidentRevisionModel(
            cause_observation_id=first_observation_id,
            committed_at=now,
        )
        session.add(revision)
        await session.flush()

        incident_id = _stable_id(f"incident:{candidate.candidate_id}")
        latest_signal = max(selected, key=lambda item: item.observed_at)
        incident = SecurityIncidentModel(
            incident_id=incident_id,
            candidate_id=candidate.candidate_id,
            incident_type=candidate.incident_type,
            lifecycle="active",
            promotion_reason=decision.reason,
            current_summary=latest_signal.summary or latest_signal.title,
            watch_state={
                "watch_priority": candidate.watch_priority,
                "next_poll_at": (
                    candidate.next_poll_at.isoformat()
                    if candidate.next_poll_at is not None
                    else None
                ),
                "unresolved_questions": candidate.unresolved_questions,
            },
            created_revision=revision.revision,
            current_revision=revision.revision,
            created_at=now,
            updated_at=now,
        )
        session.add(incident)

        event_ids: list[str] = []
        observation_ids: list[str] = []
        for signal, observation in observation_pairs:
            event_id = _stable_id(f"incident-event:{incident_id}:{signal.signal_id}")
            event_ids.append(event_id)
            observation_ids.append(observation.observation_id)
            session.add(
                IncidentTimelineEventModel(
                    event_id=event_id,
                    incident_id=incident_id,
                    signal_id=signal.signal_id,
                    event_time=signal.published_at or signal.observed_at,
                    observed_at=signal.observed_at,
                    event_type=_event_type(signal),
                    summary=signal.summary or signal.title,
                    source_role=signal.source_role.value,
                    claim_refs=[],
                    evidence_refs=[observation.observation_id],
                    supersedes_event_id=None,
                    created_revision=revision.revision,
                )
            )
            session.add(
                IncidentSourceLinkModel(
                    source_link_id=_stable_id(
                        f"incident-source:{incident_id}:{observation.observation_id}"
                    ),
                    incident_id=incident_id,
                    observation_id=observation.observation_id,
                    source_id=signal.source_id,
                    source_family=signal.source_family,
                    upstream_source=signal.upstream_source,
                    independence_key=signal.independence_key,
                    source_role=signal.source_role.value,
                    created_revision=revision.revision,
                )
            )

        session.add(
            OutboxEventModel(
                event_id=_stable_id(f"outbox:incident.changed:{incident_id}:{revision.revision}"),
                topic="incident.changed",
                aggregate_id=incident_id,
                payload={
                    "incident_id": incident_id,
                    "revision": revision.revision,
                },
                status="pending",
                attempts=0,
                available_at=now,
            )
        )

        candidate.promotion_state = "promoted"
        await self._store.put_candidate(candidate, ttl_seconds=7 * 24 * 60 * 60)
        await session.flush()
        return IncidentPromotionResult(
            incident_id=incident_id,
            incident_revision=revision.revision,
            observation_ids=observation_ids,
            timeline_event_ids=event_ids,
        )

    async def _append_to_existing_incident(
        self,
        session: AsyncSession,
        *,
        incident: SecurityIncidentModel,
        candidate: IncidentCandidate,
        signals: list[SignalItem],
        sources: dict[str, SourceDefinition],
    ) -> IncidentPromotionResult:
        existing_events = list(
            await session.scalars(
                select(IncidentTimelineEventModel).where(
                    IncidentTimelineEventModel.incident_id == incident.incident_id
                )
            )
        )
        existing_signal_ids = {event.signal_id for event in existing_events}
        new_signals = [signal for signal in signals if signal.signal_id not in existing_signal_ids]
        if not new_signals:
            existing_observation_ids = list(
                await session.scalars(
                    select(IncidentSourceLinkModel.observation_id).where(
                        IncidentSourceLinkModel.incident_id == incident.incident_id
                    )
                )
            )
            candidate.promotion_state = "promoted"
            await self._store.put_candidate(candidate, ttl_seconds=7 * 24 * 60 * 60)
            return IncidentPromotionResult(
                incident_id=incident.incident_id,
                incident_revision=incident.current_revision,
                observation_ids=existing_observation_ids,
                timeline_event_ids=[event.event_id for event in existing_events],
                replay=True,
            )

        observation_pairs: list[tuple[SignalItem, ObservationAck]] = []
        for signal in new_signals:
            source = sources.get(signal.source_id)
            if source is None:
                raise ValueError(
                    f"missing source definition for incident signal {signal.source_id}"
                )
            observation = await self._evidence_ingress.accept(
                session,
                source,
                _signal_envelope(signal),
            )
            observation_pairs.append((signal, observation))

        now = self._now()
        revision = IncidentRevisionModel(
            cause_observation_id=observation_pairs[0][1].observation_id,
            committed_at=now,
        )
        session.add(revision)
        await session.flush()

        event_ids: list[str] = []
        observation_ids: list[str] = []
        for signal, observation in observation_pairs:
            event_id = _stable_id(f"incident-event:{incident.incident_id}:{signal.signal_id}")
            event_ids.append(event_id)
            observation_ids.append(observation.observation_id)
            session.add(
                IncidentTimelineEventModel(
                    event_id=event_id,
                    incident_id=incident.incident_id,
                    signal_id=signal.signal_id,
                    event_time=signal.published_at or signal.observed_at,
                    observed_at=signal.observed_at,
                    event_type=_event_type(signal),
                    summary=signal.summary or signal.title,
                    source_role=signal.source_role.value,
                    claim_refs=[],
                    evidence_refs=[observation.observation_id],
                    supersedes_event_id=None,
                    created_revision=revision.revision,
                )
            )
            session.add(
                IncidentSourceLinkModel(
                    source_link_id=_stable_id(
                        f"incident-source:{incident.incident_id}:{observation.observation_id}"
                    ),
                    incident_id=incident.incident_id,
                    observation_id=observation.observation_id,
                    source_id=signal.source_id,
                    source_family=signal.source_family,
                    upstream_source=signal.upstream_source,
                    independence_key=signal.independence_key,
                    source_role=signal.source_role.value,
                    created_revision=revision.revision,
                )
            )

        latest_signal = max(new_signals, key=lambda item: item.observed_at)
        incident.current_revision = revision.revision
        incident.current_summary = latest_signal.summary or latest_signal.title
        incident.watch_state = {
            "watch_priority": candidate.watch_priority,
            "next_poll_at": (
                candidate.next_poll_at.isoformat() if candidate.next_poll_at is not None else None
            ),
            "unresolved_questions": candidate.unresolved_questions,
        }
        incident.updated_at = now
        session.add(
            OutboxEventModel(
                event_id=_stable_id(
                    f"outbox:incident.changed:{incident.incident_id}:{revision.revision}"
                ),
                topic="incident.changed",
                aggregate_id=incident.incident_id,
                payload={
                    "incident_id": incident.incident_id,
                    "revision": revision.revision,
                },
                status="pending",
                attempts=0,
                available_at=now,
            )
        )
        candidate.promotion_state = "promoted"
        await self._store.put_candidate(candidate, ttl_seconds=7 * 24 * 60 * 60)
        await session.flush()
        return IncidentPromotionResult(
            incident_id=incident.incident_id,
            incident_revision=revision.revision,
            observation_ids=observation_ids,
            timeline_event_ids=event_ids,
            replay=False,
        )

    async def _load_signals(self, candidate: IncidentCandidate) -> list[SignalItem]:
        signals: list[SignalItem] = []
        for signal_id in candidate.signal_ids:
            signal = await self._store.get_signal(signal_id)
            if signal is not None:
                signals.append(signal)
        if not signals:
            raise RuntimeError("incident candidate has no surviving signals")
        return signals


def _signal_envelope(signal: SignalItem) -> IngestEnvelope:
    envelope = IngestEnvelope.for_json_payload(
        acquisition_run_id=signal.acquisition_run_id,
        trigger=AcquisitionTrigger.PROMOTION,
        source_id=signal.source_id,
        external_object_id=signal.external_object_id,
        payload=signal.raw_payload,
        canonical_url=signal.canonical_url,
        published_at=signal.published_at,
        updated_at=signal.observed_at,
        external_revision=signal.external_revision,
        request_metadata={"promoted_from": f"incident:signal:{signal.signal_id}"},
        observed_at=signal.observed_at,
    )
    if envelope.content_hash != signal.content_hash:
        raise RuntimeError("incident signal payload hash no longer matches recorded hash")
    return envelope


def _select_supporting_signals(signals: list[SignalItem], reason: str) -> list[SignalItem]:
    if reason == "primary_or_authority":
        preferred = [
            signal
            for signal in signals
            if signal.source_role in {SourceRole.PRIMARY, SourceRole.AUTHORITY}
        ]
        return preferred or [max(signals, key=lambda item: item.observed_at)]
    if reason == "direct_evidence_anchor":
        direct = [
            signal
            for signal in signals
            if any(
                anchor_type in DIRECT_EVIDENCE_ANCHORS and values
                for anchor_type, values in signal.anchors.items()
            )
        ]
        return direct or [max(signals, key=lambda item: item.observed_at)]
    if reason == "independent_corroboration":
        selected: list[SignalItem] = []
        seen: set[str] = set()
        for signal in sorted(signals, key=lambda item: item.observed_at):
            if signal.independence_key in seen:
                continue
            selected.append(signal)
            seen.add(signal.independence_key)
            if len(selected) == 2:
                break
        return selected
    return [max(signals, key=lambda item: item.observed_at)]


def _event_type(signal: SignalItem) -> str:
    event_type = signal.raw_payload.get("event_type")
    return event_type if isinstance(event_type, str) and event_type else "reported"


def _has_independent_anchor_corroboration(signals: list[SignalItem]) -> bool:
    support: dict[tuple[str, str], set[str]] = {}
    strong_anchor_types = {
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
    for signal in signals:
        for anchor_type, values in signal.anchors.items():
            if anchor_type not in strong_anchor_types:
                continue
            for value in values:
                support.setdefault((anchor_type, value.lower()), set()).add(signal.independence_key)
    return any(len(independent_sources) >= 2 for independent_sources in support.values())


def _stable_id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"secfusion:{value}"))
