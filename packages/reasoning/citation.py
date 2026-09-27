from __future__ import annotations

from pydantic import BaseModel, Field, JsonValue, model_validator


class CitationSource(BaseModel):
    evidence_ref: str
    source_ref: str | None = None
    locator: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_source(self) -> CitationSource:
        if not self.evidence_ref.strip():
            raise ValueError("CitationSource evidence_ref cannot be empty")
        return self


class DecisionCitation(BaseModel):
    conclusion_index: int = Field(ge=0)
    evidence_ref: str
    source_ref: str | None = None
    locator: dict[str, JsonValue] = Field(default_factory=dict)


class CitationBinder:
    def bind(
        self,
        conclusion_evidence_refs: list[list[str]],
        sources: list[CitationSource],
    ) -> list[DecisionCitation]:
        by_ref = {item.evidence_ref: item for item in sources}
        citations: list[DecisionCitation] = []
        for conclusion_index, refs in enumerate(conclusion_evidence_refs):
            for evidence_ref in refs:
                source = by_ref.get(evidence_ref)
                if source is None:
                    raise ValueError(f"citation source missing for evidence_ref={evidence_ref}")
                citations.append(
                    DecisionCitation(
                        conclusion_index=conclusion_index,
                        evidence_ref=evidence_ref,
                        source_ref=source.source_ref,
                        locator=dict(source.locator),
                    )
                )
        return citations
