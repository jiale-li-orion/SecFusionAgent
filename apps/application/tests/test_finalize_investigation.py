from datetime import UTC, datetime

from apps.application.commands.finalize_investigation import _partial_evidence_report
from packages.investigation.state.contracts import InvestigationState, InvestigationStateItem
from packages.reasoning.citation import CitationSource
from packages.reasoning.decision import DecisionService


def test_partial_report_keeps_confirmed_citations_and_unknown_boundary() -> None:
    state = InvestigationState(
        case_id="case-1",
        case_revision=3,
        goal="What did the operator do?",
        confirmed=[
            InvestigationStateItem(
                proposition="The operator notified its partners.",
                evidence_refs=["evidence:notice"],
                writer="InvestigationRole",
                reason_code="verified",
                updated_revision=2,
            )
        ],
        unknowns=[
            InvestigationStateItem(
                proposition="Whether funds were frozen remains unverified.",
                writer="InvestigationRole",
                reason_code="not_in_source",
                updated_revision=3,
            )
        ],
        evidence_need_ids=["need-1"],
        updated_at=datetime(2026, 10, 9, tzinfo=UTC),
    )

    decision = DecisionService().decide(
        state,
        _partial_evidence_report(state),
        citation_sources=[
            CitationSource(
                evidence_ref="evidence:notice",
                source_ref="source:notice",
                locator={"field": "body"},
            )
        ],
    )

    assert decision.conclusions[0].statement == state.confirmed[0].proposition
    assert decision.citations[0].evidence_ref == "evidence:notice"
    assert decision.unknowns == [state.unknowns[0].proposition]
    assert len(decision.report_paragraphs) == 2
