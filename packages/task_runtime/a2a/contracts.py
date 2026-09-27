from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class A2ATaskState(StrEnum):
    UNSPECIFIED = "TASK_STATE_UNSPECIFIED"
    SUBMITTED = "TASK_STATE_SUBMITTED"
    WORKING = "TASK_STATE_WORKING"
    COMPLETED = "TASK_STATE_COMPLETED"
    FAILED = "TASK_STATE_FAILED"
    CANCELED = "TASK_STATE_CANCELED"
    INPUT_REQUIRED = "TASK_STATE_INPUT_REQUIRED"
    AUTH_REQUIRED = "TASK_STATE_AUTH_REQUIRED"
    REJECTED = "TASK_STATE_REJECTED"


class A2APart(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    text: str | None = None
    raw: bytes | None = None
    url: str | None = None
    data: JsonValue | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    filename: str | None = None
    media_type: str | None = Field(default=None, alias="mediaType")

    @model_validator(mode="after")
    def exactly_one_content(self) -> A2APart:
        count = sum(value is not None for value in (self.text, self.raw, self.url, self.data))
        if count != 1:
            raise ValueError("A2A Part requires exactly one text/raw/url/data content field")
        return self


class A2AMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message_id: str = Field(alias="messageId")
    context_id: str | None = Field(default=None, alias="contextId")
    task_id: str | None = Field(default=None, alias="taskId")
    role: str
    parts: list[A2APart] = Field(min_length=1)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    reference_task_ids: list[str] = Field(default_factory=list, alias="referenceTaskIds")


class A2AArtifact(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    artifact_id: str = Field(alias="artifactId")
    name: str | None = None
    description: str | None = None
    parts: list[A2APart] = Field(min_length=1)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    extensions: list[str] = Field(default_factory=list)


class A2ATaskStatus(BaseModel):
    state: A2ATaskState
    timestamp: datetime | None = None


class A2ATask(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    context_id: str | None = Field(default=None, alias="contextId")
    status: A2ATaskStatus
    artifacts: list[A2AArtifact] = Field(default_factory=list)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class A2ATaskStatusUpdateEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(alias="taskId")
    context_id: str = Field(alias="contextId")
    status: A2ATaskStatus
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class A2ATaskArtifactUpdateEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(alias="taskId")
    context_id: str = Field(alias="contextId")
    artifact: A2AArtifact
    append: bool = False
    last_chunk: bool = Field(default=False, alias="lastChunk")
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class A2AStreamResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task: A2ATask | None = None
    message: A2AMessage | None = None
    status_update: A2ATaskStatusUpdateEvent | None = Field(default=None, alias="statusUpdate")
    artifact_update: A2ATaskArtifactUpdateEvent | None = Field(
        default=None,
        alias="artifactUpdate",
    )

    @model_validator(mode="after")
    def exactly_one_payload(self) -> A2AStreamResponse:
        payloads = (self.task, self.message, self.status_update, self.artifact_update)
        if sum(item is not None for item in payloads) != 1:
            raise ValueError("A2A StreamResponse requires exactly one payload")
        return self


A2AInboundMessage = A2AMessage
