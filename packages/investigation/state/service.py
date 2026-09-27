from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from pydantic import BaseModel, JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.retrieval.validation import (
    evidence_support_summary,
    validate_object_refs,
    validate_target_ref,
)
from packages.investigation.state.contracts import (
    CaseStateEvent,
    CaseStateEventType,
    EvidenceNeed,
    EvidenceNeedContract,
    EvidenceNeedStatus,
    InvestigationState,
    InvestigationStateItem,
    PatchDisposition,
    ProposedState,
    ReasoningSemantics,
    StatePatch,
    StatePatchOperation,
)
from packages.investigation.storage.models import (
    CaseStateEventModel,
    EvidenceNeedModel,
    InvestigationCaseModel,
    InvestigationStateCurrentModel,
    PerceptionEventModel,
)


class StateRevisionConflict(RuntimeError):
    pass


class StatePatchRejected(ValueError):
    pass


class StatePatchApplyResult(BaseModel):
    state: InvestigationState
    events: list[CaseStateEvent]
    replay: bool = False


class EvidenceNeedOpenResult(BaseModel):
    need: EvidenceNeed
    state: InvestigationState
    event: CaseStateEvent
    replay: bool = False


class InvestigationStateService:
    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(UTC))

    async def get_state(self, session: AsyncSession, case_id: str) -> InvestigationState:
        case = await session.get(InvestigationCaseModel, case_id)
        if case is None:
            raise LookupError(f"investigation case not found: {case_id}")
        current = await session.get(InvestigationStateCurrentModel, case_id)
        if current is None:
            current = await self._rebuild_current(session, case)
        return _state_view(current)

    async def rebuild(self, session: AsyncSession, case_id: str) -> InvestigationState:
        case = await session.get(InvestigationCaseModel, case_id)
        if case is None:
            raise LookupError(f"investigation case not found: {case_id}")
        current = await self._rebuild_current(session, case, force=True)
        return _state_view(current)

    async def get_evidence_need(self, session: AsyncSession, need_id: str) -> EvidenceNeed:
        model = await session.get(EvidenceNeedModel, need_id)
        if model is None:
            raise LookupError(f"EvidenceNeed not found: {need_id}")
        return _need_view(model)

    async def list_evidence_needs(
        self,
        session: AsyncSession,
        case_id: str,
        *,
        statuses: set[EvidenceNeedStatus] | None = None,
    ) -> list[EvidenceNeed]:
        query = select(EvidenceNeedModel).where(EvidenceNeedModel.case_id == case_id)
        if statuses:
            query = query.where(EvidenceNeedModel.status.in_([item.value for item in statuses]))
        models = list(
            await session.scalars(
                query.order_by(EvidenceNeedModel.priority.desc(), EvidenceNeedModel.need_id)
            )
        )
        return [_need_view(model) for model in models]

    async def mark_perception(
        self,
        session: AsyncSession,
        *,
        case_id: str,
        perception_event_id: str,
        world_revision: int,
        perceived_at: datetime,
    ) -> InvestigationState:
        case = await _lock_case(session, case_id)
        patch_id = f"perception:{perception_event_id}"
        existing = await session.scalar(
            select(CaseStateEventModel).where(
                CaseStateEventModel.case_id == case_id,
                CaseStateEventModel.patch_id == patch_id,
                CaseStateEventModel.operation_index == 0,
                CaseStateEventModel.event_type == CaseStateEventType.PERCEPTION_RECORDED.value,
            )
        )
        if existing is None:
            await _append_event(
                session,
                case,
                event_type=CaseStateEventType.PERCEPTION_RECORDED,
                proposition=None,
                target_ref=None,
                evidence_refs=[],
                writer="perception-runtime",
                reason_code="perception_coordinate_advanced",
                payload={
                    "perception_event_id": perception_event_id,
                    "world_revision": world_revision,
                    "perceived_at": _utc_datetime(perceived_at).isoformat(),
                },
                created_at=self._now(),
                patch_id=patch_id,
                operation_index=0,
            )
        else:
            stored_perception_id = existing.payload.get("perception_event_id")
            stored_world_revision = existing.payload.get("world_revision")
            stored_perceived_at = _payload_datetime(existing.payload.get("perceived_at"))
            if (
                stored_perception_id != perception_event_id
                or stored_world_revision != world_revision
                or stored_perceived_at != _utc_datetime(perceived_at)
            ):
                raise ValueError("perception state replay identity changed payload")
        current = await self._rebuild_current(session, case, force=True)
        return _state_view(current)

    async def open_evidence_need(
        self,
        session: AsyncSession,
        *,
        case_id: str,
        base_case_revision: int,
        need_id: str,
        proposition_or_question: str,
        purpose: str,
        target_objects: list[str],
        evidence_contract: EvidenceNeedContract | None = None,
        derived_from_enrichment_requirement: str | None = None,
        preferred_source_roles: list[str] | None = None,
        rejected_evidence_patterns: list[str] | None = None,
        freshness_requirement: dict[str, object] | None = None,
        completion_predicate: dict[str, object] | None = None,
        priority: int = 50,
        writer: str = "state-runtime",
        reason_code: str = "evidence_gap",
    ) -> EvidenceNeedOpenResult:
        case = await _lock_case(session, case_id)
        existing = await session.get(EvidenceNeedModel, need_id)
        if existing is not None:
            event_models = list(
                await session.scalars(
                    select(CaseStateEventModel).where(
                        CaseStateEventModel.case_id == case_id,
                        CaseStateEventModel.event_type
                        == CaseStateEventType.EVIDENCE_NEED_OPENED.value,
                    )
                )
            )
            event_model = next(
                (item for item in event_models if item.payload.get("need_id") == need_id),
                None,
            )
            if event_model is None:
                raise RuntimeError("evidence need exists without open event")
            return EvidenceNeedOpenResult(
                need=_need_view(existing),
                state=await self.get_state(session, case_id),
                event=_event_view(event_model),
                replay=True,
            )
        _require_revision(case, base_case_revision)
        if not proposition_or_question.strip() or not purpose.strip():
            raise ValueError("EvidenceNeed proposition/purpose cannot be empty")
        await _validate_target_objects(session, target_objects)

        now = self._now()
        event = await _append_event(
            session,
            case,
            event_type=CaseStateEventType.EVIDENCE_NEED_OPENED,
            proposition=proposition_or_question,
            target_ref=None,
            evidence_refs=[],
            writer=writer,
            reason_code=reason_code,
            payload={"need_id": need_id},
            created_at=now,
        )
        contract = evidence_contract or EvidenceNeedContract()
        model = EvidenceNeedModel(
            need_id=need_id,
            case_id=case_id,
            derived_from_enrichment_requirement=derived_from_enrichment_requirement,
            proposition_or_question=proposition_or_question,
            purpose=purpose,
            target_objects=list(target_objects),
            evidence_contract=contract.model_dump(mode="json"),
            preferred_source_roles=list(preferred_source_roles or []),
            rejected_evidence_patterns=list(rejected_evidence_patterns or []),
            freshness_requirement=dict(freshness_requirement or {}),
            completion_predicate=dict(completion_predicate or {"type": "state_accepted"}),
            priority=priority,
            status=EvidenceNeedStatus.OPEN.value,
            resolution_evidence_refs=[],
            opened_revision=event.case_revision,
            updated_revision=event.case_revision,
            opened_at=now,
            updated_at=now,
        )
        session.add(model)
        await session.flush()
        current = await self._rebuild_current(session, case, force=True)
        return EvidenceNeedOpenResult(
            need=_need_view(model),
            state=_state_view(current),
            event=event,
            replay=False,
        )

    async def reopen_evidence_need(
        self,
        session: AsyncSession,
        *,
        need_id: str,
        base_case_revision: int,
        reopen_key: str,
        writer: str = "state-runtime",
        reason_code: str = "world_change_reopened",
    ) -> EvidenceNeedOpenResult:
        need = await session.get(EvidenceNeedModel, need_id)
        if need is None:
            raise LookupError(f"EvidenceNeed not found: {need_id}")
        case = await _lock_case(session, need.case_id)
        existing_event = await session.scalar(
            select(CaseStateEventModel).where(
                CaseStateEventModel.case_id == need.case_id,
                CaseStateEventModel.patch_id == reopen_key,
                CaseStateEventModel.operation_index == 0,
                CaseStateEventModel.event_type == CaseStateEventType.EVIDENCE_NEED_OPENED.value,
            )
        )
        if existing_event is not None:
            return EvidenceNeedOpenResult(
                need=_need_view(need),
                state=await self.get_state(session, need.case_id),
                event=_event_view(existing_event),
                replay=True,
            )
        if need.status == EvidenceNeedStatus.OPEN.value:
            original_event = await session.scalar(
                select(CaseStateEventModel)
                .where(
                    CaseStateEventModel.case_id == need.case_id,
                    CaseStateEventModel.event_type == CaseStateEventType.EVIDENCE_NEED_OPENED.value,
                )
                .order_by(CaseStateEventModel.case_revision.desc())
            )
            if original_event is None:
                raise RuntimeError("open EvidenceNeed exists without open event")
            return EvidenceNeedOpenResult(
                need=_need_view(need),
                state=await self.get_state(session, need.case_id),
                event=_event_view(original_event),
                replay=True,
            )
        _require_revision(case, base_case_revision)
        now = self._now()
        event = await _append_event(
            session,
            case,
            event_type=CaseStateEventType.EVIDENCE_NEED_OPENED,
            patch_id=reopen_key,
            operation_index=0,
            proposition=need.proposition_or_question,
            target_ref=None,
            evidence_refs=[],
            writer=writer,
            reason_code=reason_code,
            payload={"need_id": need.need_id, "reopened": True},
            created_at=now,
        )
        need.status = EvidenceNeedStatus.OPEN.value
        need.resolution_evidence_refs = []
        need.updated_revision = event.case_revision
        need.updated_at = now
        current = await self._rebuild_current(session, case, force=True)
        return EvidenceNeedOpenResult(
            need=_need_view(need),
            state=_state_view(current),
            event=event,
            replay=False,
        )

    async def apply_patch(
        self,
        session: AsyncSession,
        patch: StatePatch,
        *,
        reason_code: str = "state_patch_accepted",
    ) -> StatePatchApplyResult:
        case = await _lock_case(session, patch.case_id)
        existing = list(
            await session.scalars(
                select(CaseStateEventModel)
                .where(
                    CaseStateEventModel.case_id == patch.case_id,
                    CaseStateEventModel.patch_id == patch.patch_id,
                )
                .order_by(CaseStateEventModel.operation_index, CaseStateEventModel.case_revision)
            )
        )
        if existing:
            return StatePatchApplyResult(
                state=await self.get_state(session, patch.case_id),
                events=[_event_view(item) for item in existing],
                replay=True,
            )
        _require_revision(case, patch.base_case_revision)
        await self._validate_patch(session, patch)

        events: list[CaseStateEvent] = []
        for index, operation in enumerate(patch.operations):
            event = await _append_event(
                session,
                case,
                event_type=_event_type_for(operation),
                patch_id=patch.patch_id,
                operation_index=index,
                proposition=operation.proposition,
                target_ref=operation.target_ref,
                evidence_refs=operation.evidence_refs,
                writer=patch.producer,
                reason_code=reason_code,
                payload={
                    "proposed_state": operation.proposed_state.value,
                    "disposition": operation.disposition.value,
                    "reasoning_relation": (
                        operation.reasoning_relation.model_dump(mode="json")
                        if operation.reasoning_relation is not None
                        else None
                    ),
                    "resolves_need_id": operation.resolves_need_id,
                    "model_prompt_revision": patch.model_prompt_revision,
                },
                created_at=self._now(),
            )
            events.append(event)
            if operation.resolves_need_id is not None:
                resolved = await self._resolve_need_from_operation(
                    session,
                    case,
                    operation,
                    writer=patch.producer,
                )
                if resolved is not None:
                    events.append(resolved)

        current = await self._rebuild_current(session, case, force=True)
        return StatePatchApplyResult(
            state=_state_view(current),
            events=events,
            replay=False,
        )

    async def _validate_patch(self, session: AsyncSession, patch: StatePatch) -> None:
        for operation in patch.operations:
            if operation.target_ref is not None:
                await _validate_target_ref(session, operation.target_ref)
            await _validate_evidence_refs(session, operation.evidence_refs)
            if (
                operation.target_ref is not None
                and operation.target_ref.startswith("object:")
                and operation.proposed_state in {ProposedState.CONFIRMED, ProposedState.CONFLICT}
                and operation.disposition is PatchDisposition.SET
            ):
                support = await evidence_support_summary(session, operation.evidence_refs)
                target_object_id = operation.target_ref.removeprefix("object:")
                if target_object_id not in support.supported_object_ids:
                    raise StatePatchRejected(
                        "EvidenceRef does not support StatePatch target object"
                    )
            if (
                operation.reasoning_relation is not None
                and operation.reasoning_relation.semantics is ReasoningSemantics.INFERRED
                and operation.proposed_state is ProposedState.CONFIRMED
                and operation.disposition is PatchDisposition.SET
            ):
                raise StatePatchRejected("inferred reasoning relation cannot write confirmed state")
            if operation.resolves_need_id is not None:
                need = await session.get(EvidenceNeedModel, operation.resolves_need_id)
                if need is None or need.case_id != patch.case_id:
                    raise StatePatchRejected("resolves_need_id does not belong to this case")
                if need.status != EvidenceNeedStatus.OPEN.value:
                    raise StatePatchRejected("only an open EvidenceNeed can be resolved")
                await _validate_need_resolution(session, need, operation)

    async def _resolve_need_from_operation(
        self,
        session: AsyncSession,
        case: InvestigationCaseModel,
        operation: StatePatchOperation,
        *,
        writer: str,
    ) -> CaseStateEvent | None:
        if operation.resolves_need_id is None:
            return None
        need = await session.get(EvidenceNeedModel, operation.resolves_need_id)
        if need is None:
            raise RuntimeError("validated EvidenceNeed disappeared")
        need.status = EvidenceNeedStatus.RESOLVED.value
        need.resolution_evidence_refs = list(operation.evidence_refs)
        need.updated_at = self._now()
        event = await _append_event(
            session,
            case,
            event_type=CaseStateEventType.EVIDENCE_NEED_RESOLVED,
            proposition=need.proposition_or_question,
            target_ref=operation.target_ref,
            evidence_refs=operation.evidence_refs,
            writer=writer,
            reason_code="evidence_need_completion_predicate_satisfied",
            payload={"need_id": need.need_id},
            created_at=self._now(),
        )
        need.updated_revision = event.case_revision
        return event

    async def _rebuild_current(
        self,
        session: AsyncSession,
        case: InvestigationCaseModel,
        *,
        force: bool = False,
    ) -> InvestigationStateCurrentModel:
        current = await session.get(InvestigationStateCurrentModel, case.case_id)
        if current is not None and current.case_revision == case.current_revision and not force:
            return current
        events = list(
            await session.scalars(
                select(CaseStateEventModel)
                .where(CaseStateEventModel.case_id == case.case_id)
                .order_by(CaseStateEventModel.case_revision)
            )
        )
        buckets: dict[str, dict[tuple[str, str | None], dict[str, object]]] = {
            "confirmed": {},
            "tentative": {},
            "conflicts": {},
            "unknowns": {},
            "hypotheses": {},
        }
        current_decision: dict[str, object] | None = None
        for event in events:
            _replay_event(buckets, event)
            if event.event_type == CaseStateEventType.DECISION_CHANGED.value:
                decision = event.payload.get("decision")
                current_decision = decision if isinstance(decision, dict) else None
        open_need_ids = list(
            await session.scalars(
                select(EvidenceNeedModel.need_id)
                .where(
                    EvidenceNeedModel.case_id == case.case_id,
                    EvidenceNeedModel.status.in_(
                        [EvidenceNeedStatus.OPEN.value, EvidenceNeedStatus.BLOCKED.value]
                    ),
                )
                .order_by(EvidenceNeedModel.priority.desc(), EvidenceNeedModel.need_id)
            )
        )
        latest_perception = await session.scalar(
            select(PerceptionEventModel)
            .where(PerceptionEventModel.case_id == case.case_id)
            .order_by(
                PerceptionEventModel.finished_at.desc(),
                PerceptionEventModel.perception_event_id.desc(),
            )
            .limit(1)
        )
        now = self._now()
        values = dict(
            case_revision=case.current_revision,
            goal=case.goal,
            targets=list(case.target_object_ids),
            confirmed=list(buckets["confirmed"].values()),
            tentative=list(buckets["tentative"].values()),
            conflicts=list(buckets["conflicts"].values()),
            unknowns=list(buckets["unknowns"].values()),
            hypotheses=list(buckets["hypotheses"].values()),
            evidence_need_ids=open_need_ids,
            current_decision=current_decision,
            last_world_revision=(
                latest_perception.world_revision
                if latest_perception is not None
                else case.initial_knowledge_revision
            ),
            last_perception_at=(
                latest_perception.finished_at if latest_perception is not None else None
            ),
            updated_at=now,
        )
        if current is None:
            current = InvestigationStateCurrentModel(
                case_id=case.case_id,
                open_questions=[],
                decision_variables=[],
                active_skills=[],
                normative_context_refs=[],
                unresolved_applicability=[],
                **values,
            )
            session.add(current)
        else:
            for key, value in values.items():
                setattr(current, key, value)
        await session.flush()
        return current


async def _lock_case(session: AsyncSession, case_id: str) -> InvestigationCaseModel:
    case = await session.scalar(
        select(InvestigationCaseModel)
        .where(InvestigationCaseModel.case_id == case_id)
        .with_for_update()
    )
    if case is None:
        raise LookupError(f"investigation case not found: {case_id}")
    if case.status in {"closed", "cancelled"}:
        raise StatePatchRejected(f"case state is immutable in lifecycle={case.status}")
    return case


def _require_revision(case: InvestigationCaseModel, base_revision: int) -> None:
    if case.current_revision != base_revision:
        raise StateRevisionConflict(
            f"stale case revision: base={base_revision}, current={case.current_revision}"
        )


async def _append_event(
    session: AsyncSession,
    case: InvestigationCaseModel,
    *,
    event_type: CaseStateEventType,
    proposition: str | None,
    target_ref: str | None,
    evidence_refs: list[str],
    writer: str,
    reason_code: str,
    payload: dict[str, object],
    created_at: datetime,
    patch_id: str | None = None,
    operation_index: int | None = None,
) -> CaseStateEvent:
    base = case.current_revision
    revision = base + 1
    event = CaseStateEventModel(
        event_id=str(uuid4()),
        case_id=case.case_id,
        case_revision=revision,
        base_case_revision=base,
        event_type=event_type.value,
        patch_id=patch_id,
        operation_index=operation_index,
        proposition=proposition,
        target_ref=target_ref,
        evidence_refs=list(evidence_refs),
        writer=writer,
        reason_code=reason_code,
        payload=payload,
        created_at=created_at,
    )
    session.add(event)
    case.current_revision = revision
    if case.status in {"open", "running", "created", "waiting"}:
        case.status = "active"
    await session.flush()
    return _event_view(event)


async def _validate_target_objects(session: AsyncSession, object_ids: list[str]) -> None:
    missing = await validate_object_refs(session, object_ids)
    if missing:
        raise StatePatchRejected(f"target object not found: {missing[0]}")


async def _validate_target_ref(session: AsyncSession, target_ref: str) -> None:
    if not await validate_target_ref(session, target_ref):
        raise StatePatchRejected(f"invalid or missing target_ref: {target_ref}")


async def _validate_evidence_refs(session: AsyncSession, evidence_refs: list[str]) -> None:
    if not evidence_refs:
        return
    support = await evidence_support_summary(session, evidence_refs)
    missing = sorted(set(evidence_refs) - set(support.evidence_refs))
    if missing:
        raise StatePatchRejected(f"unknown EvidenceRef: {missing[0]}")


async def _validate_need_resolution(
    session: AsyncSession,
    need: EvidenceNeedModel,
    operation: StatePatchOperation,
) -> None:
    contract = EvidenceNeedContract.model_validate(need.evidence_contract)
    if operation.proposed_state not in contract.accepted_states:
        raise StatePatchRejected("proposed state does not satisfy EvidenceNeed completion contract")
    predicate_type = need.completion_predicate.get("type")
    if predicate_type != "state_accepted":
        raise StatePatchRejected(f"unsupported EvidenceNeed completion predicate: {predicate_type}")
    if contract.require_evidence and not operation.evidence_refs:
        raise StatePatchRejected("EvidenceNeed resolution requires evidence")
    if not operation.evidence_refs:
        return
    support = await evidence_support_summary(session, operation.evidence_refs)
    for role in contract.required_source_roles:
        if role not in support.source_roles:
            raise StatePatchRejected(f"required source role missing: {role}")
    if len(support.independent_source_keys) < contract.min_independent_sources:
        raise StatePatchRejected(
            "independent source requirement unsatisfied: "
            f"{len(support.independent_source_keys)}/{contract.min_independent_sources}"
        )


def _event_type_for(operation: StatePatchOperation) -> CaseStateEventType:
    mapping = {
        (ProposedState.CONFIRMED, PatchDisposition.SET): CaseStateEventType.FACT_CONFIRMED,
        (ProposedState.CONFIRMED, PatchDisposition.CLEAR): CaseStateEventType.FACT_RETRACTED,
        (ProposedState.TENTATIVE, PatchDisposition.SET): CaseStateEventType.TENTATIVE_ADDED,
        (ProposedState.TENTATIVE, PatchDisposition.CLEAR): CaseStateEventType.TENTATIVE_REMOVED,
        (ProposedState.CONFLICT, PatchDisposition.SET): CaseStateEventType.CONFLICT_OPENED,
        (ProposedState.CONFLICT, PatchDisposition.CLEAR): CaseStateEventType.CONFLICT_RESOLVED,
        (ProposedState.UNKNOWN, PatchDisposition.SET): CaseStateEventType.UNKNOWN_OPENED,
        (ProposedState.UNKNOWN, PatchDisposition.CLEAR): CaseStateEventType.UNKNOWN_RESOLVED,
        (ProposedState.HYPOTHESIS, PatchDisposition.SET): CaseStateEventType.HYPOTHESIS_ADDED,
        (ProposedState.HYPOTHESIS, PatchDisposition.CLEAR): CaseStateEventType.HYPOTHESIS_REJECTED,
    }
    return mapping[(operation.proposed_state, operation.disposition)]


def _replay_event(
    buckets: dict[str, dict[tuple[str, str | None], dict[str, object]]],
    event: CaseStateEventModel,
) -> None:
    if event.proposition is None:
        return
    key = (event.proposition, event.target_ref)
    item = {
        "proposition": event.proposition,
        "target_ref": event.target_ref,
        "evidence_refs": list(event.evidence_refs),
        "writer": event.writer,
        "reason_code": event.reason_code,
        "reasoning_relation": event.payload.get("reasoning_relation"),
        "updated_revision": event.case_revision,
    }
    additions = {
        CaseStateEventType.FACT_CONFIRMED.value: "confirmed",
        CaseStateEventType.TENTATIVE_ADDED.value: "tentative",
        CaseStateEventType.CONFLICT_OPENED.value: "conflicts",
        CaseStateEventType.UNKNOWN_OPENED.value: "unknowns",
        CaseStateEventType.HYPOTHESIS_ADDED.value: "hypotheses",
    }
    removals = {
        CaseStateEventType.FACT_RETRACTED.value: "confirmed",
        CaseStateEventType.TENTATIVE_REMOVED.value: "tentative",
        CaseStateEventType.CONFLICT_RESOLVED.value: "conflicts",
        CaseStateEventType.UNKNOWN_RESOLVED.value: "unknowns",
        CaseStateEventType.HYPOTHESIS_REJECTED.value: "hypotheses",
    }
    bucket = additions.get(event.event_type)
    if bucket is not None:
        if bucket != "hypotheses":
            for other in ("confirmed", "tentative", "conflicts", "unknowns"):
                buckets[other].pop(key, None)
        buckets[bucket][key] = item
        return
    bucket = removals.get(event.event_type)
    if bucket is not None:
        buckets[bucket].pop(key, None)


def _state_view(model: InvestigationStateCurrentModel) -> InvestigationState:
    return InvestigationState(
        case_id=model.case_id,
        case_revision=model.case_revision,
        goal=model.goal,
        targets=list(model.targets),
        confirmed=[InvestigationStateItem.model_validate(item) for item in model.confirmed],
        tentative=[InvestigationStateItem.model_validate(item) for item in model.tentative],
        conflicts=[InvestigationStateItem.model_validate(item) for item in model.conflicts],
        unknowns=[InvestigationStateItem.model_validate(item) for item in model.unknowns],
        hypotheses=[InvestigationStateItem.model_validate(item) for item in model.hypotheses],
        open_questions=list(model.open_questions),
        decision_variables=list(model.decision_variables),
        evidence_need_ids=list(model.evidence_need_ids),
        active_skills=list(model.active_skills),
        normative_context_refs=list(model.normative_context_refs),
        unresolved_applicability=list(model.unresolved_applicability),
        current_decision=cast(dict[str, JsonValue] | None, model.current_decision),
        last_world_revision=model.last_world_revision,
        last_perception_at=_utc_optional_datetime(model.last_perception_at),
        updated_at=_utc_datetime(model.updated_at),
    )


def _event_view(model: CaseStateEventModel) -> CaseStateEvent:
    return CaseStateEvent(
        event_id=model.event_id,
        case_id=model.case_id,
        case_revision=model.case_revision,
        base_case_revision=model.base_case_revision,
        event_type=CaseStateEventType(model.event_type),
        proposition=model.proposition,
        target_ref=model.target_ref,
        evidence_refs=list(model.evidence_refs),
        writer=model.writer,
        reason_code=model.reason_code,
        payload=cast(dict[str, JsonValue], model.payload),
        created_at=_utc_datetime(model.created_at),
    )


def _need_view(model: EvidenceNeedModel) -> EvidenceNeed:
    return EvidenceNeed(
        need_id=model.need_id,
        case_id=model.case_id,
        derived_from_enrichment_requirement=model.derived_from_enrichment_requirement,
        proposition_or_question=model.proposition_or_question,
        purpose=model.purpose,
        target_objects=list(model.target_objects),
        evidence_contract=EvidenceNeedContract.model_validate(model.evidence_contract),
        preferred_source_roles=list(model.preferred_source_roles),
        rejected_evidence_patterns=list(model.rejected_evidence_patterns),
        freshness_requirement=cast(dict[str, JsonValue], model.freshness_requirement),
        completion_predicate=cast(dict[str, JsonValue], model.completion_predicate),
        priority=model.priority,
        status=EvidenceNeedStatus(model.status),
        resolution_evidence_refs=list(model.resolution_evidence_refs),
        opened_revision=model.opened_revision,
        updated_revision=model.updated_revision,
        opened_at=_utc_datetime(model.opened_at),
        updated_at=_utc_datetime(model.updated_at),
    )


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _utc_optional_datetime(value: datetime | None) -> datetime | None:
    return None if value is None else _utc_datetime(value)


def _payload_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return _utc_datetime(parsed)
