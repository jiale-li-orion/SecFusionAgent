from __future__ import annotations

from collections.abc import Iterable

from packages.enrichment.runtime.role import EnrichmentTaskDesiredState
from packages.enrichment.runtime.state import EnrichmentStatus
from packages.intelligence.knowledge.vocabulary import VOCABULARY_REVISION, EnrichmentDimension
from packages.task_runtime.contracts.models import (
    CancellationSemantics,
    DelegationCeiling,
    EffectCeiling,
    TaskContract,
    TaskKind,
)


def build_vulnerability_enrichment_contract(
    *,
    task_contract_id: str,
    principal: str,
    target_object_id: str,
    cve_id: str,
    required_dimensions: Iterable[EnrichmentDimension],
    policy_revision: str,
    contract_revision: int = 1,
    on_behalf_of: str | None = None,
) -> TaskContract:
    dimensions = sorted(set(required_dimensions), key=lambda item: item.value)
    desired = EnrichmentTaskDesiredState(
        target_object_id=target_object_id,
        cve_id=cve_id.upper(),
        required_dimensions=dimensions,
    )
    return TaskContract(
        task_contract_id=task_contract_id,
        contract_revision=contract_revision,
        principal=principal,
        on_behalf_of=on_behalf_of,
        task_kind=TaskKind.ENRICHMENT,
        target_resources=[f"object:{target_object_id}", f"cve:{cve_id.upper()}"],
        desired_state=desired.model_dump(mode="json"),
        evidence_contract={
            "vocabulary_revision": VOCABULARY_REVISION,
            "fact_authority": "m1_m3_evidence_world",
        },
        output_contract={
            "result_type": "EnrichmentTaskResult",
            "dimensions": [item.value for item in dimensions],
        },
        temporal_contract={"scope": "current"},
        effect_ceiling=EffectCeiling.INTERNAL_STATE,
        delegation_ceiling=DelegationCeiling(),
        completion_predicate={
            "type": "enrichment_dimensions_terminal",
            "required_dimensions": [item.value for item in dimensions],
            "terminal_statuses": [
                EnrichmentStatus.RESOLVED.value,
                EnrichmentStatus.CONFLICT.value,
                EnrichmentStatus.UNKNOWN.value,
            ],
        },
        cancellation_semantics=CancellationSemantics.CANCELLABLE,
        policy_revision=policy_revision,
    )


async def ensure_background_vulnerability_enrichment_run(
    session,
    *,
    object_id: str,
    cve_id: str,
    trigger_ref: str,
    stream_name: str,
    policy_revision: str = "policy-v1",
) -> str:
    from uuid import NAMESPACE_URL, uuid5

    from sqlalchemy import func, select

    from packages.intelligence.storage.knowledge_models import KnowledgeRevisionModel
    from packages.task_runtime.contracts.models import ContextManifest
    from packages.task_runtime.contracts.roles import canonical_roles
    from packages.task_runtime.storage.models import TaskRunModel
    from packages.task_runtime.storage.service import create_task_run

    run_id = str(
        uuid5(
            NAMESPACE_URL,
            f"secfusion:background-enrichment:{object_id}:{trigger_ref}",
        )
    )
    if await session.get(TaskRunModel, run_id) is not None:
        return run_id

    trigger_revision = await session.scalar(
        select(KnowledgeRevisionModel.revision)
        .where(KnowledgeRevisionModel.cause_processing_run_id == trigger_ref)
        .order_by(KnowledgeRevisionModel.revision.desc())
        .limit(1)
    )
    knowledge_revision = int(
        trigger_revision
        or await session.scalar(select(func.max(KnowledgeRevisionModel.revision)))
        or 0
    )
    contract = build_vulnerability_enrichment_contract(
        task_contract_id=f"background-enrichment:{object_id}:{trigger_ref}",
        principal="system:background-enrichment",
        target_object_id=object_id,
        cve_id=cve_id,
        required_dimensions=default_background_vulnerability_dimensions(),
        policy_revision=policy_revision,
    )
    contract.target_resources.append(f"processing-run:{trigger_ref}")
    manifest = ContextManifest(
        context_id=f"context:background-enrichment:{run_id}",
        context_revision=1,
        task_contract_ref=f"{contract.task_contract_id}@{contract.contract_revision}",
        role_ref="EnrichmentRole@1",
        knowledge_revision=knowledge_revision,
        object_refs=[object_id],
        policy_context_ref=f"policy-context:{policy_revision}",
        capability_envelope_ref="capability:enrichment:v1",
        budget_ref=f"budget:{run_id}",
    )
    await create_task_run(
        session,
        contract=contract,
        manifest=manifest,
        role=canonical_roles()["EnrichmentRole"],
        execution_envelope_ref=f"execution:{run_id}",
        stream_name=stream_name,
        run_id=run_id,
    )
    return run_id


def default_background_vulnerability_dimensions() -> list[EnrichmentDimension]:
    from packages.enrichment.runtime.operators import enrichment_operator_registry

    dimensions = {
        dimension
        for operator in enrichment_operator_registry().values()
        for dimension in operator.produces
    }
    return sorted(dimensions, key=lambda item: item.value)
