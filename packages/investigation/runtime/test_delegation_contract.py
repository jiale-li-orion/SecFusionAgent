from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from packages.intelligence.knowledge.vocabulary import EnrichmentDimension
from packages.investigation.runtime.contracts import (
    DelegationAction,
    EnrichmentDelegationRequest,
    InvestigationFrame,
    InvestigationPlannerDecision,
)
from packages.investigation.runtime.planner import _normalize_action


def test_planner_delegation_rejects_answer_fields_as_enrichment_dimensions() -> None:
    proposal: dict[str, Any] = {
        "action": {
            "kind": "delegate",
            "request": {
                "delegation_id": "model-proposal",
                "target_object_id": "vulnerability-id",
                "cve_id": "CVE-2026-48746",
                "required_dimensions": ["first_fixed_version"],
                "reason": "Verify the first fixed version",
            },
        }
    }
    with pytest.raises(ValidationError, match="required_dimensions"):
        InvestigationPlannerDecision.model_validate(proposal)

    proposal["action"]["request"]["required_dimensions"] = ["fix_remediation"]
    decision = InvestigationPlannerDecision.model_validate(proposal)
    assert decision.model_dump(mode="json")["action"]["request"]["required_dimensions"] == [
        "fix_remediation"
    ]
    schema = InvestigationPlannerDecision.model_json_schema()
    assert set(schema["$defs"]["EnrichmentDimension"]["enum"]) == {
        dimension.value for dimension in EnrichmentDimension
    }


def test_delegation_identity_is_stable_across_parent_context_refresh() -> None:
    request = EnrichmentDelegationRequest(
        delegation_id="model-proposal",
        target_object_id="vulnerability-id",
        cve_id="CVE-2026-48746",
        required_dimensions=[EnrichmentDimension.FIX_REMEDIATION],
        reason="Verify the first fixed release",
    )

    def normalize(iteration: int, assembly_hash: str, value: EnrichmentDelegationRequest):
        return _normalize_action(
            DelegationAction(request=value),
            frame=InvestigationFrame.model_construct(
                task_run_id="parent-run", iteration=iteration
            ),
            assembly_hash=assembly_hash,
            provider_ref="provider@1",
            budget_ref="budget:parent-run",
        )

    first = normalize(1, "before-enrichment", request)
    replay = normalize(3, "after-enrichment", request)
    another_dimension = normalize(
        3,
        "after-enrichment",
        request.model_copy(
            update={"required_dimensions": [EnrichmentDimension.VERSION_APPLICABILITY]}
        ),
    )

    assert first.request.delegation_id == replay.request.delegation_id
    assert first.request.delegation_id != another_dimension.request.delegation_id
