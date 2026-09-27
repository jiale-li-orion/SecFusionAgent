from __future__ import annotations

from datetime import UTC, datetime

import pytest

from packages.investigation.state.continuation import ContinuationRequest
from packages.investigation.state.contracts import InvestigationState
from packages.reasoning.citation import CitationSource
from packages.reasoning.decision import ConclusionType, DecisionConclusion, DecisionDraft
from packages.reasoning.model import (
    ContinuationProposal,
    DecisionPlannerResponse,
    FinalDecisionProposal,
    ModelDecisionPlanner,
)
from packages.shared.model_provider import StructuredModelRequest

NOW = datetime(2026, 9, 27, 19, 30, tzinfo=UTC)


class _Provider:
    name = "fixture-decision"
    version = "v1"

    def __init__(self, response: DecisionPlannerResponse) -> None:
        self.response = response
        self.requests: list[StructuredModelRequest] = []

    async def generate_structured(self, request, response_model):
        assert response_model is DecisionPlannerResponse
        self.requests.append(request)
        return self.response


def _state() -> InvestigationState:
    return InvestigationState(
        case_id="case-1",
        case_revision=7,
        goal="Decide the fix boundary.",
        targets=["vuln-1"],
        updated_at=NOW,
    )


@pytest.mark.asyncio
async def test_model_decision_planner_forces_case_identity_from_state() -> None:
    provider = _Provider(
        DecisionPlannerResponse(
            action=FinalDecisionProposal(
                conclusions=[],
                unknowns=["No confirmed fix evidence."],
                answer_payload={"status": "partial"},
                stop_reason="insufficient_evidence",
            )
        )
    )
    result = await ModelDecisionPlanner(provider).plan(_state(), citation_sources=[])
    assert isinstance(result, DecisionDraft)
    assert result.case_id == "case-1"
    assert result.case_revision == 7
    assert result.model_prompt_revision == "decision-model-v1"
    assert provider.requests[0].metadata["case_revision"] == 7


@pytest.mark.asyncio
async def test_model_decision_planner_emits_typed_continuation_without_need_id() -> None:
    provider = _Provider(
        DecisionPlannerResponse(
            action=ContinuationProposal(
                proposition_or_question="Which primary release contains the fix?",
                purpose="verify_fix_release",
                target_objects=["vuln-1"],
                preferred_source_roles=["primary"],
                reason="confirmed state has no primary release evidence",
            )
        )
    )
    result = await ModelDecisionPlanner(provider).plan(
        _state(),
        citation_sources=[CitationSource(evidence_ref="evidence:unused")],
    )
    assert isinstance(result, ContinuationRequest)
    assert result.case_id == "case-1"
    assert result.base_case_revision == 7
    assert result.request_id.startswith("continuation:")
    assert not hasattr(result, "need_id")


def test_final_proposal_fact_schema_requires_evidence() -> None:
    with pytest.raises(ValueError, match="fact conclusion requires evidence_refs"):
        FinalDecisionProposal(
            conclusions=[
                DecisionConclusion(
                    statement="v1.2.3 is fixed",
                    type=ConclusionType.FACT,
                )
            ],
            stop_reason="evidence_sufficient",
        )
