from __future__ import annotations

import pytest
from pydantic import JsonValue

from packages.task_runtime.admission import (
    TaskAdmissionAuthorization,
    TaskAdmissionDenied,
    TaskAdmissionRequest,
    TaskContractService,
    TaskIntentParser,
)
from packages.task_runtime.contracts.models import (
    DelegationCeiling,
    EffectCeiling,
    TaskContract,
    TaskIntent,
    TaskKind,
)


class _LookupCompiler:
    task_kind = TaskKind.LOOKUP
    compiler_revision = "lookup-test-v1"

    def compile(
        self,
        intent: TaskIntent,
        *,
        task_contract_id: str,
        contract_revision: int,
        principal: str,
        on_behalf_of: str | None,
        policy_revision: str,
        binding_context: dict[str, JsonValue],
    ) -> TaskContract:
        field = str(binding_context.get("field", "severity"))
        return TaskContract(
            task_contract_id=task_contract_id,
            contract_revision=contract_revision,
            principal=principal,
            on_behalf_of=on_behalf_of,
            task_kind=TaskKind.LOOKUP,
            target_resources=list(intent.candidate_targets),
            desired_state={"field": field},
            output_contract={"field": field},
            effect_ceiling=EffectCeiling.READ_ONLY,
            delegation_ceiling=DelegationCeiling(),
            completion_predicate={"type": "field_resolved"},
            policy_revision=policy_revision,
        )


class _Authorizer:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed

    async def authorize(self, *, intent_ref, intent, candidate_contract):
        del intent, candidate_contract
        return TaskAdmissionAuthorization(
            allowed=self.allowed,
            authorization="permit" if self.allowed else "deny",
            policy_decision_ref=f"policy:{intent_ref}",
            denial_reason=None if self.allowed else "policy_deny",
        )


def test_deterministic_parser_extracts_identifiers_without_guessing_task_kind() -> None:
    intent = TaskIntentParser().parse(
        raw_request=(
            "Verify CVE-2026-12345 against object:vuln-1 and GHSA-ab12-cd34-ef56 for case:case-9"
        )
    )

    assert intent.candidate_task_kind is None
    assert intent.parsed_identifiers == [
        "CVE-2026-12345",
        "GHSA-AB12-CD34-EF56",
        "object:vuln-1",
        "case:case-9",
    ]
    assert intent.candidate_targets == ["object:vuln-1", "case:case-9"]


@pytest.mark.asyncio
async def test_task_contract_service_is_deterministic_and_rejects_ambiguous_intent() -> None:
    service = TaskContractService([_LookupCompiler()], authorizer=_Authorizer())
    ambiguous = TaskAdmissionRequest(
        intent=TaskIntent(raw_request="What is the score?"),
        principal="user:test",
        policy_revision="policy-v1",
    )
    with pytest.raises(ValueError, match="ambiguous"):
        await service.admit(ambiguous)

    request = TaskAdmissionRequest(
        intent=TaskIntent(
            raw_request="What is the score?",
            candidate_task_kind=TaskKind.LOOKUP,
            candidate_targets=["object:vuln-1"],
        ),
        principal="user:test",
        policy_revision="policy-v1",
        binding_context={"field": "severity"},
    )
    first = await service.admit(request)
    second = await service.admit(request)

    assert first.intent_ref == second.intent_ref
    assert first.contract == second.contract
    assert first.replay_key == second.replay_key
    assert first.contract.effect_ceiling is EffectCeiling.READ_ONLY


@pytest.mark.asyncio
async def test_task_contract_service_fails_closed_on_policy_deny() -> None:
    service = TaskContractService([_LookupCompiler()], authorizer=_Authorizer(False))
    request = TaskAdmissionRequest(
        intent=TaskIntent(
            raw_request="lookup",
            candidate_task_kind=TaskKind.LOOKUP,
        ),
        principal="user:test",
        policy_revision="policy-v1",
    )
    with pytest.raises(TaskAdmissionDenied, match="policy_deny"):
        await service.admit(request)
