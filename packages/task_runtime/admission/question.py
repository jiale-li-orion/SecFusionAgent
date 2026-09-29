from __future__ import annotations

from typing import cast

from pydantic import BaseModel, Field, JsonValue

from packages.task_runtime.contracts.models import (
    CancellationSemantics,
    DelegationCeiling,
    EffectCeiling,
    TaskContract,
    TaskIntent,
    TaskKind,
)


class QuestionAdmissionBinding(BaseModel):
    question: str = Field(min_length=1)
    target_object_ids: list[str] = Field(default_factory=list)


class QuestionTaskContractCompiler:
    compiler_revision = "question-admission-v1"

    def __init__(self, task_kind: TaskKind) -> None:
        if task_kind not in {TaskKind.LOOKUP, TaskKind.RETRIEVE}:
            raise ValueError(f"unsupported question admission kind: {task_kind.value}")
        self.task_kind = task_kind

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
        binding = QuestionAdmissionBinding.model_validate(binding_context)
        allowed_targets = {
            *binding.target_object_ids,
            *(f"object:{item}" for item in binding.target_object_ids),
        }
        unexpected = [item for item in intent.candidate_targets if item not in allowed_targets]
        if unexpected:
            raise ValueError(f"question admission target is not bound: {unexpected[0]}")
        return _build_question_contract(
            task_contract_id=task_contract_id,
            principal=principal,
            on_behalf_of=on_behalf_of,
            task_kind=self.task_kind,
            question=binding.question,
            target_object_ids=binding.target_object_ids,
            policy_revision=policy_revision,
            contract_revision=contract_revision,
        )


def _build_question_contract(
    *,
    task_contract_id: str,
    principal: str,
    task_kind: TaskKind,
    question: str,
    target_object_ids: list[str],
    policy_revision: str,
    contract_revision: int,
    on_behalf_of: str | None,
) -> TaskContract:
    return TaskContract(
        task_contract_id=task_contract_id,
        contract_revision=contract_revision,
        principal=principal,
        on_behalf_of=on_behalf_of,
        task_kind=task_kind,
        target_resources=[f"object:{item}" for item in target_object_ids],
        desired_state=cast(
            dict[str, JsonValue],
            {"question": question, "target_object_ids": target_object_ids},
        ),
        evidence_contract={"authority": "m1_m3_evidence_world", "access": "read_only"},
        output_contract={"result_type": "DecisionResult|InvestigationView"},
        temporal_contract={"scope": "current"},
        effect_ceiling=EffectCeiling.READ_ONLY,
        delegation_ceiling=DelegationCeiling(),
        completion_predicate={"type": "decision_or_investigation_escalation"},
        cancellation_semantics=CancellationSemantics.CANCELLABLE,
        policy_revision=policy_revision,
    )
