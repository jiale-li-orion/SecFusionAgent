from __future__ import annotations

from typing import Any


def render_fault_recovery_markdown(payload: dict[str, Any]) -> str:
    cases = payload.get("cases")
    rows = cases if isinstance(cases, list) else []
    lines = [
        "<!-- GENERATED from fault-recovery benchmark JSON; DO NOT EDIT BY HAND. -->",
        "# Engineering fault/recovery benchmark",
        "",
        f"- Benchmark run: `{payload.get('benchmark_run_id', 'unknown')}`",
        f"- Deployment: `{payload.get('deployment_revision_id', 'unknown')}`",
        f"- Suite: `{payload.get('suite_ref', 'unknown')}`",
        f"- Fault-recovery success: {float(payload.get('success_rate', 0.0)) * 100:.1f}%",
        "",
        "| Case | Success | Mechanism | Diagnostics |",
        "| --- | --- | --- | --- |",
    ]
    for item in rows:
        if not isinstance(item, dict):
            continue
        diagnostics = item.get("diagnostics")
        diag_text = _compact_diagnostics(diagnostics if isinstance(diagnostics, dict) else {})
        lines.append(
            f"| `{item.get('case_id', 'unknown')}` | `{str(item.get('success', False)).lower()}` | "
            f"{item.get('mechanism', 'unknown')} | {diag_text} |"
        )
    lines.extend(
        [
            "",
            (
                "The probes execute against the real database state-transition code but scope "
                "every injected row by an explicit run/event ID and roll the injected operational "
                "rows back through a savepoint. Only TD3 benchmark rows persist."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _compact_diagnostics(payload: dict[str, Any]) -> str:
    if not payload:
        return "—"
    return "; ".join(f"`{key}={value}`" for key, value in sorted(payload.items()))
