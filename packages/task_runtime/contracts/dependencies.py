from __future__ import annotations

TASK_DEPENDENCY_PREFIX = "task_dependency:"
_LEGACY_DEPENDENCY_PREFIXES = ("delegated_enrichment:",)


def task_dependency_reason(child_run_id: str) -> str:
    child_run_id = child_run_id.strip()
    if not child_run_id:
        raise ValueError("child_run_id cannot be empty")
    return f"{TASK_DEPENDENCY_PREFIX}{child_run_id}"


def dependency_run_id(stop_reason: str | None) -> str | None:
    if stop_reason is None:
        return None
    for prefix in (TASK_DEPENDENCY_PREFIX, *_LEGACY_DEPENDENCY_PREFIXES):
        if stop_reason.startswith(prefix):
            child_run_id = stop_reason[len(prefix) :].strip()
            return child_run_id or None
    return None
