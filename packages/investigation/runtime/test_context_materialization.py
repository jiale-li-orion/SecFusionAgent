from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import (
    EvidenceLinkModel,
    KnowledgeRevisionModel,
    ObjectModel,
)
from packages.investigation.cases.service import CaseService
from packages.investigation.runtime.context import (
    materialize_investigation_prompt,
    materialize_investigation_state_fragment,
)
from packages.investigation.runtime.tasks import build_investigation_contract
from packages.investigation.state.service import InvestigationStateService
from packages.shared.db import Base
from packages.sources.storage.models import SourceModel
from packages.task_runtime.context.materializer import ContextMaterializer
from packages.task_runtime.contracts.models import ContextManifest, TaskKind
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.service import create_task_run, get_task_context

NOW = datetime(2026, 9, 27, 6, 15, tzinfo=UTC)


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_investigation_state_fragment_requires_exact_pinned_case_revision() -> None:
    engine, factory = await _database()
    service = InvestigationStateService(now=lambda: NOW)
    try:
        async with factory() as session, session.begin():
            revision = KnowledgeRevisionModel(committed_at=NOW)
            session.add(revision)
            await session.flush()
            object_id = str(uuid4())
            session.add(
                ObjectModel(
                    object_id=object_id,
                    object_type="Vulnerability",
                    canonical_key="cve:CVE-2026-91919",
                    properties={},
                    created_revision=revision.revision,
                )
            )
            await session.flush()
            case = await CaseService(now=lambda: NOW).create(
                session,
                task_signature="materialize-investigation",
                target_object_ids=[object_id],
                goal="Materialize pinned investigation state.",
                initial_knowledge_revision=revision.revision,
            )
            need = await service.open_evidence_need(
                session,
                case_id=case.case_id,
                base_case_revision=0,
                need_id=str(uuid4()),
                proposition_or_question="Need primary verification",
                purpose="verify",
                target_objects=[object_id],
            )
            run_id = str(uuid4())
            contract = build_investigation_contract(
                task_contract_id=f"verify:{run_id}",
                principal="user:test",
                task_kind=TaskKind.VERIFY_VERSION_FIX,
                case_id=case.case_id,
                target_object_ids=[object_id],
                required_need_ids=[need.need.need_id],
                policy_revision="policy-v1",
            )
            manifest = ContextManifest(
                context_id=f"context:{run_id}",
                context_revision=1,
                task_contract_ref=f"{contract.task_contract_id}@1",
                role_ref="InvestigationRole@1",
                case_ref=case.case_id,
                knowledge_revision=revision.revision,
                investigation_state_ref=f"case:{case.case_id}@1",
                object_refs=[object_id],
                policy_context_ref="policy-context:v1",
                capability_envelope_ref="capability:investigation:v1",
                budget_ref=f"budget:{run_id}",
            )
            await create_task_run(
                session,
                contract=contract,
                manifest=manifest,
                role=canonical_roles()["InvestigationRole"],
                execution_envelope_ref=f"execution:{run_id}",
                stream_name="secfusion:task-events:test",
                case_id=case.case_id,
                run_id=run_id,
                now=NOW,
            )

        async with factory() as session:
            current_manifest = await get_task_context(session, run_id)
            fragment = await materialize_investigation_state_fragment(
                session, current_manifest, state_service=service
            )
            assert fragment is not None
            assert fragment.source_ref == f"case:{case.case_id}@1"
            assembly = await ContextMaterializer(
                platform_invariant_revision="platform-v1",
                platform_invariant={"authority": "runtime gates"},
            ).materialize(
                session,
                task_run_id=run_id,
                dynamic_fragments=[fragment],
                state_projection_revision=fragment.source_ref,
            )
            assert assembly.state_projection_revision == fragment.source_ref
            assert fragment.fragment_id in assembly.ordered_fragment_ids

        async with factory() as session, session.begin():
            await service.open_evidence_need(
                session,
                case_id=case.case_id,
                base_case_revision=1,
                need_id=str(uuid4()),
                proposition_or_question="Need independent corroboration",
                purpose="corroborate",
                target_objects=[object_id],
            )

        async with factory() as session:
            stale_manifest = await get_task_context(session, run_id)
            with pytest.raises(ValueError, match="stale and requires refresh/rebase"):
                await materialize_investigation_state_fragment(
                    session, stale_manifest, state_service=service
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_investigation_prompt_materializes_pinned_object_and_evidence_refs() -> None:
    engine, factory = await _database()
    service = InvestigationStateService(now=lambda: NOW)
    try:
        async with factory() as session, session.begin():
            revision = KnowledgeRevisionModel(committed_at=NOW)
            session.add(revision)
            await session.flush()
            object_id = str(uuid4())
            session.add(
                ObjectModel(
                    object_id=object_id,
                    object_type="Vulnerability",
                    canonical_key="cve:CVE-2026-92929",
                    properties={"display_name": "CVE-2026-92929"},
                    created_revision=revision.revision,
                )
            )
            source_id = f"vendor-primary-{uuid4()}"
            session.add(
                SourceModel(
                    source_id=source_id,
                    adapter_type="fixture",
                    source_class="vendor_security_material",
                    authority_scope=["fix_status"],
                    source_role="primary",
                    source_family="vendor",
                    upstream_source=None,
                    access_mode="fixture",
                    update_semantics="mutable",
                    discovery_method={},
                    time_semantics={},
                    identity_semantics={},
                    auth_ref=None,
                    rate_limit_policy={},
                    access_rights={},
                    retention_mode="durable_managed",
                    schedule_policy={},
                    schema_version="1",
                    definition_hash=uuid4().hex,
                    managed_by="test",
                    enabled=True,
                    updated_at=NOW,
                )
            )
            await session.flush()
            observation_id = str(uuid4())
            session.add(
                ObservationModel(
                    observation_id=observation_id,
                    source_id=source_id,
                    acquisition_run_id=None,
                    acquisition_trigger="replay",
                    external_object_id="vendor-advisory-92929",
                    external_revision="rev-1",
                    canonical_url="https://example.invalid/advisory/92929",
                    published_at=NOW,
                    updated_at=NOW,
                    observed_at=NOW,
                    content_hash=uuid4().hex + uuid4().hex,
                    request_metadata={},
                    request_metadata_captured=True,
                    idempotency_key=uuid4().hex + uuid4().hex,
                    created_at=NOW,
                )
            )
            await session.flush()
            evidence_id = str(uuid4())
            session.add(
                EvidenceLinkModel(
                    evidence_link_id=evidence_id,
                    target_kind="object",
                    target_id=object_id,
                    observation_id=observation_id,
                    artifact_id=None,
                    locator={"kind": "fixture", "field": "advisory"},
                    locator_hash=uuid4().hex + uuid4().hex,
                )
            )
            await session.flush()

            case = await CaseService(now=lambda: NOW).create(
                session,
                task_signature="materialize-evidence-world",
                target_object_ids=[object_id],
                goal="Materialize evidence world refs.",
                initial_knowledge_revision=revision.revision,
            )
            need = await service.open_evidence_need(
                session,
                case_id=case.case_id,
                base_case_revision=0,
                need_id=str(uuid4()),
                proposition_or_question="Need vendor evidence",
                purpose="verify",
                target_objects=[object_id],
            )
            run_id = str(uuid4())
            contract = build_investigation_contract(
                task_contract_id=f"verify:{run_id}",
                principal="user:test",
                task_kind=TaskKind.VERIFY_VERSION_FIX,
                case_id=case.case_id,
                target_object_ids=[object_id],
                required_need_ids=[need.need.need_id],
                policy_revision="policy-v1",
            )
            manifest = ContextManifest(
                context_id=f"context:{run_id}",
                context_revision=1,
                task_contract_ref=f"{contract.task_contract_id}@1",
                role_ref="InvestigationRole@1",
                case_ref=case.case_id,
                knowledge_revision=revision.revision,
                investigation_state_ref=f"case:{case.case_id}@1",
                object_refs=[object_id],
                evidence_refs=[evidence_id],
                policy_context_ref="policy-context:v1",
                capability_envelope_ref="capability:investigation:v1",
                budget_ref=f"budget:{run_id}",
            )
            await create_task_run(
                session,
                contract=contract,
                manifest=manifest,
                role=canonical_roles()["InvestigationRole"],
                execution_envelope_ref=f"execution:{run_id}",
                stream_name="secfusion:task-events:test",
                case_id=case.case_id,
                run_id=run_id,
                now=NOW,
            )

        async with factory() as session:
            assembly = await materialize_investigation_prompt(
                session,
                task_run_id=run_id,
                materializer=ContextMaterializer(
                    platform_invariant_revision="platform-v1",
                    platform_invariant={"authority": "runtime gates"},
                ),
                state_service=service,
            )
            by_kind = {fragment.kind: fragment for fragment in assembly.fragments}
            assert by_kind["knowledge_object"].source_ref == object_id
            assert by_kind["evidence_reference"].source_ref == evidence_id
            evidence_content = by_kind["evidence_reference"].content
            assert isinstance(evidence_content, dict)
            assert evidence_content["source_role"] == "primary"
            assert by_kind["investigation_state"].source_ref == f"case:{case.case_id}@1"
            request = assembly.to_model_request()
            assert "CVE-2026-92929" in str(request.data)
            assert "vendor-advisory-92929" in str(request.data)

        async with factory() as session, session.begin():
            session.add(KnowledgeRevisionModel(committed_at=NOW))

        async with factory() as session:
            with pytest.raises(ValueError, match="knowledge_revision is stale"):
                await materialize_investigation_prompt(
                    session,
                    task_run_id=run_id,
                    materializer=ContextMaterializer(
                        platform_invariant_revision="platform-v1",
                        platform_invariant={"authority": "runtime gates"},
                    ),
                    state_service=service,
                )
    finally:
        await engine.dispose()
