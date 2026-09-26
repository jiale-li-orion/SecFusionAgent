from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SourceInventoryEntry(BaseModel):
    category: str
    name: str
    mode: Literal["fixed_provider", "grouped_member", "dynamic_resolution"]
    coverage: Literal["owned", "partial", "dynamic"]
    source_ids: list[str] = Field(default_factory=list)
    dynamic_owner: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def validate_ownership(self) -> SourceInventoryEntry:
        if self.mode == "dynamic_resolution":
            if not self.dynamic_owner:
                raise ValueError("dynamic_resolution entry requires dynamic_owner")
        elif not self.source_ids:
            raise ValueError(f"{self.mode} entry requires source_ids")
        if self.coverage == "dynamic" and self.mode != "dynamic_resolution":
            raise ValueError("coverage=dynamic requires mode=dynamic_resolution")
        return self


class SourceInventory(BaseModel):
    schema_version: str
    purpose: str
    coverage_semantics: dict[str, str]
    entries: list[SourceInventoryEntry]


def load_source_inventory(path: Path = Path("config/source-inventory.json")) -> SourceInventory:
    return SourceInventory.model_validate(json.loads(path.read_text()))
