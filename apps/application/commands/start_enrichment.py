from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.application.errors import (
    ApplicationError,
    PermissionDeniedError,
    ResourceNotFoundError,
    RevisionConflictError,
)
from apps.application.views.enrichment import ProductEnrichmentRunPage, ProductEnrichmentRunView
from apps.task_admission import create_task_contract_service
from packages.enrichment.runtime.role import EnrichmentTaskDesiredState
from packages.enrichment.runtime.state import EnrichmentStateBuilder
from packages.intelligence.knowledge.read import get_object_by_id
from packages.intelligence.knowledge.vocabulary import EnrichmentDimension
from packages.intelligence.storage.knowledge_models import ObjectModel
from packages.runtime.budget import BudgetGovernor, BudgetLimits
from packages.runtime.execution.service import ExecutionRunService
from packages.runtime.policy.loader import load_runtime_policy
from packages.task_runtime.admission import TaskAdmissionDenied, TaskAdmissionRequest
from packages.task_runtime.contracts.execution import ExecutionEnvelope
from packages.task_runtime.contracts.models import (
    ContextManifest,
    TaskIntent,
    TaskKind,
    TaskRunStatus,
)
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.models import TaskContractVersionModel, TaskRunModel
from packages.task_runtime.storage.service import (
    create_task_run,
    get_task_contract_for_run,
    transition_task_run,
)


class EnrichmentIdempotencyConflict(ApplicationError):
    code = "idempotency_conflict"


class StartEnrichmentCommand(BaseModel):
    principal: str = Field(min_length=1)
    request_id: str
    trace_id: str | None = None
    object_id: str
    idempotency_key: str = Field(min_length=1, max_length=128)
    dimensions: list[EnrichmentDimension] = Field(min_length=1, max_length=12)
    expected_world_revision: int | None = Field(default=None, ge=0)


class StartEnrichmentUseCase:
    """Admit a bounded M3 task; operators remain owned by the existing EnrichmentRole."""

    def __init__(self, *, policy_path: Path, task_event_stream_name: str) -> None:
        self._policy_path = policy_path
        self._stream_name = task_event_stream_name

    async def execute(
        self, session: AsyncSession, command: StartEnrichmentCommand
    ) -> ProductEnrichmentRunView:
        # Serialize public submissions for a target before looking up the durable replay identity.
        target = await session.scalar(
            select(ObjectModel).where(ObjectModel.object_id == command.object_id).with_for_update()
        )
        if target is None:
            raise ResourceNotFoundError("intelligence object not found")
        if target.object_type != "Vulnerability" or target.superseded_revision is not None:
            raise ValueError("EnrichmentRole accepts current Vulnerability objects only")
        view = await get_object_by_id(session, target.object_id)
        assert view is not None
        cves = sorted(set(view.external_identifiers.get("cve", [])))
        if len(cves) != 1 or not re.fullmatch(r"CVE-\d{4}-\d{4,}", cves[0], re.IGNORECASE):
            raise ValueError("EnrichmentRole requires one actual CVE bound to the Vulnerability")
        cve_id = cves[0].upper()
        dimensions = sorted(set(command.dimensions), key=lambda item: item.value)
        digest = sha256(
            json.dumps(
                {
                    "object_id": command.object_id,
                    "dimensions": [item.value for item in dimensions],
                    "expected_world_revision": command.expected_world_revision,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        run_id = str(
            uuid5(
                NAMESPACE_URL,
                json.dumps(
                    [
                        "product-enrichment",
                        command.principal,
                        command.object_id,
                        command.idempotency_key,
                    ]
                ),
            )
        )
        existing = await session.get(TaskRunModel, run_id)
        execution_service = ExecutionRunService()
        if existing is not None:
            envelope = await execution_service.get(session, existing.execution_envelope_ref)
            if envelope.trace_context.get("request_digest") != digest:
                raise EnrichmentIdempotencyConflict("Idempotency-Key was used with another request")
            return await _run_view(session, existing, replayed=True)

        snapshot = await EnrichmentStateBuilder().build(
            session, command.object_id, materialize=False
        )
        if (
            command.expected_world_revision is not None
            and command.expected_world_revision != snapshot.world_revision
        ):
            raise RevisionConflictError(
                "enrichment world revision changed",
                context={
                    "expected_world_revision": command.expected_world_revision,
                    "world_revision": snapshot.world_revision,
                },
            )
        policy = load_runtime_policy(self._policy_path)
        try:
            admission = await create_task_contract_service(policy).admit(
                TaskAdmissionRequest(
                    intent=TaskIntent(
                        trigger_ref=f"product-request:{command.request_id}",
                        parsed_identifiers=[cve_id],
                        candidate_task_kind=TaskKind.ENRICHMENT,
                        candidate_targets=[command.object_id, cve_id],
                        requested_actions=["enrich_vulnerability"],
                    ),
                    principal=command.principal,
                    policy_revision=policy.policy_revision,
                    task_contract_id=f"product-enrichment:{run_id}",
                    binding_context={
                        "target_object_id": command.object_id,
                        "cve_id": cve_id,
                        "required_dimensions": [item.value for item in dimensions],
                        "refresh_dimensions": [item.value for item in dimensions],
                    },
                )
            )
        except TaskAdmissionDenied as exc:
            raise PermissionDeniedError(str(exc)) from exc
        role = canonical_roles()["EnrichmentRole"]
        budget_ref = f"budget:{run_id}"
        execution_id = f"execution:{run_id}"
        await create_task_run(
            session,
            contract=admission.contract,
            manifest=ContextManifest(
                context_id=f"context:{run_id}",
                context_revision=1,
                task_contract_ref=f"{admission.contract.task_contract_id}@1",
                role_ref="EnrichmentRole@1",
                knowledge_revision=snapshot.world_revision,
                object_refs=[command.object_id],
                policy_context_ref=f"policy-context:{policy.policy_revision}",
                capability_envelope_ref="capability:enrichment:v1",
                budget_ref=budget_ref,
            ),
            role=role,
            execution_envelope_ref=execution_id,
            run_id=run_id,
            stream_name=self._stream_name,
            producer="product-enrichment",
        )
        await BudgetGovernor().create_account(
            session,
            account_id=budget_ref,
            task_run_id=run_id,
            limits=BudgetLimits(quantities={"tool_calls": Decimal(16)}),
        )
        await execution_service.create(
            session,
            ExecutionEnvelope(
                execution_id=execution_id,
                task_contract_id=admission.contract.task_contract_id,
                task_run_id=run_id,
                role_revision="EnrichmentRole@1",
                context_manifest_revision=1,
                execution_profile=role.default_execution_profile,
                deadline_at=datetime.now(UTC) + timedelta(seconds=300),
                budget_ref=budget_ref,
                policy_revision=policy.policy_revision,
                identity_scope=["public"],
                network_policy="public-sources",
                side_effect_policy="internal-state-only",
                sandbox_profile_revision="process_restricted@1",
                trace_context={
                    "surface": "product-enrichment",
                    "request_id": command.request_id,
                    "request_digest": digest,
                    "trace_id": command.trace_id,
                },
            ),
        )
        await transition_task_run(
            session,
            run_id=run_id,
            target=TaskRunStatus.QUEUED,
            payload_ref="queue:product-enrichment",
            idempotency_key=f"queued:{run_id}",
            stream_name=self._stream_name,
            producer="product-enrichment",
        )
        await session.commit()
        run = await session.get(TaskRunModel, run_id)
        assert run is not None
        return await _run_view(session, run)


async def list_product_enrichment_runs(
    session: AsyncSession, object_id: str, *, principal: str
) -> ProductEnrichmentRunPage:
    if await session.get(ObjectModel, object_id) is None:
        raise ResourceNotFoundError("intelligence object not found")
    rows = await session.scalars(
        select(TaskRunModel)
        .join(
            TaskContractVersionModel,
            TaskContractVersionModel.task_contract_version_id
            == TaskRunModel.task_contract_version_id,
        )
        .where(
            TaskRunModel.role_id == "EnrichmentRole",
            TaskRunModel.task_contract_id.like("product-enrichment:%"),
            TaskContractVersionModel.principal == principal,
            TaskContractVersionModel.contract_json["desired_state"]["target_object_id"].as_string()
            == object_id,
        )
        .order_by(TaskRunModel.created_at.desc())
        .limit(5)
    )
    return ProductEnrichmentRunPage(items=[await _run_view(session, row) for row in rows])


async def _run_view(
    session: AsyncSession, run: TaskRunModel, *, replayed: bool = False
) -> ProductEnrichmentRunView:
    contract = await get_task_contract_for_run(session, run.run_id)
    desired = EnrichmentTaskDesiredState.model_validate(contract.desired_state)
    return ProductEnrichmentRunView(
        object_id=desired.target_object_id,
        cve_id=desired.cve_id,
        task_run_id=run.run_id,
        status=run.status,
        required_dimensions=[item.value for item in desired.required_dimensions],
        stop_reason=run.stop_reason,
        task_url=f"/api/v1/tasks/{run.run_id}",
        state_url=f"/api/v1/intelligence/objects/{desired.target_object_id}/enrichment",
        replayed=replayed,
    )
