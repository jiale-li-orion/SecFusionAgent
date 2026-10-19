from __future__ import annotations

from datetime import UTC, datetime

import pytest

from packages.investigation.state.continuation import ContinuationRequest
from packages.investigation.state.contracts import InvestigationState, InvestigationStateItem
from packages.reasoning.citation import CitationSource
from packages.reasoning.decision import (
    ConclusionType,
    DecisionConclusion,
    DecisionDraft,
    DecisionReportParagraph,
    DecisionService,
)
from packages.reasoning.model import (
    ContinuationProposal,
    DecisionPlannerResponse,
    FinalDecisionProposal,
    InvestigationReportResponse,
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
        assert response_model is (
            InvestigationReportResponse
            if request.data["prefer_partial_final"] or request.data["methodology_mode"]
            else DecisionPlannerResponse
        )
        self.requests.append(request)
        return response_model.model_validate(self.response.model_dump())


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
    assert result.model_prompt_revision == "decision-model-v9-core"
    assert provider.requests[0].metadata["case_revision"] == 7
    assert "minimal sufficient answer" in provider.requests[0].system_instruction
    assert "research report for a security analyst" not in provider.requests[0].system_instruction


@pytest.mark.asyncio
async def test_model_decision_planner_enables_report_only_for_durable_investigation() -> None:
    provider = _Provider(
        DecisionPlannerResponse(
            action=FinalDecisionProposal(
                report_paragraphs=[
                    DecisionReportParagraph(text="The release contains the confirmed fix.")
                ],
                stop_reason="evidence_sufficient",
            )
        )
    )
    result = await ModelDecisionPlanner(provider).plan(
        _state(), citation_sources=[], include_report=True
    )
    assert isinstance(result, DecisionDraft)
    assert result.model_prompt_revision == "decision-model-v9"
    assert result.report_paragraphs[0].text == "The release contains the confirmed fix."
    assert "research report for a security analyst" in provider.requests[0].system_instruction


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("options", "revision"),
    [
        ({}, "decision-model-v9-core"),
        ({"include_report": True}, "decision-model-v9"),
        ({"methodology_mode": True}, "decision-methodology-v3"),
        ({"include_report": True, "public_briefing": True}, "public-editorial-v7"),
    ],
)
async def test_answer_contract_is_versioned_for_every_planner_profile(options, revision) -> None:
    provider = _Provider(DecisionPlannerResponse(action=FinalDecisionProposal(
        stop_reason="partial_evidence",
    )))
    result = await ModelDecisionPlanner(provider).plan(_state(), citation_sources=[], **options)
    request = provider.requests[0]
    assert isinstance(result, DecisionDraft)
    assert result.model_prompt_revision == revision
    assert request.metadata["prompt_revision"] == revision
    # The shared contract must reach all profiles, including editorial and methodology.
    assert "Source-record lookup:" in request.system_instruction
    assert "Analytical investigation:" in request.system_instruction
    assert "Apply sorting and tie-breaking internally" in request.system_instruction
    assert "including any semantics= suffix" in request.system_instruction
    assert "same state item" in request.system_instruction
    assert "inference" in request.system_instruction
    assert "report_summary and report_paragraphs" in request.system_instruction
    assert "Do not add conclusions to authorize extra report citations" in (
        request.system_instruction
    )
    assert "Return a final report with only the confirmed facts" not in request.system_instruction
    if not options.get("public_briefing"):
        # Keep the contract smaller than the v7 report prompt (5,868 characters).
        assert len(request.system_instruction) < 5868


@pytest.mark.asyncio
@pytest.mark.parametrize("analytical", [False, True])
async def test_record_lookup_and_partial_analysis_preserve_distinct_valid_outcomes(
    analytical,
) -> None:
    state = _state()
    state.goal = (
        "Assess deployment exposure and whether this change mitigates it."
        if analytical else "According to the supplied change record, is it merged?"
    )
    state.confirmed = [InvestigationStateItem(
        proposition='change:17 merged = false semantics={"source_id":"forge"}',
        evidence_refs=["evidence:status"], writer="M3Knowledge",
        reason_code="source_record", updated_revision=7,
    ), InvestigationStateItem(
        proposition='change:17 title = "Guard invalid input"',
        evidence_refs=["evidence:title"], writer="M3Knowledge",
        reason_code="source_record", updated_revision=7,
    )]
    conclusion = DecisionConclusion(
        statement=(
            "The recorded unmerged status does not establish deployment exposure."
            if analytical else state.confirmed[0].proposition
        ),
        type=ConclusionType.INFERENCE if analytical else ConclusionType.FACT,
        evidence_refs=["evidence:status"],
    )
    proposal = FinalDecisionProposal(
        conclusions=[conclusion],
        unknowns=["Deployment exposure has not been checked."] if analytical else [],
        answer_payload={"status": "partial"} if analytical else {"merged": False},
        report_paragraphs=[DecisionReportParagraph(
            text=(
                conclusion.statement if analytical else "The supplied record says it is unmerged."
            ),
            evidence_refs=conclusion.evidence_refs,
        )],
        stop_reason="partial_evidence" if analytical else "evidence_sufficient",
    )
    provider = _Provider(DecisionPlannerResponse(action=proposal))
    sources = [CitationSource(evidence_ref="evidence:status", source_ref="source:forge")]
    draft = await ModelDecisionPlanner(provider).plan(
        state, citation_sources=sources, include_report=True, prefer_partial_final=analytical,
    )
    assert isinstance(draft, DecisionDraft)
    result = DecisionService().decide(state, draft, citation_sources=sources)
    assert result.conclusions == [conclusion]
    assert result.unknowns == proposal.unknowns
    assert result.answer_payload == proposal.answer_payload
    assert result.stop_reason == proposal.stop_reason
    assert result.report_summary is None and result.report_layout is None
    # The planner retains all supplied evidence and the user's full goal; no heuristic
    # drops analytical context or filters conclusions to match a lookup-shaped answer.
    assert provider.requests[0].data["investigation_state"] == state.model_dump(mode="json")
    instruction = provider.requests[0].system_instruction
    assert ("current investigation episode has ended" in instruction) is analytical


@pytest.mark.asyncio
async def test_exhausted_investigation_requests_a_partial_final_report() -> None:
    provider = _Provider(DecisionPlannerResponse(action=FinalDecisionProposal(
        stop_reason="evidence_insufficient",
    )))
    await ModelDecisionPlanner(provider).plan(
        _state(), citation_sources=[], include_report=True, prefer_partial_final=True
    )
    assert provider.requests[0].data["prefer_partial_final"] is True


def test_episode_report_schema_requires_delivery_instead_of_another_continuation() -> None:
    with pytest.raises(ValueError):
        InvestigationReportResponse.model_validate({"action": {
            "kind": "continue", "proposition_or_question": "Check applicability",
            "purpose": "verify_applicability", "reason": "Missing evidence",
        }})


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
