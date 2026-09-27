from __future__ import annotations

from pathlib import Path

import pytest

from apps.task_admission import create_task_contract_service
from packages.runtime.policy.loader import load_runtime_policy
from packages.task_runtime.admission import TaskAdmissionDenied, TaskAdmissionRequest
from packages.task_runtime.contracts.models import TaskIntent, TaskKind


@pytest.mark.asyncio
async def test_runtime_task_admission_compiles_investigation_contract_under_policy() -> None:
    service = create_task_contract_service(load_runtime_policy(Path("config/runtime-policy.json")))
    request = TaskAdmissionRequest(
        intent=TaskIntent(
            raw_request="Verify the fix boundary for the bound case.",
            candidate_task_kind=TaskKind.VERIFY_VERSION_FIX,
            candidate_targets=["case:case-1", "object:vuln-1"],
        ),
        principal="user:test",
        on_behalf_of="team:security",
        policy_revision="policy-v1",
        binding_context={
            "case_id": "case-1",
            "target_object_ids": ["vuln-1"],
            "required_need_ids": ["need-fix-boundary"],
            "allow_wait": True,
        },
    )

    admitted = await service.admit(request)

    assert admitted.policy_authorization == "permit"
    assert admitted.policy_decision_ref is not None
    assert admitted.contract.task_kind is TaskKind.VERIFY_VERSION_FIX
    assert admitted.contract.on_behalf_of == "team:security"
    assert admitted.contract.target_resources == ["case:case-1", "object:vuln-1"]
    assert admitted.contract.desired_state["required_need_ids"] == ["need-fix-boundary"]


@pytest.mark.asyncio
async def test_runtime_task_admission_denies_unmapped_external_principal() -> None:
    service = create_task_contract_service(load_runtime_policy(Path("config/runtime-policy.json")))
    request = TaskAdmissionRequest(
        intent=TaskIntent(
            raw_request="Verify the fix boundary.",
            candidate_task_kind=TaskKind.VERIFY_VERSION_FIX,
        ),
        principal="a2a:untrusted-peer",
        policy_revision="policy-v1",
        binding_context={
            "case_id": "case-1",
            "target_object_ids": [],
            "required_need_ids": ["need-1"],
        },
    )

    with pytest.raises(TaskAdmissionDenied, match="policy_deny"):
        await service.admit(request)
