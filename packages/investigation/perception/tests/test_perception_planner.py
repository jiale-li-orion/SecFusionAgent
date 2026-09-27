from packages.investigation.perception.contracts import (
    EvidenceRequirement,
    IdentifierTarget,
    PerceptionOperation,
    PerceptionRequest,
    PerceptionTarget,
    PhysicalOperator,
)
from packages.investigation.perception.planner import PerceptionPlanner


def test_inspect_identifier_plans_exact_then_structured() -> None:
    request = PerceptionRequest(
        request_id="req-1",
        operation=PerceptionOperation.INSPECT,
        target=PerceptionTarget(
            identifier=IdentifierTarget(namespace="cve", value="CVE-2026-48746"),
            projection_types=["current_vulnerability_view"],
        ),
    )
    plan = PerceptionPlanner().plan(request)

    assert [step.operator for step in plan.steps] == [
        PhysicalOperator.EXACT,
        PhysicalOperator.STRUCTURED,
    ]
    assert plan.steps[1].dependency == "exact:0"
    assert plan.steps[1].input["projection_types"] == ["current_vulnerability_view"]


def test_search_plans_lexical_and_dense_without_forcing_dense() -> None:
    request = PerceptionRequest(
        request_id="req-2",
        operation=PerceptionOperation.SEARCH,
        target=PerceptionTarget(
            query_text="prompt injection",
            query_vector=[0.1, 0.2],
            source_ids=["arxiv-ai-security"],
        ),
        evidence_requirement=EvidenceRequirement(max_candidates=7),
    )
    plan = PerceptionPlanner().plan(request)

    assert [step.operator for step in plan.steps] == [
        PhysicalOperator.LEXICAL,
        PhysicalOperator.DENSE,
    ]
    assert plan.steps[0].input["limit"] == 7
    assert plan.steps[1].input["query_vector"] == [0.1, 0.2]
