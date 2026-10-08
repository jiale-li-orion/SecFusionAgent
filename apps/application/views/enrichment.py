from pydantic import BaseModel, Field


class ProductEnrichmentRunView(BaseModel):
    object_id: str
    cve_id: str
    task_run_id: str
    role_id: str = "EnrichmentRole"
    execution_profile: str = "INVESTIGATE"
    status: str
    required_dimensions: list[str]
    stop_reason: str | None = None
    task_url: str
    state_url: str
    replayed: bool = False


class ProductEnrichmentRunPage(BaseModel):
    items: list[ProductEnrichmentRunView] = Field(default_factory=list)
