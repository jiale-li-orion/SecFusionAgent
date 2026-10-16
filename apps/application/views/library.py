"""Public retained-material catalog; totals describe usable source material, not claims."""

from datetime import datetime

from pydantic import BaseModel, Field

from apps.application.views.world import WorldStoryView


class LibraryFacetView(BaseModel):
    key: str
    label: str
    label_en: str
    count: int


class LibraryMaterialView(WorldStoryView):
    subjects: list[str] = Field(default_factory=list)


class MaterialLibraryView(BaseModel):
    items: list[LibraryMaterialView]
    total: int
    corpus_total: int
    offset: int
    next_offset: int | None
    limit: int
    as_of: datetime
    categories: list[LibraryFacetView]
    sources: list[LibraryFacetView]
    subjects: list[LibraryFacetView]
