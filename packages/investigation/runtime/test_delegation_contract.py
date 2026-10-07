from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from packages.intelligence.knowledge.vocabulary import EnrichmentDimension
from packages.investigation.runtime.contracts import InvestigationPlannerDecision


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
