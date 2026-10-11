from datetime import UTC, datetime

from packages.intelligence.knowledge.network_incident import get_incident_network
from packages.intelligence.knowledge.tests.test_network import session  # noqa: F401
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.incident_models import (
    IncidentRevisionModel,
    IncidentSourceLinkModel,
    IncidentTimelineEventModel,
    SecurityIncidentModel,
)
from packages.intelligence.storage.knowledge_models import ClaimModel


async def test_incident_associations_use_incident_history_and_real_refs(session):  # noqa: F811
    now = datetime(2026, 10, 1, tzinfo=UTC)
    for revision in [10, 11]:
        session.add(IncidentRevisionModel(revision=revision, committed_at=now))
    session.add(
        SecurityIncidentModel(
            incident_id="incident",
            candidate_id="candidate",
            incident_type="attack",
            lifecycle="active",
            promotion_reason="verified",
            current_summary="Actual incident",
            created_revision=10,
            current_revision=11,
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        ObservationModel(
            observation_id="obs",
            source_id="fixture",
            external_object_id="advisory",
            canonical_url="https://example.invalid/advisory",
            observed_at=now,
            content_hash="hash",
            idempotency_key="obs",
            created_at=now,
        )
    )
    session.add(
        ClaimModel(
            claim_id="claim",
            subject_id="root",
            predicate="description",
            value="Confirmed",
            qualifier={},
            origin="source_asserted",
            lifecycle="accepted",
            created_revision=1,
        )
    )
    session.add(
        IncidentSourceLinkModel(
            source_link_id="source-link",
            incident_id="incident",
            observation_id="obs",
            source_id="fixture",
            source_family="vendor",
            independence_key="vendor",
            source_role="primary",
            created_revision=10,
        )
    )
    session.add(
        IncidentTimelineEventModel(
            event_id="event",
            incident_id="incident",
            signal_id="signal",
            event_time=now,
            observed_at=now,
            event_type="report",
            summary="Actual event",
            source_role="primary",
            claim_refs=["claim"],
            evidence_refs=["obs"],
            created_revision=11,
        )
    )
    await session.commit()
    result = await get_incident_network(session, "incident")
    assert result.revision_domain == "incident"
    assert result.snapshot_revision == 11
    assert {node.object_type for node in result.nodes} == {"Incident", "IncidentEvent", "Evidence"}
    expanded = await get_incident_network(
        session,
        "incident",
        focus_id="event:event",
        existing_ids=[node.object_id for node in result.nodes],
    )
    claim = next(node for node in expanded.nodes if node.object_type == "Claim")
    assert claim.canonical_object_id == "root"
    assert claim.created_revision == 11
    evidence = next(node for node in expanded.nodes if node.object_type == "Evidence")
    assert evidence.evidence_ref == "observation:obs"
    assert all(edge.origin == "incident_record" for edge in expanded.edges)
    assert {edge.relation_type for edge in expanded.edges} == {
        "has_event",
        "has_source_evidence",
        "references_evidence",
        "references_claim",
    }
    historical = await get_incident_network(session, "incident", revision=10)
    assert {node.object_type for node in historical.nodes} == {"Incident", "Evidence"}
    assert historical.nodes[1].created_revision == 10
    first = await get_incident_network(session, "incident", limit=2)
    assert len(first.nodes) == 2
    assert first.remaining_count == 1
    second = await get_incident_network(
        session,
        "incident",
        limit=2,
        cursor=first.next_cursor,
        existing_ids=[node.object_id for node in first.nodes],
    )
    assert second.next_cursor is None
    assert len(second.nodes) == 3
    assert any(edge.relation_type == "references_evidence" for edge in second.edges)

    incident = await session.get(SecurityIncidentModel, "incident")
    incident.current_revision = 12
    session.add(IncidentRevisionModel(revision=12, committed_at=now))
    session.add(
        IncidentTimelineEventModel(
            event_id="correction",
            incident_id="incident",
            signal_id="correction",
            event_time=now,
            observed_at=now,
            event_type="correction",
            summary="Corrected",
            source_role="primary",
            claim_refs=[],
            evidence_refs=["obs"],
            created_revision=12,
            supersedes_event_id="event",
        )
    )
    await session.commit()
    corrected = await get_incident_network(session, "incident")
    old_edge = next(edge for edge in corrected.edges if edge.relation_id == "incident-event:event")
    assert old_edge.superseded_revision == 12
    assert old_edge.superseded_at is not None
    assert all(edge.created_revision >= 10 for edge in corrected.edges)


async def test_incident_expansion_enforces_total_node_cap(session):  # noqa: F811
    import pytest

    now = datetime(2026, 10, 1, tzinfo=UTC)
    session.add(IncidentRevisionModel(revision=10, committed_at=now))
    session.add(
        SecurityIncidentModel(
            incident_id="incident",
            candidate_id="candidate",
            incident_type="attack",
            lifecycle="active",
            promotion_reason="verified",
            current_summary="Actual incident",
            created_revision=10,
            current_revision=10,
            created_at=now,
            updated_at=now,
        )
    )
    for index in range(200):
        session.add(
            IncidentTimelineEventModel(
                event_id=f"event-{index:03}",
                incident_id="incident",
                signal_id=f"signal-{index}",
                event_time=now,
                observed_at=now,
                event_type="report",
                summary="Actual event",
                source_role="primary",
                claim_refs=[],
                evidence_refs=[],
                created_revision=10,
            )
        )
    await session.commit()
    existing = [f"event:event-{index:03}" for index in range(196)]
    result = await get_incident_network(session, "incident", existing_ids=existing)
    assert len(result.nodes) == 200
    assert result.remaining_count == 1
    assert result.next_cursor is None
    repeat = await get_incident_network(
        session, "incident", existing_ids=[node.object_id for node in result.nodes]
    )
    assert len(repeat.nodes) == 200
    assert repeat.remaining_count == 1
    assert repeat.next_cursor is None
    with pytest.raises(ValueError, match="200"):
        await get_incident_network(
            session, "incident", existing_ids=[f"event:event-{index:03}" for index in range(200)]
        )
