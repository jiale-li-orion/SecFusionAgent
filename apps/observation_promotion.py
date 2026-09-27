from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.perception_execution import ObservationPromotionBinding
from packages.intelligence.ingestion.attachment import EvidenceAttachmentService
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.retrieval.operators import EvidenceRetrievalOperator
from packages.investigation.perception.contracts import PerceptionStepResult
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.runtime.artifacts import RuntimeArtifactService
from packages.runtime.capability.broker import CapabilityInvocationOutcome
from packages.runtime.policy.contracts import Authorization, PolicyDecisionPoint, PolicyRequest
from packages.runtime.policy.engine import StaticPolicyEngine
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope, SourceDefinition
from packages.task_runtime.contracts.models import TaskContract
from packages.task_runtime.storage.service import get_task_run


class ObservationPromotionService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        policy_engine: StaticPolicyEngine,
        runtime_artifacts: RuntimeArtifactService,
        evidence_ingress: EvidenceIngress,
        source_definitions: dict[str, SourceDefinition],
        *,
        attachment_service: EvidenceAttachmentService | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._policy = policy_engine
        self._runtime_artifacts = runtime_artifacts
        self._evidence_ingress = evidence_ingress
        self._sources = dict(source_definitions)
        self._attachment = attachment_service or EvidenceAttachmentService()
        self._evidence_retrieval = EvidenceRetrievalOperator()

    async def promote(
        self,
        *,
        task_run_id: str,
        task: TaskContract,
        outcome: CapabilityInvocationOutcome,
        binding: ObservationPromotionBinding,
    ) -> PerceptionStepResult:
        observation = outcome.observation
        if observation is None:
            return PerceptionStepResult(unresolved=["observation_promotion_missing_observation"])
        if task.policy_revision != self._policy.policy_revision:
            return PerceptionStepResult(
                unresolved=["observation_promotion_policy_revision_mismatch"]
            )
        policy_request = PolicyRequest(
            decision_point=PolicyDecisionPoint.OBSERVATION_PROMOTION,
            principal=task.principal,
            action="promote_observation",
            resource=f"source:{binding.source_id}",
            context={
                "task_contract_id": task.task_contract_id,
                "task_run_id": task_run_id,
                "capability_id": observation.capability_id,
                "observation_id": observation.observation_id,
                "target_kind": binding.target_kind,
                "target_id": binding.target_id,
                "trust_label": observation.trust_label,
            },
        )
        decision = self._policy.evaluate(policy_request)
        decision_ref = self._policy.decision_ref(policy_request, decision)
        if decision.authorization is not Authorization.PERMIT:
            return PerceptionStepResult(
                unresolved=[f"observation_promotion_{decision.authorization.value}"],
                cost={"promotion_policy_ref": decision_ref},
            )
        required = {item.kind for item in [*decision.constraints, *decision.obligations]}
        if not required <= binding.fulfilled_obligation_kinds:
            missing = ",".join(sorted(required - binding.fulfilled_obligation_kinds))
            return PerceptionStepResult(
                unresolved=[f"observation_promotion_obligation_unsatisfied:{missing}"],
                cost={"promotion_policy_ref": decision_ref},
            )

        source = self._sources.get(binding.source_id)
        if source is None:
            return PerceptionStepResult(
                unresolved=[f"observation_promotion_source_unknown:{binding.source_id}"],
                cost={"promotion_policy_ref": decision_ref},
            )
        provenance = observation.provenance
        acquisition_run_id = _required_string(provenance, "acquisition_run_id")
        external_object_id = _required_string(provenance, "external_object_id")
        external_revision = _optional_string(provenance.get("external_revision"))
        canonical_url = _optional_string(provenance.get("canonical_url"))
        published_at = _optional_datetime(provenance.get("published_at"))
        updated_at = _optional_datetime(provenance.get("updated_at"))

        async with self._session_factory() as session, session.begin():
            run = await get_task_run(session, task_run_id)
            acquisition = await session.get(AcquisitionRunModel, acquisition_run_id)
            if acquisition is None:
                raise LookupError(
                    f"observation promotion acquisition run not found: {acquisition_run_id}"
                )
            if acquisition.source_id != source.source_id:
                raise ValueError("observation promotion source/acquisition lineage mismatch")
            runtime_artifact = await self._runtime_artifacts.get(
                session,
                observation.raw_result_ref,
            )
            if runtime_artifact.execution_id != run.execution_envelope_ref:
                raise PermissionError(
                    "observation promotion runtime artifact escapes TaskRun execution"
                )
            body = await self._runtime_artifacts.read(session, observation.raw_result_ref)
            envelope = IngestEnvelope.for_binary_payload(
                acquisition_run_id=acquisition_run_id,
                trigger=AcquisitionTrigger(acquisition.trigger),
                source_id=source.source_id,
                external_object_id=external_object_id,
                body=body,
                media_type=runtime_artifact.media_type,
                canonical_url=canonical_url,
                published_at=published_at,
                updated_at=updated_at,
                external_revision=external_revision,
                request_metadata={
                    "promoted_from": "ephemeral_observation",
                    "ephemeral_observation_id": observation.observation_id,
                    "capability_id": observation.capability_id,
                    "promotion_policy_ref": decision_ref,
                    "provenance": cast(JsonValue, provenance),
                },
                observed_at=observation.observed_at,
            )
            ack = await self._evidence_ingress.accept(session, source, envelope)
            attached = await self._attachment.attach(
                session,
                observation_id=ack.observation_id,
                artifact_id=ack.artifact_id,
                target_kind=binding.target_kind,
                target_id=binding.target_id,
                locator={
                    **binding.locator,
                    "ephemeral_observation_id": observation.observation_id,
                    "capability_id": observation.capability_id,
                },
            )
            candidates = await self._evidence_retrieval.for_target(
                session,
                target_kind=binding.target_kind,
                target_id=binding.target_id,
            )
            promoted = next(
                (item for item in candidates if item.evidence_ref == attached.evidence_link_id),
                None,
            )
            if promoted is None:
                raise RuntimeError("promoted evidence link is not retrievable")
        return PerceptionStepResult(
            candidates=[promoted],
            cost={
                "promotion_calls": 1,
                "promotion_policy_ref": decision_ref,
                "durable_observation_id": ack.observation_id,
            },
        )


def _required_string(value: dict[str, JsonValue], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise ValueError(f"ephemeral observation provenance missing {key}")
    return result


def _optional_string(value: JsonValue | None) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_datetime(value: JsonValue | None) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
