from __future__ import annotations

import json
from typing import cast
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, JsonValue

from packages.task_runtime.a2a.contracts import (
    A2AArtifact,
    A2AInboundMessage,
    A2APart,
    A2AStreamResponse,
    A2ATask,
    A2ATaskArtifactUpdateEvent,
    A2ATaskState,
    A2ATaskStatus,
    A2ATaskStatusUpdateEvent,
)
from packages.task_runtime.context.handoff import TaskResultEnvelope
from packages.task_runtime.contracts.models import (
    ContextManifest,
    TaskContract,
    TaskEvent,
    TaskEventType,
    TaskIntent,
    TaskRun,
    TaskRunStatus,
)


class ImportedA2AIntent(BaseModel):
    intent: TaskIntent
    external_context_id: str | None = None
    external_task_id: str | None = None
    external_message_id: str


class A2AAdapter:
    """Pure interoperability mapping; A2A Context never becomes internal Context storage."""

    def export_task(
        self,
        run: TaskRun,
        contract: TaskContract,
        context: ContextManifest,
        *,
        artifacts: list[A2AArtifact] | None = None,
    ) -> A2ATask:
        return A2ATask(
            id=run.run_id,
            contextId=_external_context_id(run, context),
            status=A2ATaskStatus(state=_task_state(run.status)),
            artifacts=list(artifacts or []),
            metadata={
                "secfusion": {
                    "internalStatus": run.status.value,
                    "roleRef": f"{run.role_id}@{run.role_version}",
                    "parentRunId": run.parent_run_id,
                    "taskContract": contract.model_dump(mode="json"),
                    "contextManifestRef": run.context_manifest_ref,
                    "policyContextRef": context.policy_context_ref,
                    "capabilityEnvelopeRef": context.capability_envelope_ref,
                }
            },
        )

    def export_result(self, result: TaskResultEnvelope) -> A2AArtifact:
        return A2AArtifact(
            artifactId=result.result_id,
            name="SecFusionAgent TaskResult",
            parts=[
                A2APart(
                    data=cast(
                        JsonValue,
                        {
                            "payloadRef": result.payload_ref,
                            "evidenceRefs": result.evidence_refs,
                            "stateRefs": result.state_refs,
                            "artifactRefs": result.artifact_refs,
                            "basedOnContext": {
                                "id": result.based_on_context_id,
                                "revision": result.based_on_context_revision,
                            },
                        },
                    ),
                    mediaType="application/json",
                )
            ],
            metadata={
                "secfusion": {
                    "sender": result.sender,
                    "taskRunId": result.task_run_id,
                    "parentRunId": result.parent_run_id,
                    "status": result.status.value,
                }
            },
        )

    def export_event(self, event: TaskEvent, *, context_id: str) -> A2AStreamResponse:
        if event.event_type is TaskEventType.ARTIFACT_PRODUCED:
            artifact = A2AArtifact(
                artifactId=f"task-event:{event.event_id}",
                parts=[
                    A2APart(
                        data={"payloadRef": event.payload_ref},
                        mediaType="application/json",
                    )
                ],
                metadata={"secfusion": {"eventId": event.event_id, "seq": event.seq}},
            )
            return A2AStreamResponse(
                artifactUpdate=A2ATaskArtifactUpdateEvent(
                    taskId=event.task_run_id,
                    contextId=context_id,
                    artifact=artifact,
                )
            )
        return A2AStreamResponse(
            statusUpdate=A2ATaskStatusUpdateEvent(
                taskId=event.task_run_id,
                contextId=context_id,
                status=A2ATaskStatus(
                    state=_event_state(event.event_type),
                    timestamp=event.emitted_at,
                ),
                metadata={
                    "secfusion": {
                        "eventId": event.event_id,
                        "eventType": event.event_type.value,
                        "seq": event.seq,
                        "payloadRef": event.payload_ref,
                    }
                },
            )
        )

    def export_push(self, event: TaskEvent, *, context_id: str) -> A2AStreamResponse:
        return self.export_event(event, context_id=context_id)

    def import_message(self, message: A2AInboundMessage) -> ImportedA2AIntent:
        if message.role not in {"ROLE_USER", "user"}:
            raise ValueError("only user A2A messages can create TaskIntent")
        text_parts = [
            part.text.strip() for part in message.parts if part.text and part.text.strip()
        ]
        if text_parts:
            raw_request = "\n".join(text_parts)
        else:
            data_parts = [part.data for part in message.parts if part.data is not None]
            if not data_parts:
                raise ValueError("A2A message contains no task request content")
            raw_request = json.dumps(data_parts, ensure_ascii=False, sort_keys=True)
        return ImportedA2AIntent(
            intent=TaskIntent(raw_request=raw_request),
            external_context_id=message.context_id,
            external_task_id=message.task_id,
            external_message_id=message.message_id,
        )


def _external_context_id(run: TaskRun, context: ContextManifest) -> str:
    stable_scope = run.case_id or context.parent_context_id or context.context_id
    return str(uuid5(NAMESPACE_URL, f"secfusion:a2a-context:{stable_scope}"))


def _task_state(status: TaskRunStatus) -> A2ATaskState:
    mapping = {
        TaskRunStatus.SUBMITTED: A2ATaskState.SUBMITTED,
        TaskRunStatus.QUEUED: A2ATaskState.WORKING,
        TaskRunStatus.RUNNING: A2ATaskState.WORKING,
        TaskRunStatus.WAITING_INPUT: A2ATaskState.INPUT_REQUIRED,
        TaskRunStatus.WAITING_DEPENDENCY: A2ATaskState.WORKING,
        TaskRunStatus.BLOCKED: A2ATaskState.FAILED,
        TaskRunStatus.COMPLETED: A2ATaskState.COMPLETED,
        TaskRunStatus.FAILED: A2ATaskState.FAILED,
        TaskRunStatus.CANCELLED: A2ATaskState.CANCELED,
        TaskRunStatus.TIMED_OUT: A2ATaskState.FAILED,
    }
    return mapping[status]


def _event_state(event_type: TaskEventType) -> A2ATaskState:
    mapping = {
        TaskEventType.TASK_CREATED: A2ATaskState.SUBMITTED,
        TaskEventType.TASK_STARTED: A2ATaskState.WORKING,
        TaskEventType.NEED_INPUT: A2ATaskState.INPUT_REQUIRED,
        TaskEventType.TASK_COMPLETED: A2ATaskState.COMPLETED,
        TaskEventType.TASK_FAILED: A2ATaskState.FAILED,
        TaskEventType.TASK_CANCELED: A2ATaskState.CANCELED,
        TaskEventType.TASK_BLOCKED: A2ATaskState.FAILED,
    }
    return mapping.get(event_type, A2ATaskState.WORKING)
