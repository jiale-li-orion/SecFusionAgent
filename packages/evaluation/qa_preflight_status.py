from __future__ import annotations

from typing import Any


def render_qa_preflight_markdown(
    product: dict[str, Any],
    session: dict[str, Any],
) -> str:
    rows = [
        _row("Product QA", product),
        _row("Session QA", session),
    ]
    lines = [
        "<!-- GENERATED from QA preflight JSON; DO NOT EDIT BY HAND. -->",
        "# M6 QA no-model preflight",
        "",
        (
            "| Denominator | Cases | Sessions | Structured gold | Pinned Knowledge | "
            "Current Knowledge | Gold provenance | Live world | Model provider |"
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
        *rows,
        "",
        (
            "`gold provenance=valid` means the declared EvidenceRefs/facts/paths/absence "
            "checks are valid as of the pinned Knowledge revision. "
            "`live world=stale_requires_refresh_or_rebase` means the same manifest cannot "
            "be executed through the live Product runtime until its world pin is rebased; "
            "it does not invalidate the frozen gold."
        ),
        "",
    ]
    return "\n".join(lines)


def _row(label: str, payload: dict[str, Any]) -> str:
    structured = int(payload.get("structured_authority_case_count", 0)) + int(
        payload.get("structured_authority_session_turn_count", 0)
    )
    return (
        f"| {label} | {payload.get('case_count', 0)} | {payload.get('session_count', 0)} | "
        f"{structured} | {payload.get('knowledge_revision', '—')} | "
        f"{payload.get('current_knowledge_revision', '—')} | "
        f"`{payload.get('gold_provenance_status', 'unknown')}` | "
        f"`{payload.get('live_runtime_world_status', 'unknown')}` | "
        f"`{payload.get('model_provider_status', 'unknown')}` |"
    )
