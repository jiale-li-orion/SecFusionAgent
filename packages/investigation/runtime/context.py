from __future__ import annotations

from typing import cast

from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession

from packages.investigation.state.service import InvestigationStateService
from packages.task_runtime.context.materializer import (
    ContextMaterializer,
    FragmentCacheClass,
    FragmentTrustClass,
    MaterializedFragment,
    PromptAssembly,
)
from packages.task_runtime.contracts.models import ContextManifest
from packages.task_runtime.storage.service import get_task_context


async def materialize_investigation_state_fragment(
    session: AsyncSession,
    manifest: ContextManifest,
    *,
    state_service: InvestigationStateService | None = None,
) -> MaterializedFragment | None:
    if manifest.case_ref is None or manifest.investigation_state_ref is None:
        return None
    service = state_service or InvestigationStateService()
    state = await service.get_state(session, manifest.case_ref)
    expected_ref = f"case:{state.case_id}@{state.case_revision}"
    if manifest.investigation_state_ref != expected_ref:
        raise ValueError(
            "ContextManifest investigation_state_ref is stale and requires refresh/rebase: "
            f"pinned={manifest.investigation_state_ref}, current={expected_ref}"
        )
    needs = [
        (await service.get_evidence_need(session, need_id)).model_dump(mode="json")
        for need_id in state.evidence_need_ids
    ]
    return MaterializedFragment.build(
        kind="investigation_state",
        source_ref=manifest.investigation_state_ref,
        source_revision=str(state.case_revision),
        trust_class=FragmentTrustClass.DURABLE_STATE,
        cache_class=FragmentCacheClass.STATE_DYNAMIC,
        content={
            "state": state.model_dump(mode="json"),
            "evidence_needs": cast(JsonValue, needs),
        },
    )


async def materialize_evidence_world_fragments(
    session: AsyncSession,
    manifest: ContextManifest,
) -> list[MaterializedFragment]:
    from packages.intelligence.retrieval.context import read_context_world_slice

    world = await read_context_world_slice(
        session,
        pinned_knowledge_revision=manifest.knowledge_revision,
        object_refs=manifest.object_refs,
        relation_refs=manifest.relation_refs,
        evidence_refs=manifest.evidence_refs,
    )
    return [
        MaterializedFragment.build(
            kind=item.kind,
            source_ref=item.source_ref,
            source_revision=item.source_revision,
            trust_class=FragmentTrustClass.EVIDENCE_REFERENCE,
            cache_class=FragmentCacheClass.STATE_DYNAMIC,
            content=item.content,
        )
        for item in world.items
    ]


async def materialize_investigation_context_fragments(
    session: AsyncSession,
    manifest: ContextManifest,
    *,
    state_service: InvestigationStateService | None = None,
) -> list[MaterializedFragment]:
    fragments = await materialize_evidence_world_fragments(session, manifest)
    state = await materialize_investigation_state_fragment(
        session,
        manifest,
        state_service=state_service,
    )
    if state is not None:
        fragments.append(state)
    return sorted(fragments, key=lambda item: (item.kind, item.source_ref, item.fragment_id))


async def materialize_investigation_prompt(
    session: AsyncSession,
    *,
    task_run_id: str,
    materializer: ContextMaterializer,
    state_service: InvestigationStateService | None = None,
    disclosure_fragments: list[MaterializedFragment] | None = None,
    additional_dynamic_fragments: list[MaterializedFragment] | None = None,
    ephemeral_fragments: list[MaterializedFragment] | None = None,
    runtime_disclosure_refs: set[str] | None = None,
    percept_refs: list[str] | None = None,
    execution_profile_revision: str | None = None,
) -> PromptAssembly:
    manifest = await get_task_context(session, task_run_id)
    dynamic = await materialize_investigation_context_fragments(
        session,
        manifest,
        state_service=state_service,
    )
    dynamic.extend(additional_dynamic_fragments or [])
    return await materializer.materialize(
        session,
        task_run_id=task_run_id,
        disclosure_fragments=disclosure_fragments,
        dynamic_fragments=dynamic,
        ephemeral_fragments=ephemeral_fragments,
        runtime_disclosure_refs=runtime_disclosure_refs,
        percept_refs=percept_refs,
        execution_profile_revision=execution_profile_revision,
        state_projection_revision=manifest.investigation_state_ref,
    )


def _strip_ref_prefix(value: str, kind: str) -> str:
    prefix = f"{kind}:"
    return value[len(prefix) :] if value.startswith(prefix) else value
