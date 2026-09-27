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
                    statement="v1.2.3 is the verified fixed release.",
                    type=ConclusionType.FACT,
                    evidence_refs=["evidence:primary-release"],
                )
            ],
            answer_payload={"fixed_release": "v1.2.3"},
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
