from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, JsonValue

from packages.sources.contracts import IngestEnvelope


class AssetObservation(BaseModel):
    source_id: str
    provider: str
    acquisition_run_id: str
    query: str
    observed_at: datetime
    external_object_id: str
    external_revision: str | None = None
    ip: str
    port: int
    transport: str
    hostnames: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    product: str | None = None
    version: str | None = None
    organization: str | None = None
    isp: str | None = None
    asn: str | None = None
    cpe: list[str] = Field(default_factory=list)
    location: dict[str, JsonValue] = Field(default_factory=dict)


class AssetObservationResult(BaseModel):
    observation: AssetObservation
    envelope: IngestEnvelope
