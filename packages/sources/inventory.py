from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from packages.sources.taxonomy import SOURCE_PORTFOLIO_CATEGORIES, SourcePortfolioCategory


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


class MonitoringMeasurementContract(BaseModel):
    public_epoch: datetime
    fresh_event_max_age_seconds: int = Field(gt=0)
    recent_event_max_age_seconds: int = Field(gt=0)
    rolling_windows_hours: tuple[int, ...]

    @model_validator(mode="after")
    def validate_windows(self) -> MonitoringMeasurementContract:
        if self.recent_event_max_age_seconds <= self.fresh_event_max_age_seconds:
            raise ValueError("recent-event horizon must exceed fresh-event horizon")
        if not self.rolling_windows_hours or any(
            value <= 0 for value in self.rolling_windows_hours
        ):
            raise ValueError("rolling windows must be positive")
        if tuple(sorted(set(self.rolling_windows_hours))) != self.rolling_windows_hours:
            raise ValueError("rolling windows must be unique and sorted")
        return self


class SourceInventory(BaseModel):
    schema_version: str
    purpose: str
    coverage_semantics: dict[str, str]
    monitoring_measurement: MonitoringMeasurementContract
    measurement_category_overrides: dict[str, SourcePortfolioCategory] = Field(default_factory=dict)
    entries: list[SourceInventoryEntry]

    @model_validator(mode="after")
    def validate_categories(self) -> SourceInventory:
        categories = {SourcePortfolioCategory(item.category) for item in self.entries}
        if categories != SOURCE_PORTFOLIO_CATEGORIES:
            raise ValueError(
                "source inventory must contain the complete frozen eight-category taxonomy"
            )
        physical = self.physical_source_categories()
        multi_category = {
            source_id
            for source_id, source_categories in physical.items()
            if len(source_categories) > 1
        }
        override_ids = set(self.measurement_category_overrides)
        if override_ids != multi_category:
            raise ValueError(
                "measurement_category_overrides must name exactly the "
                "multi-category physical sources"
            )
        for source_id, category in self.measurement_category_overrides.items():
            if category not in physical[source_id]:
                raise ValueError(
                    f"measurement category override for {source_id} is outside its "
                    "inventory categories"
                )
        return self

    def physical_source_categories(self) -> dict[str, frozenset[SourcePortfolioCategory]]:
        mapping: dict[str, set[SourcePortfolioCategory]] = defaultdict(set)
        for item in self.entries:
            category = SourcePortfolioCategory(item.category)
            for source_id in item.source_ids:
                mapping[source_id].add(category)
        return {source_id: frozenset(categories) for source_id, categories in mapping.items()}

    def measurement_category(self, source_id: str) -> SourcePortfolioCategory:
        categories = self.physical_source_categories().get(source_id)
        if not categories:
            raise KeyError(f"source inventory has no physical category for {source_id}")
        if len(categories) == 1:
            return next(iter(categories))
        override = self.measurement_category_overrides.get(source_id)
        if override is None:
            raise ValueError(
                f"multi-category source requires measurement category override: {source_id}"
            )
        if override not in categories:
            raise ValueError(
                f"measurement category override for {source_id} is outside its inventory categories"
            )
        return override


def load_source_inventory(path: Path = Path("config/source-inventory.json")) -> SourceInventory:
    return SourceInventory.model_validate(json.loads(path.read_text()))
