from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, JsonValue


class NormativeEvidence(BaseModel):
    quote: str = Field(min_length=1)


class NormativeDocumentFactProposal(BaseModel):
    field: Literal[
        "issuer",
        "jurisdiction",
        "document_type",
        "binding_status",
        "status",
        "effective_date",
        "expiry_date",
        "supersedes_ref",
        "amends_ref",
        "reference",
    ]
    value: str = Field(min_length=1)
    evidence: NormativeEvidence


class NormativeRequirementProposal(BaseModel):
    local_id: str = Field(min_length=1)
    source_clause: str | None = None
    modality: Literal[
        "obligation",
        "prohibition",
        "permission",
        "recommendation",
        "guidance",
    ]
    subject: str = Field(min_length=1)
    action: str = Field(min_length=1)
    object: str = Field(min_length=1)
    condition: str | None = None
    exception: str | None = None
    jurisdiction: str | None = None
    applicability: dict[str, JsonValue] = Field(default_factory=dict)
    valid_from: date | None = None
    valid_to: date | None = None
    risk_mapping: list[str] = Field(default_factory=list)
    evidence: NormativeEvidence


class NormativeControlProposal(BaseModel):
    local_id: str = Field(min_length=1)
    canonical_key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str | None = None
    evidence: NormativeEvidence


class RequirementControlProposal(BaseModel):
    requirement_local_id: str = Field(min_length=1)
    control_local_id: str = Field(min_length=1)
    relation_type: Literal[
        "supports",
        "implements",
        "partially-satisfies",
        "mitigates",
    ]
    evidence: NormativeEvidence


class NormativeChunkExtraction(BaseModel):
    document_facts: list[NormativeDocumentFactProposal] = Field(default_factory=list)
    requirements: list[NormativeRequirementProposal] = Field(default_factory=list)
    controls: list[NormativeControlProposal] = Field(default_factory=list)
    control_mappings: list[RequirementControlProposal] = Field(default_factory=list)


class NormativeExtractionResult(BaseModel):
    document_revision_id: str
    normative_document_id: str
    normative_revision_id: str
    processing_run_id: str
    requirement_ids: list[str] = Field(default_factory=list)
    control_ids: list[str] = Field(default_factory=list)
    mapping_ids: list[str] = Field(default_factory=list)
    replay: bool = False
