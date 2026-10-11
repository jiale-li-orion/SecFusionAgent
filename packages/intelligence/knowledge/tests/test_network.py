from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.intelligence.knowledge.network import get_object_network
from packages.intelligence.storage.knowledge_models import (
    KnowledgeRevisionModel,
    ObjectModel,
    RelationModel,
)
from packages.shared.db import Base


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        for revision in range(1, 5):
            session.add(
                KnowledgeRevisionModel(
                    revision=revision, committed_at=datetime(2026, 10, revision, tzinfo=UTC)
                )
            )
        for object_id, revision in [("root", 1), ("a", 1), ("b", 2), ("c", 3), ("future", 4)]:
            session.add(
                ObjectModel(
                    object_id=object_id,
                    object_type="document",
                    canonical_key=object_id,
                    properties={"title": object_id},
                    created_revision=revision,
                )
            )
        for relation_id, source, target, created, superseded in [
            ("inbound", "a", "root", 1, None),
            ("outbound", "root", "b", 2, None),
            ("cross", "a", "b", 2, None),
            ("old", "root", "a", 1, 3),
            ("expand", "b", "c", 3, None),
            ("future", "root", "future", 4, None),
        ]:
            session.add(
                RelationModel(
                    relation_id=relation_id,
                    source_object_id=source,
                    target_object_id=target,
                    relation_type="references",
                    qualifier={},
                    origin="source_asserted",
                    lifecycle="accepted",
                    created_revision=created,
                    superseded_revision=superseded,
                )
            )
        await session.commit()
        yield session
    await engine.dispose()


async def test_bidirectional_induced_history_and_snapshot(session):
    result = await get_object_network(session, "root", revision=3)
    assert result is not None
    assert {n.object_id for n in result.nodes} == {"root", "a", "b"}
    assert {e.relation_id for e in result.edges} == {"inbound", "outbound", "cross", "old"}
    old = next(e for e in result.edges if e.relation_id == "old")
    assert old.superseded_revision == 3
    assert old.superseded_at.day == 3
    assert old.created_at.day == 1
    assert result.snapshot_revision == 3
    historical = await get_object_network(session, "root", revision=1)
    assert {n.object_id for n in historical.nodes} == {"root", "a"}
    assert {e.relation_id for e in historical.edges} == {"inbound", "old"}
    assert await get_object_network(session, "future", revision=3) is None


async def test_cursor_and_expansion_preserve_center_and_cross_edges(session):
    first = await get_object_network(session, "root", limit=2, revision=3)
    assert [n.object_id for n in first.nodes] == ["root", "b"]
    assert first.remaining_count == 1
    assert first.next_cursor
    second = await get_object_network(
        session, "root", limit=2, cursor=first.next_cursor, existing_ids=["b"]
    )
    assert second.snapshot_revision == 3
    assert {n.object_id for n in second.nodes} == {"root", "a", "b"}
    assert "cross" in {e.relation_id for e in second.edges}
    assert second.next_cursor is None
    expanded = await get_object_network(
        session, "root", focus_id="b", existing_ids=["a", "b"], revision=3
    )
    assert expanded.center_id == "root"
    assert {n.object_id for n in expanded.nodes} == {"root", "a", "b", "c"}
    assert "expand" in {e.relation_id for e in expanded.edges}
    with pytest.raises(ValueError):
        await get_object_network(session, "root", focus_id="a", cursor=first.next_cursor)


async def test_evidence_count_precedes_newness_and_evidence_is_preserved(session):
    from packages.intelligence.storage.evidence_models import ObservationModel
    from packages.intelligence.storage.knowledge_models import EvidenceLinkModel

    now = datetime(2026, 10, 1, tzinfo=UTC)
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
        EvidenceLinkModel(
            evidence_link_id="ev",
            target_kind="relation",
            target_id="inbound",
            observation_id="obs",
            locator={"section": "references"},
            locator_hash="hash",
        )
    )
    await session.commit()
    result = await get_object_network(session, "root", limit=2, revision=3)
    assert [node.object_id for node in result.nodes] == ["root", "a"]
    edge = next(edge for edge in result.edges if edge.relation_id == "inbound")
    assert edge.evidence[0].evidence_ref == "evidence:ev"
    assert edge.evidence[0].canonical_url == "https://example.invalid/advisory"
    assert edge.evidence[0].locator == {"section": "references"}
    assert result.remaining_count == 1
    second = await get_object_network(
        session, "root", limit=2, cursor=result.next_cursor, existing_ids=["a"]
    )
    assert {node.object_id for node in second.nodes} == {"root", "a", "b"}
    assert second.remaining_count == 0


@pytest.mark.parametrize("cursor", ["bad", "bnVsbA==", "W10=", "e30="])
async def test_invalid_cursors_are_client_errors(session, cursor):
    with pytest.raises(ValueError, match="invalid network cursor"):
        await get_object_network(session, "root", cursor=cursor)


async def test_default_page_cap_and_nonaccepted_edges(session):
    for index in range(45):
        object_id = f"neighbor-{index:02}"
        session.add(
            ObjectModel(
                object_id=object_id,
                object_type="document",
                canonical_key=object_id,
                properties={},
                created_revision=1,
            )
        )
        session.add(
            RelationModel(
                relation_id=f"relation-{index:02}",
                source_object_id="root",
                target_object_id=object_id,
                relation_type="references",
                qualifier={},
                origin="source_asserted",
                lifecycle="accepted",
                created_revision=1,
            )
        )
    session.add(
        RelationModel(
            relation_id="candidate",
            source_object_id="root",
            target_object_id="c",
            relation_type="references",
            qualifier={},
            origin="semantic_derived",
            lifecycle="proposed",
            created_revision=3,
        )
    )
    await session.commit()
    result = await get_object_network(session, "root")
    assert len(result.nodes) == 40
    assert result.remaining_count == 9
    assert "candidate" not in {edge.relation_id for edge in result.edges}
    assert "c" not in {node.object_id for node in result.nodes}


async def test_expansion_enforces_total_node_cap_and_readable_identity_labels(session):
    existing = []
    for index in range(196):
        object_id = f"loaded-{index:03}"
        existing.append(object_id)
        session.add(
            ObjectModel(
                object_id=object_id,
                object_type="Repo",
                canonical_key=object_id,
                properties={"full_name": f"owner/repo-{index}"},
                created_revision=1,
            )
        )
    for index in range(40):
        object_id = f"next-{index:02}"
        session.add(
            ObjectModel(
                object_id=object_id,
                object_type="Document",
                canonical_key=object_id,
                properties={"display_name": f"Article {index}"},
                created_revision=1,
            )
        )
        session.add(
            RelationModel(
                relation_id=f"new-{index:02}",
                source_object_id="root",
                target_object_id=object_id,
                relation_type="references",
                qualifier={},
                origin="source_asserted",
                lifecycle="accepted",
                created_revision=1,
            )
        )
    await session.commit()
    result = await get_object_network(session, "root", existing_ids=existing)
    assert len(result.nodes) == 200
    assert result.remaining_count == 40
    assert result.next_cursor is None
    assert next(n for n in result.nodes if n.object_id == existing[0]).label == "owner/repo-0"
    full = [node.object_id for node in result.nodes]
    repeat = await get_object_network(session, "root", existing_ids=full)
    assert len(repeat.nodes) == 200
    assert repeat.remaining_count == 40
    assert repeat.next_cursor is None
    with pytest.raises(ValueError, match="200"):
        await get_object_network(session, "root", existing_ids=[*existing, "a", "b", "c", "future"])
    labels = await get_object_network(session, "next-00")
    assert labels.nodes[0].label == "Article 0"
