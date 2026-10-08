from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.enrichment.providers.factory import create_configured_ai_provider
from packages.runtime.artifacts import RuntimeArtifactService
from packages.runtime.model import (
    ModelRetryPolicy,
    PromptAssemblyRecord,
    PromptAssemblyRecordService,
    PromptFragmentRecord,
    RecordedModelProvider,
)
from packages.shared.config import Settings
from packages.shared.model_provider import ModelProvider
from packages.task_runtime.context.materializer import PromptAssembly


class RuntimePromptAssemblyRecorder:
    def __init__(self, service: PromptAssemblyRecordService | None = None) -> None:
        self._service = service or PromptAssemblyRecordService()

    async def persist(
        self,
        session: AsyncSession,
        *,
        assembly: PromptAssembly,
        context_manifest_ref: str,
    ) -> None:
        await self._service.persist(
            session,
            PromptAssemblyRecord(
                assembly_id=assembly.assembly_id,
                assembly_hash=assembly.assembly_hash,
                execution_id=assembly.execution_id,
                task_run_id=assembly.task_run_id,
                task_contract_id=assembly.task_contract_id,
                context_manifest_ref=context_manifest_ref,
                context_manifest_revision=assembly.context_manifest_revision,
                role_revision=assembly.role_revision,
                platform_invariant_revision=assembly.platform_invariant_revision,
                execution_profile_revision=assembly.execution_profile_revision,
                policy_context_revision=assembly.policy_context_revision,
                state_projection_revision=assembly.state_projection_revision,
                percept_refs=list(assembly.percept_refs),
                materialized_skill_refs=list(assembly.materialized_skill_refs),
                materialized_capability_view_refs=list(assembly.materialized_capability_view_refs),
                materialized_fragment_refs=list(assembly.materialized_fragment_refs),
                ordered_fragment_ids=list(assembly.ordered_fragment_ids),
                materialized_ref_set_digest=assembly.materialized_ref_set_digest,
                cache_handle_hints=list(assembly.cache_handle_hints),
                fragment_manifest=[
                    PromptFragmentRecord(
                        fragment_id=fragment.fragment_id,
                        kind=fragment.kind,
                        source_ref=fragment.source_ref,
                        source_revision=fragment.source_revision,
                        disclosure_level=fragment.disclosure_level,
                        selection_reason=fragment.selection_reason,
                        trust_class=fragment.trust_class.value,
                        cache_class=fragment.cache_class.value,
                        content_hash=fragment.content_hash,
                    )
                    for fragment in assembly.fragments
                ],
                created_at=datetime.now(UTC),
            ),
        )


def record_model_provider(
    session_factory: async_sessionmaker[AsyncSession],
    provider: ModelProvider,
    *,
    artifact_service: RuntimeArtifactService | None = None,
    retry_policy: ModelRetryPolicy | None = None,
) -> ModelProvider:
    return RecordedModelProvider(
        session_factory,
        provider,
        artifact_service=artifact_service,
        retry_policy=retry_policy,
    )


def create_recorded_model_provider(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    client: httpx.AsyncClient,
    *,
    artifact_service: RuntimeArtifactService | None = None,
    on_delta: Callable[[str, str], Awaitable[None]] | None = None,
) -> ModelProvider | None:
    provider = create_configured_ai_provider(settings, client, on_delta=on_delta)
    if provider is None or not settings.model_name:
        return None
    return RecordedModelProvider(
        session_factory,
        provider,
        artifact_service=artifact_service,
        retry_policy=ModelRetryPolicy(
            max_attempts=settings.model_max_attempts,
            base_delay_seconds=settings.model_retry_base_seconds,
            max_delay_seconds=settings.model_retry_max_seconds,
        ),
    )
