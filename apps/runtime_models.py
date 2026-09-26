"""Register all SQLAlchemy runtime models at application composition boundaries."""

from __future__ import annotations

from importlib import import_module

_MODEL_MODULES = (
    "packages.sources.storage.models",
    "packages.monitoring.storage.models",
    "packages.intelligence.storage.models",
    "packages.intelligence.storage.evidence_models",
    "packages.intelligence.storage.knowledge_models",
    "packages.intelligence.storage.incident_models",
    "packages.intelligence.storage.projection_models",
    "packages.intelligence.storage.document_models",
    "packages.intelligence.storage.normative_models",
    "packages.investigation.storage.models",
    "packages.shared.storage.models",
)

_registered = False


def register_runtime_models() -> None:
    global _registered
    if _registered:
        return
    for module_name in _MODEL_MODULES:
        import_module(module_name)
    _registered = True
