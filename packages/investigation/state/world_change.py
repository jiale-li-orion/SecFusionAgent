from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.retrieval.validation import evidence_dependencies
from packages.investigation.cases.service import CaseService
from packages.investigation.state.contracts import (
    CaseLifecycle,
    CaseStateEventType,
    EvidenceNeedStatus,
    InvestigationStateItem,
)
from packages.investigation.state.service import (
    InvestigationStateService,
    _append_event,
    _lock_case,
)
from packages.investigation.storage.models import EvidenceNeedModel, InvestigationCaseModel


class KnowledgeChangeNotice(BaseModel):
    revision: int = Field(ge=1)
    object_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    relation_ids: list[str] = Field(default_factory=list)
    cause_observation_id: str | None = None


WorldChange = KnowledgeChangeNotice


class WorldChangeImpact(BaseModel):
    case_id: str
    world_revision: int
    case_activated: bool = False
    affected_propositions: list[str] = Field(default_factory=list)
    opened_or_reopened_need_ids: list[str] = Field(default_factory=list)


class WorldChangeService:
    """Route KnowledgeChange into Case-local invalidation/wake semantics."""

    def __init__(
        self,
        *,
        state_service: InvestigationStateService | None = None,
        case_service: CaseService | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._state_service = state_service or InvestigationStateService()
        self._case_service = case_service or CaseService()
        self._now = now or (lambda: datetime.now(UTC))

    async def process(
        self,
        session: AsyncSession,
        change: KnowledgeChangeNotice,
    ) -> list[WorldChangeImpact]:
        impacts: list[WorldChangeImpact] = []
        for case_id in await relevant_case_ids(session, change):
            case = await session.get(InvestigationCaseModel, case_id)
            if case is None or case.status in {
                CaseLifecycle.CLOSED.value,
                CaseLifecycle.CANCELLED.value,
            }:
                continue
            impacts.append(await self._apply_case(session, case_id=case_id, change=change))
        return impacts

    async def _apply_case(
        self,
        session: AsyncSession,
        *,
        case_id: str,
        change: KnowledgeChangeNotice,
    ) -> WorldChangeImpact:
        case = await _lock_case(session, case_id)
        prior_status = case.status
        state = await self._state_service.get_state(session, case_id)
        stale_items = await _stale_confirmed_items(session, state.confirmed, change)
        resolved_needs = list(
            await session.scalars(
                select(EvidenceNeedModel).where(
                    EvidenceNeedModel.case_id == case_id,
                    EvidenceNeedModel.status == EvidenceNeedStatus.RESOLVED.value,
                )
            )
        )
        stale_need_ids = await _stale_need_ids(session, resolved_needs, change)
        now = self._now()

        for item in stale_items:
            await _append_event(
                session,
                case,
                event_type=CaseStateEventType.FACT_RETRACTED,
                proposition=item.proposition,
                target_ref=item.target_ref,
                evidence_refs=list(item.evidence_refs),
                writer="world-change-runtime",
                reason_code="world_change_stale",
                payload={
                    "world_revision": change.revision,
                    "cause_observation_id": change.cause_observation_id,
                    "stale_support": True,
                },
                created_at=now,
            )
            await _append_event(
                session,
                case,
                event_type=CaseStateEventType.UNKNOWN_OPENED,
                proposition=item.proposition,
                target_ref=item.target_ref,
                evidence_refs=[],
                writer="world-change-runtime",
                reason_code="world_change_stale",
                payload={
                    "world_revision": change.revision,
                    "cause_observation_id": change.cause_observation_id,
                    "revalidate_required": True,
                },
                created_at=now,
            )

        reopened: list[str] = []
        for need in resolved_needs:
            if need.need_id not in stale_need_ids:
                continue
            need.status = EvidenceNeedStatus.OPEN.value
            need.resolution_evidence_refs = []
            need.updated_at = now
            event = await _append_event(
                session,
                case,
                event_type=CaseStateEventType.EVIDENCE_NEED_OPENED,
                proposition=need.proposition_or_question,
                target_ref=(
                    f"object:{need.target_objects[0]}" if len(need.target_objects) == 1 else None
                ),
                evidence_refs=[],
                writer="world-change-runtime",
                reason_code="world_change_reopen",
                payload={
                    "need_id": need.need_id,
                    "reopened": True,
                    "world_revision": change.revision,
                    "cause_observation_id": change.cause_observation_id,
                },
                created_at=now,
            )
            need.updated_revision = event.case_revision
            reopened.append(need.need_id)

        state_mutated = bool(stale_items or reopened)
        if state_mutated:
            await self._state_service.rebuild(session, case_id)

        case_activated = prior_status == CaseLifecycle.WAITING.value and case.status == "active"
        if prior_status == CaseLifecycle.WAITING.value and not case_activated:
            await self._case_service.activate(session, case_id)
            case_activated = True
            refreshed_case = await session.get(InvestigationCaseModel, case_id)
            if refreshed_case is None:
                raise RuntimeError("investigation case disappeared during world-change wake")
            case = refreshed_case

        await session.flush()
        return WorldChangeImpact(
            case_id=case_id,
            world_revision=change.revision,
            case_activated=case_activated,
            affected_propositions=sorted(item.proposition for item in stale_items),
            opened_or_reopened_need_ids=sorted(reopened),
        )


WorldChangeInvalidationService = WorldChangeService


async def relevant_case_ids(
    session: AsyncSession,
    change: KnowledgeChangeNotice,
) -> list[str]:
    """Deterministic relevance prefilter for refresh/WATCH wake routing."""

    changed_objects = set(change.object_ids)
    cases = list(await session.scalars(select(InvestigationCaseModel)))
    relevant: list[str] = []
    for case in cases:
        if case.status in {CaseLifecycle.CLOSED.value, CaseLifecycle.CANCELLED.value}:
            continue
        if changed_objects & set(case.target_object_ids):
            relevant.append(case.case_id)
            continue
        state = await InvestigationStateService().get_state(session, case.case_id)
        if await _evidence_refs_touch_change(
            session,
            _state_evidence_refs(state.confirmed),
            change,
        ):
            relevant.append(case.case_id)
            continue
        needs = list(
            await session.scalars(
                select(EvidenceNeedModel).where(EvidenceNeedModel.case_id == case.case_id)
            )
        )
        if any(changed_objects & set(need.target_objects) for need in needs):
            relevant.append(case.case_id)
            continue
        if await _evidence_refs_touch_change(
            session,
            [ref for need in needs for ref in need.resolution_evidence_refs],
            change,
        ):
            relevant.append(case.case_id)
    return sorted(set(relevant))


async def _stale_confirmed_items(
    session: AsyncSession,
    items: list[InvestigationStateItem],
    change: KnowledgeChangeNotice,
) -> list[InvestigationStateItem]:
    stale: list[InvestigationStateItem] = []
    changed_objects = set(change.object_ids)
    for item in items:
        if _target_ref_object_id(item.target_ref) in changed_objects:
            stale.append(item)
            continue
        if await _evidence_refs_touch_change(session, item.evidence_refs, change):
            stale.append(item)
    return stale


async def _stale_need_ids(
    session: AsyncSession,
    needs: list[EvidenceNeedModel],
    change: KnowledgeChangeNotice,
) -> set[str]:
    changed_objects = set(change.object_ids)
    result: set[str] = set()
    for need in needs:
        if changed_objects & set(need.target_objects):
            result.add(need.need_id)
            continue
        if await _evidence_refs_touch_change(session, need.resolution_evidence_refs, change):
            result.add(need.need_id)
    return result


async def _evidence_refs_touch_change(
    session: AsyncSession,
    evidence_refs: Iterable[str],
    change: KnowledgeChangeNotice,
) -> bool:
    refs = sorted(set(evidence_refs))
    if not refs:
        return False
    dependencies = await evidence_dependencies(session, refs)
    changed_objects = set(change.object_ids)
    changed_claims = set(change.claim_ids)
    changed_relations = set(change.relation_ids)
    return any(
        (item.target_kind == "claim" and item.target_id in changed_claims)
        or (item.target_kind == "relation" and item.target_id in changed_relations)
        or (item.target_kind == "object" and item.target_id in changed_objects)
        for item in dependencies
    )


def _state_evidence_refs(items: Iterable[InvestigationStateItem]) -> list[str]:
    return sorted({ref for item in items for ref in item.evidence_refs})


def _target_ref_object_id(target_ref: str | None) -> str | None:
    if target_ref is None:
        return None
    kind, separator, identity = target_ref.partition(":")
    return identity if separator and kind == "object" and identity else None
