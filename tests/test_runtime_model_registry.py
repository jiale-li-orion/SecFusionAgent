from apps.runtime_models import register_runtime_models
from packages.shared.db import Base


def test_runtime_model_registry_resolves_cross_package_foreign_keys() -> None:
    register_runtime_models()
    required = {
        "sources",
        "source_state",
        "acquisition_runs",
        "observations",
        "evidence_artifacts",
        "objects",
        "claims",
        "relations",
        "document_chunks",
        "incidents",
        "current_projections",
        "investigation_cases",
        "case_state_events",
        "evidence_needs",
        "investigation_state_current",
        "task_contract_versions",
        "context_manifest_versions",
        "task_runs",
        "task_events",
        "task_event_deliveries",
        "enrichment_dimension_states",
        "enrichment_attempts",
        "perception_events",
        "investigation_snapshots",
        "budget_accounts",
        "budget_reservations",
        "capability_invocations",
        "skill_versions",
        "execution_runs",
        "sandbox_instances",
        "sandbox_executions",
        "runtime_artifacts",
        "outbox_events",
    }
    assert required <= set(Base.metadata.tables)
    # Accessing sorted_tables forces SQLAlchemy to resolve every FK target.
    assert len(Base.metadata.sorted_tables) >= len(required)
