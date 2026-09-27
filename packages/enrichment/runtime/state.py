from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.enrichment.runtime.state_models import (
    EnrichmentAttemptModel,
    EnrichmentDimensionStateModel,
)
from packages.intelligence.knowledge.vocabulary import (
    CANONICAL_TERMS,
    VOCABULARY_REVISION,
    ApplicabilityState,
    EnrichmentDimension,
    VocabularyTerm,
)
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    ExternalIdentifierModel,
    KnowledgeRevisionModel,
    ObjectModel,
    RelationModel,
)


class EnrichmentStatus(StrEnum):
    RESOLVED = "resolved"
    CONFLICT = "conflict"
    UNKNOWN = "unknown"
    MISSING = "missing"


class EnrichmentAttemptStatus(StrEnum):
    SUCCEEDED = "succeeded"
    BLOCKED = "blocked"
    FAILED = "failed"


class EnrichmentSemanticOutcome(StrEnum):
    RESOLVED = "resolved"
    UNKNOWN = "unknown"
    NO_CHANGE = "no_change"


class EnrichmentDimensionSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    requirement_id: str
    vocabulary_revision: str = VOCABULARY_REVISION
    target_object_type: str
    dimension: EnrichmentDimension
    canonical_terms: tuple[str, ...]
    required: bool = True
    acceptable_source_roles: tuple[str, ...] = ()
    authority_requirement: str | None = None
    freshness_requirement: str = "current"
    evidence_requirement: str = "evidence_backed_canonical_fact"
    completion_predicate: str = "any_supported_canonical_fact"


class EnrichmentDimensionState(BaseModel):
    target_object_id: str
    target_object_type: str
    target_object_key: str
    requirement_id: str
    vocabulary_revision: str = VOCABULARY_REVISION
    dimension: EnrichmentDimension
    status: EnrichmentStatus
    accepted_fact_refs: list[str] = Field(default_factory=list)
    conflict_refs: list[str] = Field(default_factory=list)
    missing_prerequisites: list[str] = Field(default_factory=list)
    attempted_operator_refs: list[str] = Field(default_factory=list)
    blocked_attempt_refs: list[str] = Field(default_factory=list)
    world_revision: int = Field(ge=0)


class EnrichmentStateSnapshot(BaseModel):
    target_object_id: str
    target_object_type: str
    target_object_key: str
    vocabulary_revision: str = VOCABULARY_REVISION
    world_revision: int = Field(ge=0)
    dimensions: list[EnrichmentDimensionState]

    def by_dimension(self) -> dict[EnrichmentDimension, EnrichmentDimensionState]:
        return {item.dimension: item for item in self.dimensions}


class EnrichmentAttempt(BaseModel):
    attempt_id: str
    target_object_id: str
    requirement_id: str
    dimension: EnrichmentDimension
    operator_id: str
    task_run_id: str | None = None
    execution_status: EnrichmentAttemptStatus
    semantic_outcome: EnrichmentSemanticOutcome | None = None
    blocked_reason: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    output_refs: list[str] = Field(default_factory=list)
    world_revision_before: int = Field(ge=0)
    world_revision_after: int | None = Field(default=None, ge=0)
    started_at: datetime
    finished_at: datetime | None = None


class EnrichmentStateBuilder:
    def requirements_for(self, object_type: str) -> tuple[EnrichmentDimensionSpec, ...]:
        if object_type != "Vulnerability":
            raise ValueError(f"enrichment-v1 state builder does not support {object_type!r}")
        requirements: list[EnrichmentDimensionSpec] = []
        for dimension in EnrichmentDimension:
            terms = tuple(
                sorted(
                    {
                        term.name
                        for term in CANONICAL_TERMS
                        if term.dimension is dimension
                        and _term_applies_to_object(term, object_type)
                    }
                )
            )
            if dimension is EnrichmentDimension.IDENTITY and "external-identifier" not in terms:
                terms = ("external-identifier", *terms)
            requirements.append(
                EnrichmentDimensionSpec(
                    requirement_id=(f"{VOCABULARY_REVISION}:{object_type}:{dimension.value}"),
                    target_object_type=object_type,
                    dimension=dimension,
                    canonical_terms=terms,
                )
            )
        return tuple(requirements)

    async def build(
        self,
        session: AsyncSession,
        target_object_id: str,
        *,
        materialize: bool = True,
        now: datetime | None = None,
    ) -> EnrichmentStateSnapshot:
        target = await session.get(ObjectModel, target_object_id)
        if target is None:
            raise LookupError(f"enrichment target object not found: {target_object_id}")
        requirements = self.requirements_for(target.object_type)
        world_revision = int(
            await session.scalar(select(func.max(KnowledgeRevisionModel.revision))) or 0
        )
        claims = list(
            await session.scalars(
                select(ClaimModel).where(
                    ClaimModel.subject_id == target_object_id,
                    ClaimModel.lifecycle == "accepted",
                    ClaimModel.superseded_revision.is_(None),
                )
            )
        )
        outgoing = list(
            await session.scalars(
                select(RelationModel).where(
                    RelationModel.source_object_id == target_object_id,
                    RelationModel.lifecycle == "accepted",
                    RelationModel.superseded_revision.is_(None),
                )
            )
        )
        incoming = list(
            await session.scalars(
                select(RelationModel).where(
                    RelationModel.target_object_id == target_object_id,
                    RelationModel.lifecycle == "accepted",
                    RelationModel.superseded_revision.is_(None),
                )
            )
        )
        identifiers = list(
            await session.scalars(
                select(ExternalIdentifierModel).where(
                    ExternalIdentifierModel.object_id == target_object_id
                )
            )
        )
        attempts = list(
            await session.scalars(
                select(EnrichmentAttemptModel).where(
                    EnrichmentAttemptModel.target_object_id == target_object_id
                )
            )
        )

        states = [
            _evaluate_requirement(
                requirement,
                target=target,
                world_revision=world_revision,
                claims=claims,
                outgoing=outgoing,
                incoming=incoming,
                identifiers=identifiers,
                attempts=attempts,
            )
            for requirement in requirements
        ]
        if materialize:
            instant = now or datetime.now(UTC)
            for state in states:
                await _materialize_state(session, state, computed_at=instant)
            await session.flush()
        return EnrichmentStateSnapshot(
            target_object_id=target.object_id,
            target_object_type=target.object_type,
            target_object_key=target.canonical_key,
            world_revision=world_revision,
            dimensions=states,
        )


async def record_enrichment_attempt(
    session: AsyncSession,
    attempt: EnrichmentAttempt,
) -> None:
    existing = await session.get(EnrichmentAttemptModel, attempt.attempt_id)
    payload = attempt.model_dump(mode="json")
    if existing is not None:
        if _attempt_payload(existing) != payload:
            raise ValueError("enrichment attempt identity is immutable")
        return
    session.add(
        EnrichmentAttemptModel(
            attempt_id=attempt.attempt_id,
            target_object_id=attempt.target_object_id,
            requirement_id=attempt.requirement_id,
            dimension=attempt.dimension.value,
            operator_id=attempt.operator_id,
            task_run_id=attempt.task_run_id,
            execution_status=attempt.execution_status.value,
            semantic_outcome=(
                attempt.semantic_outcome.value if attempt.semantic_outcome is not None else None
            ),
            blocked_reason=attempt.blocked_reason,
            evidence_refs=list(attempt.evidence_refs),
            output_refs=list(attempt.output_refs),
            world_revision_before=attempt.world_revision_before,
            world_revision_after=attempt.world_revision_after,
            started_at=attempt.started_at,
            finished_at=attempt.finished_at,
        )
    )
    await session.flush()


def _term_applies_to_object(term: VocabularyTerm, object_type: str) -> bool:
    if term.name == "external-identifier":
        return True
    return object_type in term.subject_types or object_type in term.target_types


def _evaluate_requirement(
    requirement: EnrichmentDimensionSpec,
    *,
    target: ObjectModel,
    world_revision: int,
    claims: list[ClaimModel],
    outgoing: list[RelationModel],
    incoming: list[RelationModel],
    identifiers: list[ExternalIdentifierModel],
    attempts: list[EnrichmentAttemptModel],
) -> EnrichmentDimensionState:
    term_names = set(requirement.canonical_terms)
    fact_refs: list[str] = []
    conflict_refs: list[str] = []
    explicit_unknown = False

    if requirement.dimension is EnrichmentDimension.IDENTITY and identifiers:
        fact_refs.extend(
            f"identifier:{item.external_identifier_id}"
            for item in sorted(identifiers, key=lambda x: x.external_identifier_id)
        )

    relevant_claims = [
        item
        for item in claims
        if item.predicate in term_names and item.qualifier.get("vocabulary_scope") == "canonical"
    ]
    fact_refs.extend(f"claim:{item.claim_id}" for item in relevant_claims)
    conflict_refs.extend(_claim_conflicts(relevant_claims))

    relevant_relations = [
        item
        for item in [*outgoing, *incoming]
        if item.relation_type in term_names
        and item.qualifier.get("vocabulary_scope") == "canonical"
        and _relation_matches_target(item, target.object_id)
    ]
    concrete_relations: list[RelationModel] = []
    for relation in relevant_relations:
        if relation.relation_type == "applicability-status":
            state = relation.qualifier.get("state")
            if state == ApplicabilityState.UNKNOWN.value:
                explicit_unknown = True
                continue
        concrete_relations.append(relation)
    fact_refs.extend(f"relation:{item.relation_id}" for item in concrete_relations)
    conflict_refs.extend(_relation_conflicts(relevant_relations))

    requirement_attempts = [
        item for item in attempts if item.requirement_id == requirement.requirement_id
    ]
    attempted_operator_refs = sorted({item.operator_id for item in requirement_attempts})
    blocked_attempt_refs = sorted(
        item.attempt_id
        for item in requirement_attempts
        if item.execution_status == EnrichmentAttemptStatus.BLOCKED.value
    )
    if any(
        item.execution_status == EnrichmentAttemptStatus.SUCCEEDED.value
        and item.semantic_outcome == EnrichmentSemanticOutcome.UNKNOWN.value
        for item in requirement_attempts
    ):
        explicit_unknown = True

    if conflict_refs:
        status = EnrichmentStatus.CONFLICT
    elif fact_refs:
        status = EnrichmentStatus.RESOLVED
    elif explicit_unknown:
        status = EnrichmentStatus.UNKNOWN
    else:
        status = EnrichmentStatus.MISSING

    return EnrichmentDimensionState(
        target_object_id=target.object_id,
        target_object_type=target.object_type,
        target_object_key=target.canonical_key,
        requirement_id=requirement.requirement_id,
        dimension=requirement.dimension,
        status=status,
        accepted_fact_refs=sorted(set(fact_refs)),
        conflict_refs=sorted(set(conflict_refs)),
        missing_prerequisites=(
            [] if status is not EnrichmentStatus.MISSING else ["canonical_fact"]
        ),
        attempted_operator_refs=attempted_operator_refs,
        blocked_attempt_refs=blocked_attempt_refs,
        world_revision=world_revision,
    )


def _claim_conflicts(claims: list[ClaimModel]) -> list[str]:
    by_predicate: dict[str, dict[str, list[str]]] = {}
    for claim in claims:
        value_key = json.dumps(
            claim.value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        by_predicate.setdefault(claim.predicate, {}).setdefault(value_key, []).append(
            claim.claim_id
        )
    conflicts: list[str] = []
    for values in by_predicate.values():
        if len(values) > 1:
            conflicts.extend(f"claim:{claim_id}" for ids in values.values() for claim_id in ids)
    return conflicts


def _relation_conflicts(relations: list[RelationModel]) -> list[str]:
    applicability: dict[str, dict[str, list[str]]] = {}
    for relation in relations:
        if relation.relation_type != "applicability-status":
            continue
        state = relation.qualifier.get("state")
        if not isinstance(state, str) or state == ApplicabilityState.UNKNOWN.value:
            continue
        applicability.setdefault(relation.target_object_id, {}).setdefault(state, []).append(
            relation.relation_id
        )
    conflicts: list[str] = []
    for states in applicability.values():
        if len(states) > 1:
            conflicts.extend(
                f"relation:{relation_id}" for ids in states.values() for relation_id in ids
            )
    return conflicts


def _relation_matches_target(relation: RelationModel, target_object_id: str) -> bool:
    return (
        relation.source_object_id == target_object_id
        or relation.target_object_id == target_object_id
    )


async def _materialize_state(
    session: AsyncSession,
    state: EnrichmentDimensionState,
    *,
    computed_at: datetime,
) -> None:
    state_id = str(
        uuid5(
            NAMESPACE_URL,
            f"secfusion:enrichment-state:{state.vocabulary_revision}:"
            f"{state.target_object_id}:{state.dimension.value}",
        )
    )
    model = await session.get(EnrichmentDimensionStateModel, state_id)
    if model is None:
        model = EnrichmentDimensionStateModel(
            state_id=state_id,
            target_object_id=state.target_object_id,
            vocabulary_revision=state.vocabulary_revision,
            requirement_id=state.requirement_id,
            dimension=state.dimension.value,
            status=state.status.value,
            accepted_fact_refs=list(state.accepted_fact_refs),
            conflict_refs=list(state.conflict_refs),
            missing_prerequisites=list(state.missing_prerequisites),
            attempted_operator_refs=list(state.attempted_operator_refs),
            blocked_attempt_refs=list(state.blocked_attempt_refs),
            world_revision=state.world_revision,
            computed_at=computed_at,
        )
        session.add(model)
        return
    model.requirement_id = state.requirement_id
    model.status = state.status.value
    model.accepted_fact_refs = list(state.accepted_fact_refs)
    model.conflict_refs = list(state.conflict_refs)
    model.missing_prerequisites = list(state.missing_prerequisites)
    model.attempted_operator_refs = list(state.attempted_operator_refs)
    model.blocked_attempt_refs = list(state.blocked_attempt_refs)
    model.world_revision = state.world_revision
    model.computed_at = computed_at


def _attempt_payload(model: EnrichmentAttemptModel) -> dict[str, object]:
    return {
        "attempt_id": model.attempt_id,
        "target_object_id": model.target_object_id,
        "requirement_id": model.requirement_id,
        "dimension": model.dimension,
        "operator_id": model.operator_id,
        "task_run_id": model.task_run_id,
        "execution_status": model.execution_status,
        "semantic_outcome": model.semantic_outcome,
        "blocked_reason": model.blocked_reason,
        "evidence_refs": model.evidence_refs,
        "output_refs": model.output_refs,
        "world_revision_before": model.world_revision_before,
        "world_revision_after": model.world_revision_after,
        "started_at": model.started_at.isoformat(),
        "finished_at": model.finished_at.isoformat() if model.finished_at is not None else None,
    }
