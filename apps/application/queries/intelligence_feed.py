"""Compose durable Knowledge, previews and principal preferences into activity pages."""

from __future__ import annotations

import base64
import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.application.intelligence_preferences import (
    RecommendationFeedbackModel,
    object_label,
    read_intelligence_preferences,
)
from apps.application.queries.recommendation_previews import (
    PreviewText,
    canonical_preview,
    retained_previews,
)
from apps.application.views.recommendations import (
    FollowedObjectView,
    FollowResolutionView,
    IntelligenceActivityView,
    IntelligenceFeedView,
    RecommendationReasonView,
)
from packages.intelligence.feed import (
    ACTIVITY_TYPES,
    SECURITY_RELATIONS,
    TEXT_FIELDS,
    activity_identity,
    activity_kind,
    is_landing_document,
    rank_key,
    topic_matches,
)
from packages.intelligence.knowledge.read import EvidenceRef
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.feed_models import ActivityFeedbackModel
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    EvidenceLinkModel,
    ExternalIdentifierModel,
    KnowledgeRevisionModel,
    ObjectModel,
    RelationModel,
)


async def resolve_follow(session: AsyncSession, query: str) -> FollowResolutionView:
    objects = list(
        await session.scalars(select(ObjectModel).where(ObjectModel.superseded_revision.is_(None)))
    )
    identifiers: dict[str, list[str]] = defaultdict(list)
    for identifier in await session.scalars(select(ExternalIdentifierModel)):
        identifiers[identifier.object_id].append(identifier.value)
    normalized = query.strip().casefold().removeprefix("https://github.com/").rstrip("/")
    exact, candidates = [], []
    for obj in objects:
        names = [
            obj.canonical_key,
            obj.canonical_key.removeprefix("github:"),
            *identifiers[obj.object_id],
        ]
        names += [
            str(obj.properties[key])
            for key in ("name", "display_name", "title", "full_name")
            if isinstance(obj.properties.get(key), str)
        ]
        names = [name.casefold().strip() for name in names]
        item = FollowedObjectView(
            object_id=obj.object_id,
            object_type=obj.object_type,
            canonical_key=obj.canonical_key,
            label=object_label(obj),
        )
        if normalized in names:
            exact.append(item)
        elif any(normalized in name for name in names):
            candidates.append(item)
    exact.sort(key=lambda item: (item.label, item.object_id))
    candidates.sort(key=lambda item: (item.label, item.object_id))
    return FollowResolutionView(
        query=query,
        exact_match=exact[0] if len(exact) == 1 else None,
        candidates=(exact + candidates)[:20],
    )


async def read_intelligence_feed(
    session: AsyncSession,
    principal: str,
    *,
    mode: Literal["following", "recommended"] = "recommended",
    window: Literal["30d", "all"] = "30d",
    limit: int = 12,
    cursor: str | None = None,
) -> IntelligenceFeedView:
    now = datetime.now(UTC)
    revision = int(await session.scalar(select(func.max(KnowledgeRevisionModel.revision))) or 0)
    anchor = now
    after = None
    if cursor:
        try:
            decoded = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
            if decoded["mode"] != mode or decoded["window"] != window:
                raise ValueError("cursor belongs to a different feed")
            anchor = datetime.fromisoformat(decoded["anchor"])
            revision = int(decoded["revision"])
            after = tuple(decoded["after"])
            if anchor.tzinfo is None or len(after) != 5:
                raise ValueError("invalid feed cursor")
        except (ValueError, KeyError, TypeError, UnicodeDecodeError) as exc:
            raise ValueError("invalid feed cursor") from exc
    preferences = await read_intelligence_preferences(session, principal)
    response = IntelligenceFeedView(
        generated_at=now, knowledge_revision=revision, mode=mode, window=window
    )
    targets = set(preferences.target_object_ids)
    labels = {item.object_id: item.label for item in preferences.target_objects}
    objects = list(
        await session.scalars(
            select(ObjectModel).where(
                ObjectModel.superseded_revision.is_(None), ObjectModel.created_revision <= revision
            )
        )
    )
    object_types = {obj.object_id: obj.object_type for obj in objects}
    canonical_keys = {obj.object_id: obj.canonical_key for obj in objects}
    objects = [obj for obj in objects if obj.object_type in ACTIVITY_TYPES]
    ids = [obj.object_id for obj in objects]
    if not ids:
        return response
    claims = list(
        await session.scalars(
            select(ClaimModel).where(
                ClaimModel.subject_id.in_(ids),
                ClaimModel.lifecycle == "accepted",
                ClaimModel.superseded_revision.is_(None),
                ClaimModel.created_revision <= revision,
            )
        )
    )
    relations = list(
        await session.scalars(
            select(RelationModel).where(
                RelationModel.lifecycle == "accepted",
                RelationModel.superseded_revision.is_(None),
                RelationModel.created_revision <= revision,
            )
        )
    )
    fact_ids = [row.claim_id for row in claims] + [row.relation_id for row in relations]
    links = (
        await session.execute(
            select(EvidenceLinkModel, ObservationModel)
            .join(
                ObservationModel,
                ObservationModel.observation_id == EvidenceLinkModel.observation_id,
            )
            .where(
                EvidenceLinkModel.target_id.in_(fact_ids), ObservationModel.observed_at <= anchor
            )
            .order_by(ObservationModel.observed_at, EvidenceLinkModel.evidence_link_id)
        )
    ).all()
    by_fact: dict[str, list[EvidenceRef]] = defaultdict(list)
    for link, obs in links:
        by_fact[link.target_id].append(
            EvidenceRef(
                evidence_ref=f"evidence:{link.evidence_link_id}",
                source_id=obs.source_id,
                observation_id=obs.observation_id,
                artifact_id=link.artifact_id,
                external_object_id=obs.external_object_id,
                external_revision=obs.external_revision,
                published_at=obs.published_at,
                updated_at=obs.updated_at,
                observed_at=obs.observed_at,
                canonical_url=obs.canonical_url,
                locator=link.locator,
            )
        )
    by_object: dict[str, list[ClaimModel]] = defaultdict(list)
    object_relations: dict[str, list[RelationModel]] = defaultdict(list)
    evidence: dict[str, dict[str, EvidenceRef]] = defaultdict(dict)
    owned_evidence: dict[str, dict[str, EvidenceRef]] = defaultdict(dict)
    for claim in claims:
        if by_fact[claim.claim_id]:
            by_object[claim.subject_id].append(claim)
            owned_evidence[claim.subject_id].update(
                {ref.evidence_ref: ref for ref in by_fact[claim.claim_id]}
            )
            evidence[claim.subject_id].update(
                {ref.evidence_ref: ref for ref in by_fact[claim.claim_id]}
            )
    for relation in relations:
        if by_fact[relation.relation_id]:
            for object_id in (relation.source_object_id, relation.target_object_id):
                object_relations[object_id].append(relation)
                evidence[object_id].update(
                    {ref.evidence_ref: ref for ref in by_fact[relation.relation_id]}
                )
    source_urls: dict[str, list[str]] = {}
    for obj in objects:
        identity_urls = [
            value
            for key, value in obj.properties.items()
            if key in {"url", "canonical_url", "html_url"} and isinstance(value, str)
        ]
        source_urls[obj.object_id] = identity_urls or [
            ref.canonical_url for ref in owned_evidence[obj.object_id].values() if ref.canonical_url
        ]
    preview_candidates: list[EvidenceRef] = []
    for obj in objects:
        if obj.object_type not in {"Document", "ResearchWork", "NormativeDocument", "Release"}:
            continue
        own_refs = owned_evidence[obj.object_id]
        if obj.object_type == "Document" and is_landing_document(source_urls[obj.object_id]):
            continue
        if all(
            canonical_preview(obj, by_object[obj.object_id], by_fact, title=is_title).text
            for is_title in (True, False)
        ):
            continue
        preview_candidates.extend(own_refs.values())
    excerpts = await retained_previews(
        session, list({ref.evidence_ref: ref for ref in preview_candidates}.values())
    )
    feedback = {
        row.activity_id: row.feedback
        for row in await session.scalars(
            select(ActivityFeedbackModel).where(ActivityFeedbackModel.principal == principal)
        )
    }
    legacy_ignored = set(
        await session.scalars(
            select(RecommendationFeedbackModel.object_id).where(
                RecommendationFeedbackModel.principal == principal,
                RecommendationFeedbackModel.feedback == "ignored",
            )
        )
    )

    def item_rank(item: IntelligenceActivityView) -> tuple[int, int, int, float, str]:
        return rank_key(
            mode,
            item.activity_kind,
            bool(item.reasons),
            item.score,
            item.activity_at,
            item.activity_id,
        )

    dedup: dict[str, IntelligenceActivityView] = {}
    for obj in objects:
        refs = evidence[obj.object_id]
        if not refs or obj.object_id in legacy_ignored:
            continue
        title = canonical_preview(obj, by_object[obj.object_id], by_fact, title=True)
        summary = canonical_preview(obj, by_object[obj.object_id], by_fact, title=False)
        if not title.text:
            for claim in by_object[obj.object_id]:
                if (
                    claim.predicate
                    in {"github_title", "github_release_name", "github_commit_message"}
                    and isinstance(claim.value, str)
                    and claim.value.strip()
                ):
                    title = PreviewText(
                        claim.value.strip()[:180],
                        "accepted_claim",
                        by_fact[claim.claim_id][0].evidence_ref,
                    )
                    break
        for ref in owned_evidence[obj.object_id]:
            if ref in excerpts:
                if not title.text:
                    title = excerpts[ref][0]
                if not summary.text:
                    summary = excerpts[ref][1]
        text_sources: list[tuple[str, list[str]]] = [
            (value, [])
            for key, value in obj.properties.items()
            if key in TEXT_FIELDS and isinstance(value, str)
        ]
        text_sources += [
            (row.value, [by_fact[row.claim_id][0].evidence_ref])
            for row in by_object[obj.object_id]
            if row.predicate in TEXT_FIELDS and isinstance(row.value, str)
        ]
        text_sources += [
            (preview.text, [preview.evidence_ref] if preview.evidence_ref else [])
            for preview in (title, summary)
            if preview.text
        ]
        text = " ".join(value for value, _refs in text_sources)
        kind = activity_kind(
            obj.object_type,
            text,
            [
                row.relation_type
                for row in object_relations[obj.object_id]
                if obj.object_type not in {"PullRequest", "Commit", "Issue"}
                or object_types.get(
                    row.target_object_id
                    if row.source_object_id == obj.object_id
                    else row.source_object_id
                )
                in {"Vulnerability", "SecurityIncident", "Incident", "ExploitArtifact"}
            ],
            source_urls=source_urls[obj.object_id],
            identity=obj.canonical_key,
            title=title.text or "",
        )
        if not kind:
            continue
        reasons = []
        for relation in object_relations[obj.object_id]:
            other = (
                relation.target_object_id
                if relation.source_object_id == obj.object_id
                else relation.source_object_id
            )
            if other in targets:
                reasons.append(
                    RecommendationReasonView(
                        kind="related_object",
                        value=other,
                        label=(
                            f"与关注对象 {labels.get(other, other)} "
                            f"存在已留证关系 {relation.relation_type}"
                        ),
                        weight=40,
                        relation_id=relation.relation_id,
                        evidence_refs=[by_fact[relation.relation_id][0].evidence_ref],
                    )
                )
        first_ref = next(iter(owned_evidence[obj.object_id]), next(iter(refs)))
        if obj.object_id in targets:
            reasons.append(
                RecommendationReasonView(
                    kind="followed_object",
                    value=obj.object_id,
                    label="你关注的内容有动态",
                    weight=10,
                    evidence_refs=[first_ref],
                )
            )
        for keyword in topic_matches(text, preferences.keywords):
            reasons.append(
                RecommendationReasonView(
                    kind="keyword",
                    value=keyword,
                    label=f"标题或正文匹配主题 {keyword}",
                    weight=10,
                    evidence_refs=sorted(
                        {
                            ref
                            for value, content_refs in text_sources
                            if topic_matches(value, [keyword])
                            for ref in content_refs
                        }
                    ),
                )
            )
        matched = bool(reasons)
        if mode == "following" and not matched:
            continue
        material_relations = [
            row
            for row in object_relations[obj.object_id]
            if row.relation_type in SECURITY_RELATIONS
        ]
        # Full meaningful content detects changes beyond the displayed excerpt.
        # Normalize relation counterparts to canonical identity; source UUIDs and
        # ingestion revisions must not split the same syndicated activity.
        material_change = "\n".join(
            sorted({" ".join(value.split()) for value, _refs in text_sources})
        )
        relation_content = set()
        for row in material_relations:
            counterpart = (
                row.target_object_id
                if row.source_object_id == obj.object_id
                else row.source_object_id
            )
            relation_content.add(f"{row.relation_type}:{canonical_keys.get(counterpart, '')}")
        material_change += "|" + "|".join(sorted(relation_content))
        activity_id = activity_identity(
            obj.object_id, title.text or obj.canonical_key, summary.text or "", material_change
        )
        if feedback.get(activity_id) == "ignored":
            continue
        timestamp_ref = summary.evidence_ref or title.evidence_ref or first_ref
        timestamp = refs[timestamp_ref]
        # First evidence of each current meaningful fact avoids refreshing on a
        # repeated collection/link of unchanged content. Relation proof may date a
        # new fix but never supplies another object's title or body.
        activity_refs = [
            by_fact[row.claim_id][0]
            for row in by_object[obj.object_id]
            if row.predicate in TEXT_FIELDS
        ]
        activity_refs += [by_fact[row.relation_id][0] for row in material_relations]
        if not activity_refs:
            activity_refs = [timestamp]

        def event_time(ref: EvidenceRef) -> datetime:
            value = ref.updated_at or ref.published_at or ref.observed_at
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value

        activity_source = max(activity_refs, key=event_time)
        at = event_time(activity_source)
        if at > anchor or (window == "30d" and at < anchor - timedelta(days=30)):
            continue
        score = sum(reason.weight for reason in reasons) + (
            20 if feedback.get(activity_id) == "interested" else 0
        )
        item = IntelligenceActivityView(
            activity_id=activity_id,
            activity_kind=kind,
            activity_at=at,
            activity_evidence_ref=activity_source.evidence_ref,
            object_id=obj.object_id,
            object_type=obj.object_type,
            canonical_key=obj.canonical_key,
            label=object_label(obj),
            score=score,
            feedback="interested" if feedback.get(activity_id) == "interested" else None,
            reasons=reasons,
            evidence=list(refs.values()),
            created_revision=obj.created_revision,
            title=title.text,
            summary=summary.text,
            title_origin=title.origin,
            title_evidence_refs=[title.evidence_ref] if title.evidence_ref else [],
            preview_origin=summary.origin,
            preview_evidence_refs=[summary.evidence_ref] if summary.evidence_ref else [],
            preview_chunk_ref=summary.chunk_ref,
            evidence_count=len(refs),
            source_count=len({ref.source_id for ref in refs.values()}),
            published_at=timestamp.published_at,
            observed_at=timestamp.observed_at,
            timestamp_evidence_ref=timestamp_ref,
        )
        # Choose the strongest representative before ranking the deduplicated
        # stream. In particular, a directly followed copy must not lose its
        # relevance to an earlier unpersonalized copy of the same content.
        if activity_id in dedup:
            previous = dedup[activity_id]
            merged_evidence = list(
                {ref.evidence_ref: ref for ref in previous.evidence + item.evidence}.values()
            )
            if (item_rank(previous), previous.object_id) <= (item_rank(item), item.object_id):
                item = previous
            item.evidence = merged_evidence
            item.evidence_count = len(merged_evidence)
            item.source_count = len({ref.source_id for ref in merged_evidence})
        dedup[activity_id] = item
    ranked = [(item_rank(item), item) for item in dedup.values()]
    ranked.sort(key=lambda entry: entry[0])
    if after:
        try:
            ranked = [entry for entry in ranked if entry[0] > after]
        except TypeError as exc:
            raise ValueError("invalid feed cursor") from exc
    page = ranked[:limit]
    response.items = [entry[1] for entry in page]
    response.has_more = len(ranked) > limit
    if response.has_more and page:
        payload = {
            "mode": mode,
            "window": window,
            "anchor": anchor.isoformat(),
            "revision": revision,
            "after": page[-1][0],
        }
        response.next_cursor = (
            base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        )
    return response
