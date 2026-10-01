from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

MAX_PROSPECTIVE_FREEZE_LAG_SECONDS = 300.0


def assess_prospective_investigation_case(
    *,
    created_at: datetime,
    final_decision_at: datetime | None,
    frozen_at: datetime,
    max_freeze_lag_seconds: float,
) -> dict[str, Any]:
    created = _utc(created_at)
    frozen = _utc(frozen_at)
    decision = _utc(final_decision_at) if final_decision_at is not None else None
    freeze_lag_seconds = (frozen - created).total_seconds()

    rejection_reason: str | None = None
    if freeze_lag_seconds < 0:
        rejection_reason = "case_created_after_freeze"
    elif freeze_lag_seconds > max_freeze_lag_seconds:
        rejection_reason = "freeze_lag_exceeded"
    elif decision is not None and decision <= frozen:
        rejection_reason = "final_decision_already_visible"

    return {
        "eligible": rejection_reason is None,
        "freeze_lag_seconds": freeze_lag_seconds,
        "rejection_reason": rejection_reason,
    }


def render_investigation_readiness_markdown(payload: dict[str, Any]) -> str:
    cases = payload.get("cases")
    rows = cases if isinstance(cases, list) else []
    lines = [
        "<!-- GENERATED from Investigation readiness JSON; DO NOT EDIT BY HAND. -->",
        "# Long-Investigation readiness",
        "",
        f"- Generated at: `{payload.get('generated_at', 'unknown')}`",
        f"- Model provider: `{payload.get('model_provider_status', 'unknown')}`",
        f"- Launch readiness: `{payload.get('launch_readiness', 'unknown')}`",
        f"- Existing Product Cases: {payload.get('case_count', 0)}",
        f"- Prospectively freeze-eligible now: {payload.get('eligible_case_count', 0)}",
        "",
        (
            "| Product Case | Status | Created at | Freeze lag | Final decision | "
            "Eligibility | Rejection reason |"
        ),
        "| --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for item in rows:
        if not isinstance(item, dict):
            continue
        lag = item.get("freeze_lag_seconds")
        lag_text = f"{float(lag):.1f}s" if isinstance(lag, (int, float)) else "—"
        decision = item.get("final_decision_at") or "—"
        reason = item.get("rejection_reason") or "—"
        eligibility = "eligible" if item.get("eligible") is True else "rejected"
        lines.append(
            f"| `{item.get('case_id', 'unknown')}` | `{item.get('case_status', 'unknown')}` | "
            f"`{item.get('created_at', 'unknown')}` | {lag_text} | `{decision}` | "
            f"`{eligibility}` | `{reason}` |"
        )
    lines.extend(
        [
            "",
            (
                "This is readiness evidence only. A case becomes formal competition evidence "
                "only after a manifest freezes it within the protocol-owned prospective lag "
                "bound and `run_investigation_benchmark.py` accepts that manifest."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
