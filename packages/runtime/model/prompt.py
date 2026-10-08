from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession

from packages.runtime.model.contracts import PromptAssemblyRecord, PromptFragmentRecord
from packages.runtime.model.storage import PromptAssemblyRecordModel


class PromptAssemblyRecordService:
    async def persist(
        self,
        session: AsyncSession,
        record: PromptAssemblyRecord,
    ) -> PromptAssemblyRecord:
        existing = await session.get(PromptAssemblyRecordModel, record.assembly_id)
        if existing is not None:
            current = _view(existing)
            identity_exclude = {"created_at", "request_artifact_ref"}
            if current.model_dump(
                mode="json", exclude=identity_exclude
            ) != record.model_dump(mode="json", exclude=identity_exclude):
                raise ValueError("prompt assembly replay identity changed")
            if (
                record.request_artifact_ref is not None
                and current.request_artifact_ref not in {None, record.request_artifact_ref}
            ):
                raise ValueError("prompt assembly request artifact binding changed")
            return current
        model = PromptAssemblyRecordModel(
            assembly_id=record.assembly_id,
            assembly_hash=record.assembly_hash,
            execution_id=record.execution_id,
            task_run_id=record.task_run_id,
            task_contract_id=record.task_contract_id,
            context_manifest_ref=record.context_manifest_ref,
            context_manifest_revision=record.context_manifest_revision,
            role_revision=record.role_revision,
            platform_invariant_revision=record.platform_invariant_revision,
            execution_profile_revision=record.execution_profile_revision,
            policy_context_revision=record.policy_context_revision,
            state_projection_revision=record.state_projection_revision,
            percept_refs_json=list(record.percept_refs),
            materialized_skill_refs_json=list(record.materialized_skill_refs),
            materialized_capability_view_refs_json=list(record.materialized_capability_view_refs),
            materialized_fragment_refs_json=list(record.materialized_fragment_refs),
            ordered_fragment_ids_json=list(record.ordered_fragment_ids),
            materialized_ref_set_digest=record.materialized_ref_set_digest,
            cache_handle_hints_json=list(record.cache_handle_hints),
            fragment_manifest_json=[
                item.model_dump(mode="json") for item in record.fragment_manifest
            ],
            request_artifact_ref=record.request_artifact_ref,
            created_at=record.created_at,
        )
        session.add(model)
        await session.flush()
        return _view(model)

    async def bind_request_artifact(
        self,
        session: AsyncSession,
        *,
        assembly_id: str,
        request_artifact_ref: str,
    ) -> PromptAssemblyRecord:
        model = await session.get(PromptAssemblyRecordModel, assembly_id)
        if model is None:
            raise LookupError(f"prompt assembly record not found: {assembly_id}")
        if model.request_artifact_ref is None:
            model.request_artifact_ref = request_artifact_ref
            await session.flush()
            return _view(model)
        # Assembly identity is content-addressed: repeated planning can reuse the
        # same fragments while issuing a new logical model request. Retain the
        # first request here; each ModelRequest row owns its own artifact ref.
        return _view(model)

    async def get(self, session: AsyncSession, assembly_id: str) -> PromptAssemblyRecord:
        model = await session.get(PromptAssemblyRecordModel, assembly_id)
        if model is None:
            raise LookupError(f"prompt assembly record not found: {assembly_id}")
        return _view(model)


def _view(model: PromptAssemblyRecordModel) -> PromptAssemblyRecord:
    return PromptAssemblyRecord(
        assembly_id=model.assembly_id,
        assembly_hash=model.assembly_hash,
        execution_id=model.execution_id,
        task_run_id=model.task_run_id,
        task_contract_id=model.task_contract_id,
        context_manifest_ref=model.context_manifest_ref,
        context_manifest_revision=model.context_manifest_revision,
        role_revision=model.role_revision,
        platform_invariant_revision=model.platform_invariant_revision,
        execution_profile_revision=model.execution_profile_revision,
        policy_context_revision=model.policy_context_revision,
        state_projection_revision=model.state_projection_revision,
        percept_refs=list(model.percept_refs_json),
        materialized_skill_refs=list(model.materialized_skill_refs_json),
        materialized_capability_view_refs=list(model.materialized_capability_view_refs_json),
        materialized_fragment_refs=list(model.materialized_fragment_refs_json),
        ordered_fragment_ids=list(model.ordered_fragment_ids_json),
        materialized_ref_set_digest=model.materialized_ref_set_digest,
        cache_handle_hints=list(model.cache_handle_hints_json),
        fragment_manifest=[
            PromptFragmentRecord.model_validate(cast(dict[str, JsonValue], item))
            for item in model.fragment_manifest_json
        ],
        request_artifact_ref=model.request_artifact_ref,
        created_at=_utc(model.created_at),
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
