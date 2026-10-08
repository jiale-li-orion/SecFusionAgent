from datetime import UTC, datetime
from typing import Any, cast

import pytest

from apps.application.commands.ask_question import _citation_sources_for_state
from apps.application.queries.decision_sources import decision_citation_sources
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import EvidenceLinkModel
from packages.investigation.state.contracts import InvestigationState, InvestigationStateItem
from packages.reasoning.citation import CitationBinder


@pytest.mark.asyncio
async def test_citations_preserve_both_accepted_evidence_reference_formats() -> None:
    link = EvidenceLinkModel(
        evidence_link_id="real-id",
        observation_id="observation-id",
        target_kind="object",
        target_id="object-id",
        locator={"page": 2},
        locator_hash="a" * 64,
    )
    observation = ObservationModel(
        observation_id="observation-id",
        source_id="paper-source",
        external_object_id="paper-id",
        external_revision="v2",
    )

    class Session:
        async def get(self, model, identity):
            if model is EvidenceLinkModel and identity == "real-id":
                return link
            if model is ObservationModel and identity == "observation-id":
                return observation
            return None

    refs = ["real-id", "evidence:real-id", "missing-id"]
    state = InvestigationState(
        case_id="case",
        case_revision=1,
        goal="Read the paper",
        updated_at=datetime.now(UTC),
        confirmed=[
            InvestigationStateItem(
                proposition="Source statement",
                evidence_refs=refs,
                writer="InvestigationRole",
                reason_code="supported",
                updated_revision=1,
            )
        ],
    )
    sources = await decision_citation_sources(cast(Any, Session()), state)
    assert {item.evidence_ref for item in sources} == {"real-id", "evidence:real-id"}
    bound = CitationBinder().bind([["real-id", "evidence:real-id"]], sources)
    assert all(item.source_ref == "source:paper-source:paper-id@v2" for item in bound)
    assert all(item.locator == {"page": 2} for item in bound)
    question_sources = await _citation_sources_for_state(cast(Any, Session()), state)
    assert {item.evidence_ref for item in question_sources} == {"evidence:real-id"}
    with pytest.raises(ValueError, match="citation source missing"):
        CitationBinder().bind([["missing-id"]], sources)
