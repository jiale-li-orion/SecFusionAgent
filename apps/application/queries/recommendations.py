"""Explainable interest matching over current, evidence-backed canonical Knowledge."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import String, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from apps.application.intelligence_preferences import (
    RecommendationFeedbackModel,
    object_label,
    read_intelligence_preferences,
)
from apps.application.views.recommendations import (
    IntelligenceRecommendationsView,
    IntelligenceRecommendationView,
    RecommendationReasonView,
)
from packages.intelligence.knowledge.read import EvidenceRef
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    EvidenceLinkModel,
    ExternalIdentifierModel,
    KnowledgeRevisionModel,
    ObjectModel,
    RelationModel,
)

CANDIDATE_LIMIT = 128


def _pattern(value: str) -> str:
    return "%" + value.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"


async def read_intelligence_recommendations(
    session: AsyncSession,
    principal: str,
    *,
    limit: int = 6,
) -> IntelligenceRecommendationsView:
    preferences = await read_intelligence_preferences(session, principal)
    revision = int(await session.scalar(select(func.max(KnowledgeRevisionModel.revision))) or 0)
    response = IntelligenceRecommendationsView(
        generated_at=datetime.now(UTC),
        knowledge_revision=revision,
        preferences_updated_at=preferences.updated_at,
        candidate_limit=CANDIDATE_LIMIT,
    )
    feedback = {
        row.object_id: row.feedback
        for row in await session.scalars(
            select(RecommendationFeedbackModel).where(
                RecommendationFeedbackModel.principal == principal
            )
        )
    }
    interested = [object_id for object_id, value in feedback.items() if value == "interested"]
    ignored = [object_id for object_id, value in feedback.items() if value == "ignored"]
    targets = preferences.target_object_ids
    if not preferences.keywords and not targets and not interested:
        return response

    related_rows = (
        list(
            await session.scalars(
                select(RelationModel).where(
                    RelationModel.lifecycle == "accepted",
                    RelationModel.superseded_revision.is_(None),
                    or_(
                        RelationModel.source_object_id.in_(targets),
                        RelationModel.target_object_id.in_(targets),
                    ),
                )
            )
        )
        if targets
        else []
    )
    related_ids = {
        endpoint
        for row in related_rows
        for endpoint in (row.source_object_id, row.target_object_id)
    }
    matches: list[ColumnElement[bool]] = [
        ObjectModel.object_id.in_(targets + interested + sorted(related_ids))
    ]
    for keyword in preferences.keywords:
        pattern = _pattern(keyword)
        matches.append(
            or_(
                ObjectModel.canonical_key.ilike(pattern, escape="!"),
                cast(ObjectModel.properties, String).ilike(pattern, escape="!"),
                select(ExternalIdentifierModel.object_id)
                .where(
                    ExternalIdentifierModel.object_id == ObjectModel.object_id,
                    ExternalIdentifierModel.value.ilike(pattern, escape="!"),
                )
                .exists(),
                select(ClaimModel.claim_id)
                .where(
                    ClaimModel.subject_id == ObjectModel.object_id,
                    ClaimModel.lifecycle == "accepted",
                    ClaimModel.superseded_revision.is_(None),
                    cast(ClaimModel.value, String).ilike(pattern, escape="!"),
                )
                .exists(),
            )
        )
    objects = list(
        await session.scalars(
            select(ObjectModel)
            .where(
                ObjectModel.superseded_revision.is_(None),
                ObjectModel.object_id.not_in(ignored),
                or_(*matches),
            )
            .order_by(
                case(
                    (ObjectModel.object_id.in_(targets), 0),
                    (ObjectModel.object_id.in_(interested), 1),
                    (ObjectModel.object_id.in_(related_ids), 2),
                    else_=3,
                ),
                ObjectModel.created_revision.desc(),
                ObjectModel.object_id,
            )
            .limit(CANDIDATE_LIMIT)
        )
    )
    ids = [obj.object_id for obj in objects]
    if not ids:
        return response

    claims = list(
        await session.scalars(
            select(ClaimModel).where(
                ClaimModel.subject_id.in_(ids),
                ClaimModel.lifecycle == "accepted",
                ClaimModel.superseded_revision.is_(None),
            )
        )
    )
    # Relation matches are meaningful only with their own accepted Evidence links.
    links = (
        await session.execute(
            select(EvidenceLinkModel, ObservationModel)
            .join(
                ObservationModel,
                ObservationModel.observation_id == EvidenceLinkModel.observation_id,
            )
            .where(
                or_(
                    (EvidenceLinkModel.target_kind == "claim")
                    & EvidenceLinkModel.target_id.in_([row.claim_id for row in claims]),
                    (EvidenceLinkModel.target_kind == "relation")
                    & EvidenceLinkModel.target_id.in_([row.relation_id for row in related_rows]),
                )
            )
            .order_by(EvidenceLinkModel.evidence_link_id)
        )
    ).all()
    evidence_by_fact: dict[str, list[EvidenceRef]] = defaultdict(list)
    for link, observation in links:
        evidence_by_fact[link.target_id].append(
            EvidenceRef(
                evidence_ref=f"evidence:{link.evidence_link_id}",
                source_id=observation.source_id,
                observation_id=observation.observation_id,
                artifact_id=link.artifact_id,
                external_object_id=observation.external_object_id,
                external_revision=observation.external_revision,
                published_at=observation.published_at,
                updated_at=observation.updated_at,
                observed_at=observation.observed_at,
                canonical_url=observation.canonical_url,
                locator=link.locator,
            )
        )
    claims_by_object: dict[str, list[ClaimModel]] = defaultdict(list)
    evidence_by_object: dict[str, dict[str, EvidenceRef]] = defaultdict(dict)
    for claim in claims:
        if evidence_by_fact[claim.claim_id]:
            claims_by_object[claim.subject_id].append(claim)
            for item in evidence_by_fact[claim.claim_id]:
                evidence_by_object[claim.subject_id][item.evidence_ref] = item
    relations_by_object: dict[str, list[RelationModel]] = defaultdict(list)
    for relation in related_rows:
        if evidence_by_fact[relation.relation_id]:
            for object_id in (relation.source_object_id, relation.target_object_id):
                relations_by_object[object_id].append(relation)
                for item in evidence_by_fact[relation.relation_id]:
                    evidence_by_object[object_id][item.evidence_ref] = item
    identifiers: dict[str, list[str]] = defaultdict(list)
    for row in await session.scalars(
        select(ExternalIdentifierModel).where(ExternalIdentifierModel.object_id.in_(ids))
    ):
        identifiers[row.object_id].append(row.value)
    target_labels = {obj.object_id: obj.label for obj in preferences.target_objects}

    for obj in objects:
        evidence = evidence_by_object[obj.object_id]
        if not evidence:
            # Object identity alone cannot supply an evidence-backed recommendation.
            continue
        refs = sorted(evidence)[:1]
        reasons: list[RecommendationReasonView] = []
        if obj.object_id in targets:
            reasons.append(
                RecommendationReasonView(
                    kind="followed_object",
                    value=obj.object_id,
                    label="你关注的知识对象",
                    weight=100,
                    evidence_refs=refs,
                )
            )
        related_targets: set[str] = set()
        for relation in relations_by_object[obj.object_id]:
            other = (
                relation.target_object_id
                if relation.source_object_id == obj.object_id
                else relation.source_object_id
            )
            if other in targets and other not in related_targets:
                related_targets.add(other)
                reasons.append(
                    RecommendationReasonView(
                        kind="related_object",
                        value=other,
                        label=(
                            f"与关注对象 {target_labels.get(other, other)} "
                            f"存在已留证关系 {relation.relation_type}"
                        ),
                        weight=40,
                        relation_id=relation.relation_id,
                        evidence_refs=[evidence_by_fact[relation.relation_id][0].evidence_ref],
                    )
                )
        text = " ".join(
            [
                obj.canonical_key,
                json.dumps(obj.properties, ensure_ascii=False),
                *identifiers[obj.object_id],
                *(
                    json.dumps(claim.value, ensure_ascii=False)
                    for claim in claims_by_object[obj.object_id]
                ),
            ]
        ).casefold()
        for keyword in preferences.keywords:
            if keyword.casefold() in text:
                reasons.append(
                    RecommendationReasonView(
                        kind="keyword",
                        value=keyword,
                        label=f"知识条目匹配关注关键词: {keyword}",
                        weight=10,
                        evidence_refs=refs,
                    )
                )
        if feedback.get(obj.object_id) == "interested":
            reasons.append(
                RecommendationReasonView(
                    kind="interested",
                    value=obj.object_id,
                    label="你此前标记了感兴趣",
                    weight=20,
                    evidence_refs=refs,
                )
            )
        if not reasons:
            continue
        # Every returned reason has its referenced Evidence included in the response.
        selected_refs = {ref for reason in reasons for ref in reason.evidence_refs}
        selected_refs.update(sorted(evidence)[:6])
        response.items.append(
            IntelligenceRecommendationView(
                object_id=obj.object_id,
                object_type=obj.object_type,
                canonical_key=obj.canonical_key,
                label=object_label(obj),
                score=sum(reason.weight for reason in reasons),
                feedback="interested" if feedback.get(obj.object_id) == "interested" else None,
                reasons=reasons,
                evidence=[evidence[ref] for ref in sorted(selected_refs)],
                created_revision=obj.created_revision,
            )
        )
    response.items.sort(key=lambda item: (-item.score, -item.created_revision, item.object_id))
    response.items = response.items[:limit]
    return response
