from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from packages.task_runtime.contracts.models import (
    CancellationSemantics,
    DelegationCeiling,
    EffectCeiling,
    TaskContract,
    TaskKind,
)


class InvestigationTaskDesiredState(BaseModel):
    case_id: str
    required_need_ids: list[str] = Field(min_length=1)
    allow_wait: bool = True

    @model_validator(mode="after")
    def validate_identity(self) -> InvestigationTaskDesiredState:
        if not self.case_id.strip():
            raise ValueError("Investigation task requires case_id")
        if len(set(self.required_need_ids)) != len(self.required_need_ids):
            raise ValueError("required_need_ids must be unique")
        return self


def build_investigation_contract(
    *,
    task_contract_id: str,
    principal: str,
    task_kind: TaskKind,
    case_id: str,
    target_object_ids: list[str],
    required_need_ids: list[str],
    policy_revision: str,
    contract_revision: int = 1,
    on_behalf_of: str | None = None,
    allow_wait: bool = True,
) -> TaskContract:
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
        raise ValueError(f"InvestigationRole does not accept task kind {task_kind.value}")
    desired = InvestigationTaskDesiredState(
        case_id=case_id,
        required_need_ids=required_need_ids,
        allow_wait=allow_wait,
    )
    return TaskContract(
        task_contract_id=task_contract_id,
        contract_revision=contract_revision,
        principal=principal,
        on_behalf_of=on_behalf_of,
        task_kind=task_kind,
        target_resources=[f"case:{case_id}", *[f"object:{item}" for item in target_object_ids]],
        desired_state=desired.model_dump(mode="json"),
        evidence_contract={"authority": "m1_m3_evidence_world"},
        output_contract={"result_type": "InvestigationTaskResult"},
        temporal_contract={"scope": "current"},
        effect_ceiling=EffectCeiling.INTERNAL_STATE,
        delegation_ceiling=DelegationCeiling(
            allowed=True,
            max_depth=1,
            allowed_task_kinds=[TaskKind.ENRICHMENT],
            child_effect_ceiling=EffectCeiling.INTERNAL_STATE,
        ),
        completion_predicate={
            "type": "evidence_needs_resolved",
            "required_need_ids": list(required_need_ids),
        },
        cancellation_semantics=CancellationSemantics.CANCELLABLE,
        policy_revision=policy_revision,
    )
