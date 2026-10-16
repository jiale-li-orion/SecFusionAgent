"""Bounded model-authored report composition; never executable markup."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class ReportSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heading: str = Field(min_length=1, max_length=100)
    paragraph_indices: list[Annotated[int, Field(ge=0)]] = Field(min_length=1, max_length=32)


class ReportLayout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=180)
    style: Literal["editorial", "briefing"] = "editorial"
    sections: list[ReportSection] = Field(default_factory=list, max_length=12)

    def covers(self, paragraph_count: int) -> bool:
        if not self.sections:
            return True
        indices = [index for section in self.sections for index in section.paragraph_indices]
        return sorted(indices) == list(range(paragraph_count))
