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
    StopAction,
    WaitAction,
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


def test_model_stop_and_wait_reasons_fit_task_storage_contract() -> None:
    frame = InvestigationFrame.model_construct(task_run_id="parent-run", iteration=3)

    def normalize(action: StopAction | WaitAction) -> StopAction | WaitAction:
        return _normalize_action(
            action,
            frame=frame,
            assembly_hash="prompt-hash",
            provider_ref="provider@1",
            budget_ref="budget:parent-run",
        )

    assert normalize(StopAction(reason="evidence_sufficient")).reason == "evidence_sufficient"
    assert (
        normalize(WaitAction(reason="waiting_for_world_update")).reason
        == "waiting_for_world_update"
    )
    assert (
        normalize(StopAction(reason="证据仍有缺口。" * 40)).reason
        == "planner_stop_unstructured_reason"
    )
    assert (
        normalize(WaitAction(reason="More evidence is needed. " * 20)).reason
        == "waiting_for_evidence"
    )
