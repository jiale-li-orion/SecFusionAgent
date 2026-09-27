from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, JsonValue, model_validator


class EphemeralObservation(BaseModel):
    observation_id: str
    request_id: str
    capability_id: str
    source: str
    provenance: dict[str, JsonValue] = Field(default_factory=dict)
    observed_at: datetime
    raw_result_ref: str
    extracted_candidates: list[JsonValue] = Field(default_factory=list)
    trust_label: str
    ttl_seconds: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_observation(self) -> EphemeralObservation:
        if self.observed_at.tzinfo is None:
            raise ValueError("EphemeralObservation observed_at must be timezone-aware")
        for value, label in (
            (self.observation_id, "observation_id"),
            (self.request_id, "request_id"),
            (self.capability_id, "capability_id"),
            (self.source, "source"),
            (self.raw_result_ref, "raw_result_ref"),
            (self.trust_label, "trust_label"),
        ):
            if not value.strip():
                raise ValueError(f"EphemeralObservation {label} cannot be empty")
        return self
