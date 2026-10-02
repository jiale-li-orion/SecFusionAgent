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
    assert result.model_prompt_revision == "decision-model-v2"
    assert provider.requests[0].metadata["case_revision"] == 7
    assert "minimal sufficient answer" in provider.requests[0].system_instruction


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


@pytest.mark.asyncio
async def test_model_decision_planner_accepts_runtime_provenance_coordinates() -> None:
    provider = _Provider(
        DecisionPlannerResponse(
            action=FinalDecisionProposal(
                answer_payload={"status": "ok"},
                stop_reason="complete",
            )
        )
    )
    await ModelDecisionPlanner(provider).plan(
        _state(),
        citation_sources=[],
        runtime_metadata={
            "request_owner_ref": "task-run:run-1",
            "task_run_id": "run-1",
            "execution_id": "execution:run-1",
            "budget_ref": "budget:run-1",
            "case_id": None,
        },
    )
    metadata = provider.requests[0].metadata
    assert metadata["request_owner_ref"] == "task-run:run-1"
    assert metadata["task_run_id"] == "run-1"
    assert metadata["execution_id"] == "execution:run-1"
    assert metadata["budget_ref"] == "budget:run-1"
    assert metadata["case_id"] is None


@pytest.mark.asyncio
async def test_model_decision_planner_keeps_session_history_outside_evidence_state() -> None:
    provider = _Provider(
        DecisionPlannerResponse(
            action=FinalDecisionProposal(
                answer_payload={"status": "ok"},
                stop_reason="complete",
            )
        )
    )
    await ModelDecisionPlanner(provider).plan(
        _state(),
        citation_sources=[],
        session_context=[
            {
                "turn_index": 1,
                "user_input": "What was the score?",
                "outcome": {"kind": "decision", "answer": {"score": 9.8}},
            }
        ],
    )
    request = provider.requests[0]
    assert request.data["session_context"] == [
        {
            "turn_index": 1,
            "user_input": "What was the score?",
            "outcome": {"kind": "decision", "answer": {"score": 9.8}},
        }
    ]
    assert "session_context" in request.system_instruction
    assert "It is not evidence or current truth" in request.system_instruction


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


def test_final_proposal_stop_reason_is_bounded_to_runtime_storage_contract() -> None:
    with pytest.raises(ValueError, match="128 characters"):
        FinalDecisionProposal(stop_reason="x" * 129)


def test_continuation_purpose_is_a_bounded_machine_field() -> None:
    with pytest.raises(ValueError, match="128 characters"):
        ContinuationProposal(
            proposition_or_question="Need more evidence?",
            purpose="x" * 129,
            reason="Current state is insufficient.",
        )
