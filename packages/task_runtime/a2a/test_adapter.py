from __future__ import annotations

from datetime import UTC, datetime

from packages.task_runtime.a2a.adapter import A2AAdapter
from packages.task_runtime.a2a.contracts import (
    A2AInboundMessage,
    A2AMessage,
    A2APart,
    A2AStreamResponse,
    A2ATaskArtifactUpdateEvent,
    A2ATaskState,
    A2ATaskStatusUpdateEvent,
)
from packages.task_runtime.context.contracts import ContextDependencySet
from packages.task_runtime.context.handoff import TaskResultEnvelope
from packages.task_runtime.contracts.models import (
    ContextManifest,
    DelegationCeiling,
    EffectCeiling,
    TaskContract,
    TaskEvent,
    TaskEventType,
    TaskKind,
    TaskRun,
    TaskRunStatus,
)

NOW = datetime(2026, 9, 27, 18, 30, tzinfo=UTC)


def _contract() -> TaskContract:
    return TaskContract(
        task_contract_id="contract-1",
        contract_revision=1,
        principal="user:test",
        task_kind=TaskKind.VERIFY_VERSION_FIX,
        target_resources=["object:vuln-1"],
        desired_state={"predicate": "fix_boundary_resolved"},
        evidence_contract={"required_source_roles": ["primary"]},
        output_contract={"result_type": "decision"},
        temporal_contract={"scope": "current"},
        effect_ceiling=EffectCeiling.READ_ONLY,
        delegation_ceiling=DelegationCeiling(),
        completion_predicate={"type": "test"},
        policy_revision="policy-v1",
    )


def _context() -> ContextManifest:
    return ContextManifest(
        context_id="internal-context-secret",
        context_revision=3,
        task_contract_ref="contract-1@1",
        role_ref="InvestigationRole@1",
        case_ref="case-1",
        knowledge_revision=9,
        investigation_state_ref="case:case-1@4",
        object_refs=["vuln-1"],
        policy_context_ref="policy-context:policy-v1",
        capability_envelope_ref="capability:verify:v1",
        budget_ref="budget:run-1",
    )


def _run(status: TaskRunStatus = TaskRunStatus.RUNNING) -> TaskRun:
    return TaskRun(
        run_id="run-1",
        task_contract_id="contract-1",
        case_id="case-1",
        role_id="InvestigationRole",
        role_version="1",
        context_manifest_ref="internal-context-secret@3",
        status=status,
        base_context_revision=3,
        execution_envelope_ref="execution:run-1",
    )


def test_export_task_uses_external_context_identity_and_extension_metadata() -> None:
    task = A2AAdapter().export_task(_run(), _contract(), _context())
    assert task.id == "run-1"
    assert task.context_id is not None
    assert task.context_id != "internal-context-secret"
    assert task.status.state is A2ATaskState.WORKING
    secfusion = task.metadata["secfusion"]
    assert isinstance(secfusion, dict)
    assert secfusion["contextManifestRef"] == "internal-context-secret@3"
    assert secfusion["capabilityEnvelopeRef"] == "capability:verify:v1"


def test_export_result_maps_typed_task_result_to_artifact_data_part() -> None:
    artifact = A2AAdapter().export_result(
        TaskResultEnvelope(
            result_id="result-1",
            sender="InvestigationRole@1",
            task_run_id="run-1",
            status=TaskRunStatus.COMPLETED,
            based_on_context_id="internal-context-secret",
            based_on_context_revision=3,
            payload_ref="decision:123",
            evidence_refs=["evidence:1"],
            state_refs=["case:case-1@4"],
            dependencies=ContextDependencySet(),
        )
    )
    assert artifact.artifact_id == "result-1"
    assert artifact.parts[0].data == {
        "payloadRef": "decision:123",
        "evidenceRefs": ["evidence:1"],
        "stateRefs": ["case:case-1@4"],
        "artifactRefs": [],
        "basedOnContext": {"id": "internal-context-secret", "revision": 3},
    }


def test_task_events_map_to_status_or_artifact_stream_updates() -> None:
    adapter = A2AAdapter()
    completed = adapter.export_event(
        TaskEvent(
            event_id="event-1",
            task_run_id="run-1",
            seq=5,
            event_type=TaskEventType.TASK_COMPLETED,
            producer="InvestigationRole",
            base_context_revision=3,
            payload_ref="result:1",
            idempotency_key="complete:1",
            emitted_at=NOW,
        ),
        context_id="external-context",
    )
    assert isinstance(completed.status_update, A2ATaskStatusUpdateEvent)
    assert completed.status_update.status.state is A2ATaskState.COMPLETED

    artifact = adapter.export_event(
        TaskEvent(
            event_id="event-2",
            task_run_id="run-1",
            seq=4,
            event_type=TaskEventType.ARTIFACT_PRODUCED,
            producer="SandboxBroker",
            base_context_revision=3,
            payload_ref="artifact:runtime-1",
            idempotency_key="artifact:1",
            emitted_at=NOW,
        ),
        context_id="external-context",
    )
    assert isinstance(artifact.artifact_update, A2ATaskArtifactUpdateEvent)
    assert artifact.artifact_update.artifact.parts[0].data == {"payloadRef": "artifact:runtime-1"}


def test_import_message_keeps_a2a_context_outside_internal_context_refs() -> None:
    imported = A2AAdapter().import_message(
        A2AInboundMessage(
            messageId="message-1",
            contextId="remote-context-1",
            taskId="remote-task-1",
            role="ROLE_USER",
            parts=[A2APart(text="Verify whether v1.2.3 contains the fix.")],
        )
    )
    assert imported.intent.raw_request == "Verify whether v1.2.3 contains the fix."
    assert imported.intent.context_refs == []
    assert imported.external_context_id == "remote-context-1"
    assert imported.external_task_id == "remote-task-1"


def test_task_status_mapping_preserves_internal_blocked_detail_in_metadata() -> None:
    task = A2AAdapter().export_task(
        _run(TaskRunStatus.BLOCKED),
        _contract(),
        _context(),
    )
    assert task.status.state is A2ATaskState.FAILED
    secfusion = task.metadata["secfusion"]
    assert isinstance(secfusion, dict)
    assert secfusion["internalStatus"] == "blocked"


def test_a2a_json_view_uses_protocol_field_aliases() -> None:
    payload = (
        A2AAdapter()
        .export_task(_run(), _contract(), _context())
        .model_dump(
            mode="json",
            by_alias=True,
        )
    )
    assert "contextId" in payload
    assert "context_id" not in payload


def test_stream_response_accepts_message_as_protocol_one_of() -> None:
    response = A2AStreamResponse(
        message=A2AMessage(
            messageId="message-1",
            contextId="context-1",
            role="ROLE_AGENT",
            parts=[A2APart(text="partial response")],
        )
    )
    payload = response.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert list(payload) == ["message"]
    assert payload["message"]["messageId"] == "message-1"
