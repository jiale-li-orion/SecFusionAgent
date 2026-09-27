from __future__ import annotations

from pydantic import BaseModel, Field, JsonValue, model_validator

from packages.investigation.runtime.tasks import build_investigation_contract
from packages.task_runtime.contracts.models import TaskContract, TaskIntent, TaskKind


class InvestigationAdmissionBinding(BaseModel):
    case_id: str
    target_object_ids: list[str] = Field(default_factory=list)
    required_need_ids: list[str] = Field(min_length=1)
    allow_wait: bool = True

    @model_validator(mode="after")
    def validate_binding(self) -> InvestigationAdmissionBinding:
        if not self.case_id.strip():
            raise ValueError("Investigation admission binding requires case_id")
        if len(set(self.target_object_ids)) != len(self.target_object_ids):
            raise ValueError("Investigation admission target_object_ids must be unique")
        if len(set(self.required_need_ids)) != len(self.required_need_ids):
            raise ValueError("Investigation admission required_need_ids must be unique")
        return self


class InvestigationTaskContractCompiler:
    compiler_revision = "investigation-admission-v1"

    def __init__(self, task_kind: TaskKind) -> None:
        allowed = {
            TaskKind.VERIFY_VERSION_FIX,
            TaskKind.RESOLVE_CONFLICT,
            TaskKind.INVESTIGATE_RELATION,
            TaskKind.INVESTIGATE_INCIDENT,
            TaskKind.WATCH_INCIDENT,
            TaskKind.ASSESS_NORMATIVE_APPLICABILITY,
            TaskKind.OBSERVE_LIVE_ASSET,
        }
        if task_kind not in allowed:
            raise ValueError(f"unsupported Investigation admission kind: {task_kind.value}")
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
        binding = InvestigationAdmissionBinding.model_validate(binding_context)
        _validate_candidate_targets(intent, binding)
        return build_investigation_contract(
            task_contract_id=task_contract_id,
            principal=principal,
            on_behalf_of=on_behalf_of,
            task_kind=self.task_kind,
            case_id=binding.case_id,
            target_object_ids=binding.target_object_ids,
            required_need_ids=binding.required_need_ids,
            policy_revision=policy_revision,
            contract_revision=contract_revision,
            allow_wait=binding.allow_wait,
        )


def _validate_candidate_targets(
    intent: TaskIntent,
    binding: InvestigationAdmissionBinding,
) -> None:
    if not intent.candidate_targets:
        return
    allowed = {
        binding.case_id,
        f"case:{binding.case_id}",
        *binding.target_object_ids,
        *(f"object:{item}" for item in binding.target_object_ids),
    }
    unexpected = [item for item in intent.candidate_targets if item not in allowed]
    if unexpected:
        raise ValueError(f"Investigation admission target is not bound: {unexpected[0]}")
