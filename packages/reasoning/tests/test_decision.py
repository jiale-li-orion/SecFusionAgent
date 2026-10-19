from __future__ import annotations

from datetime import UTC, datetime

import pytest

from packages.investigation.state.continuation import ContinuationRequest
from packages.investigation.state.contracts import (
    EvidenceNeedContract,
    InvestigationState,
    InvestigationStateItem,
)
from packages.reasoning.citation import CitationSource
from packages.reasoning.decision import (
    ConclusionType,
    DecisionConclusion,
    DecisionDraft,
    DecisionReportParagraph,
    DecisionService,
)

NOW = datetime(2026, 9, 27, 18, 0, tzinfo=UTC)


def _state() -> InvestigationState:
    return InvestigationState(
        case_id="case-1",
        case_revision=4,
        goal="Decide whether the fixed release is established.",
        targets=["vuln-1"],
        confirmed=[
            InvestigationStateItem(
                proposition="Release v1.2.3 contains the fix.",
                target_ref="object:vuln-1",
                evidence_refs=["evidence:primary-release"],
                writer="InvestigationRole",
                reason_code="verified",
                updated_revision=4,
            )
        ],
        tentative=[
            InvestigationStateItem(
                proposition="Release v1.2.2 may contain the fix.",
                target_ref="object:vuln-1",
                evidence_refs=["evidence:secondary-blog"],
                writer="InvestigationRole",
                reason_code="secondary_only",
                updated_revision=3,
            )
        ],
        updated_at=NOW,
    )


def test_decision_service_binds_fact_to_confirmed_evidence_and_locator() -> None:
    result = DecisionService().decide(
        _state(),
        DecisionDraft(
            case_id="case-1",
            case_revision=4,
            conclusions=[
                DecisionConclusion(
                    statement="Release v1.2.3 contains the fix.",
                    type=ConclusionType.FACT,
                    evidence_refs=["evidence:primary-release"],
                )
            ],
            answer_payload={"fixed_release": "v1.2.3"},
            report_paragraphs=[
                DecisionReportParagraph(
                    text=(
                        "Release v1.2.3 contains the confirmed fix, according to "
                        "the primary release evidence."
                    ),
                    evidence_refs=["evidence:primary-release"],
                )
            ],
            stop_reason="evidence_sufficient",
            model_prompt_revision="decision-v1",
        ),
        citation_sources=[
            CitationSource(
                evidence_ref="evidence:primary-release",
                source_ref="source:vendor-advisory",
                locator={"field": "fixed_version"},
            )
        ],
    )
    assert result.decision_id.startswith("decision:")
    assert result.case_revision == 4
    assert result.citations[0].evidence_ref == "evidence:primary-release"
    assert result.citations[0].locator == {"field": "fixed_version"}
    assert result.report_paragraphs[0].evidence_refs == ["evidence:primary-release"]


def test_decision_service_rejects_report_citation_outside_conclusions() -> None:
    with pytest.raises(
        ValueError, match="report paragraph cites evidence outside decision conclusions"
    ):
        DecisionService().decide(
            _state(),
            DecisionDraft(
                case_id="case-1",
                case_revision=4,
                report_paragraphs=[
                    DecisionReportParagraph(
                        text="An unsupported report claim.",
                        evidence_refs=["evidence:secondary-blog"],
                    )
                ],
                stop_reason="evidence_sufficient",
                model_prompt_revision="decision-v3",
            ),
            citation_sources=[],
        )


def test_decision_service_rejects_fact_from_tentative_evidence() -> None:
    with pytest.raises(ValueError, match="outside confirmed M4 state"):
        DecisionService().decide(
            _state(),
            DecisionDraft(
                case_id="case-1",
                case_revision=4,
                conclusions=[
                    DecisionConclusion(
                        statement="v1.2.2 is fixed.",
                        type=ConclusionType.FACT,
                        evidence_refs=["evidence:secondary-blog"],
                    )
                ],
                stop_reason="evidence_sufficient",
                model_prompt_revision="decision-v1",
            ),
            citation_sources=[
                CitationSource(
                    evidence_ref="evidence:secondary-blog",
                    source_ref="source:blog",
                )
            ],
        )


def test_decision_service_rejects_fact_statement_not_confirmed_by_m4() -> None:
    with pytest.raises(ValueError, match="must reproduce one confirmed M4 proposition"):
        DecisionService().decide(
            _state(),
            DecisionDraft(
                case_id="case-1",
                case_revision=4,
                conclusions=[
                    DecisionConclusion(
                        statement="v1.2.3 fixes every affected deployment.",
                        type=ConclusionType.FACT,
                        evidence_refs=["evidence:primary-release"],
                    )
                ],
                stop_reason="evidence_sufficient",
                model_prompt_revision="decision-v1",
            ),
            citation_sources=[
                CitationSource(
                    evidence_ref="evidence:primary-release",
                    source_ref="source:vendor-advisory",
                )
            ],
        )


def test_decision_service_only_returns_continuation_against_current_state() -> None:
    request = ContinuationRequest(
        request_id="continuation-1",
        case_id="case-1",
        base_case_revision=4,
        proposition_or_question="Which primary source confirms the affected range?",
        purpose="confirm_affected_range",
        target_objects=["vuln-1"],
        evidence_contract=EvidenceNeedContract(required_source_roles=["primary"]),
        reason="decision state lacks primary range evidence",
    )
    assert DecisionService().request_continuation(_state(), request) == request
    with pytest.raises(ValueError, match="escape M4 state"):
        DecisionService().request_continuation(
            _state(),
            request.model_copy(update={"target_objects": ["other-object"]}),
        )


def test_decision_service_rejects_stale_case_revision() -> None:
    with pytest.raises(ValueError, match="stale"):
        DecisionService().decide(
            _state(),
            DecisionDraft(
                case_id="case-1",
                case_revision=3,
                stop_reason="partial",
                model_prompt_revision="decision-v1",
            ),
            citation_sources=[],
        )


@pytest.mark.parametrize("mutation", [None, "drop_qualifier", "swap_evidence"])
def test_qualified_fact_retains_its_exact_statement_and_evidence_identity(mutation) -> None:
    state = _state()
    qualified = 'component:widget affected-by vulnerability:example semantics={"platform":"linux"}'
    state.confirmed[0].proposition = qualified
    state.confirmed.append(state.confirmed[0].model_copy(update={
        "proposition": "The vendor published an advisory.",
        "evidence_refs": ["evidence:advisory-title"],
    }))
    statement = qualified.split(" semantics=", 1)[0] if mutation == "drop_qualifier" else qualified
    ref = "evidence:advisory-title" if mutation == "swap_evidence" else "evidence:primary-release"
    draft = DecisionDraft(
        case_id=state.case_id,
        case_revision=state.case_revision,
        conclusions=[DecisionConclusion(
            statement=statement, type=ConclusionType.FACT, evidence_refs=[ref],
        )],
        stop_reason="evidence_sufficient",
        model_prompt_revision="decision-test",
    )
    # Even matching source and locator coordinates cannot substitute another fact's ref.
    sources = [CitationSource(
        evidence_ref=evidence_ref,
        source_ref="source:vendor-advisory",
        locator={"field": "advisory"},
    ) for evidence_ref in ("evidence:primary-release", "evidence:advisory-title")]
    if mutation is not None:
        with pytest.raises(ValueError, match="must reproduce one confirmed M4 proposition"):
            DecisionService().decide(state, draft, citation_sources=sources)
    else:
        result = DecisionService().decide(state, draft, citation_sources=sources)
        assert result.conclusions[0].statement == qualified
        assert result.citations[0].evidence_ref == "evidence:primary-release"


@pytest.mark.parametrize("summary", [False, True])
def test_report_cannot_borrow_available_evidence_omitted_from_conclusions(summary) -> None:
    state = _state()
    text = DecisionReportParagraph(
        text="The earlier release may also contain the fix.",
        evidence_refs=["evidence:secondary-blog"],
    )
    draft = DecisionDraft(
        case_id=state.case_id,
        case_revision=state.case_revision,
        conclusions=[DecisionConclusion(
            statement=state.confirmed[0].proposition,
            type=ConclusionType.FACT,
            evidence_refs=state.confirmed[0].evidence_refs,
        )],
        report_summary=text if summary else None,
        report_paragraphs=[] if summary else [text],
        stop_reason="evidence_sufficient",
        model_prompt_revision="decision-test",
    )
    with pytest.raises(ValueError, match="report paragraph cites evidence outside"):
        DecisionService().decide(state, draft, citation_sources=[
            CitationSource(evidence_ref="evidence:primary-release"),
            CitationSource(evidence_ref="evidence:secondary-blog"),
        ])


def test_genuine_supported_inference_remains_a_valid_answer() -> None:
    state = _state()
    state.goal = "What uncertainty remains about the earliest fixed release?"
    inference = DecisionConclusion(
        statement=(
            "The primary release evidence establishes v1.2.3, but the secondary report "
            "suggests v1.2.2 may already contain the fix; "
            "the earliest fixed release remains uncertain."
        ),
        type=ConclusionType.INFERENCE,
        evidence_refs=["evidence:primary-release", "evidence:secondary-blog"],
    )
    paragraph = DecisionReportParagraph(
        text=inference.statement, evidence_refs=inference.evidence_refs,
    )
    result = DecisionService().decide(state, DecisionDraft(
        case_id=state.case_id,
        case_revision=state.case_revision,
        conclusions=[inference],
        report_summary=paragraph,
        report_paragraphs=[paragraph],
        unknowns=["Earliest fixed release"],
        stop_reason="partial_evidence",
        model_prompt_revision="decision-test",
    ), citation_sources=[
        CitationSource(evidence_ref=ref) for ref in inference.evidence_refs
    ])
    assert result.conclusions == [inference]
    assert {citation.evidence_ref for citation in result.citations} == set(inference.evidence_refs)
