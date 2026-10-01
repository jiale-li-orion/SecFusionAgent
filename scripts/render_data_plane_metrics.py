# ruff: noqa: E501
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def _duration(value: float | None) -> str:
    if value is None:
        return "—"
    if value >= 3600:
        return f"{value / 3600:.2f}h"
    if value >= 60:
        return f"{value / 60:.2f}min"
    return f"{value:.1f}s"


def _bytes(value: int | float) -> str:
    value = float(value)
    if value >= 1024**3:
        return f"{value / 1024**3:.2f} GiB"
    if value >= 1024**2:
        return f"{value / 1024**2:.2f} MiB"
    if value >= 1024:
        return f"{value / 1024:.1f} KiB"
    return f"{int(value)} B"


def _number(value: float | int | None, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


def render(payload: dict[str, Any]) -> str:
    taxonomy = payload["taxonomy"]
    health = payload["source_health"]["counts"]
    storage = payload["storage"]
    artifact = storage["artifact_store"]
    lines = [
        "# Data-plane runtime metrics",
        "",
        f"Snapshot `{payload['generated_at']}`. Public continuous-monitoring epoch: "
        f"`{payload['public_monitoring_epoch_local']}`; earlier rows are bootstrap/corpus-prefill and are excluded from public runtime throughput.",
        "",
        "## Source portfolio contract",
        "",
        "| Metric | Current |",
        "| --- | ---: |",
        f"| Portfolio categories | {taxonomy['portfolio_categories']} |",
        f"| Catalog entries | {taxonomy['catalog_entries']} |",
        f"| Executable sources | {taxonomy['executable_sources']} |",
        f"| Scheduled monitors | {taxonomy['scheduled_monitors']} |",
        f"| Categories with scheduled monitoring | {taxonomy['scheduled_categories']}/{taxonomy['portfolio_categories']} |",
        "",
        "`assets` is intentionally query-time/on-demand; it remains part of 8-category product coverage and outside scheduled-monitor throughput.",
        "",
        "## Current source health",
        "",
        "| State | Sources |",
        "| --- | ---: |",
        f"| healthy | {health.get('healthy', 0)} |",
        f"| degraded | {health.get('degraded', 0)} |",
        f"| blocked | {health.get('blocked', 0)} |",
        f"| warming | {health.get('warming', 0)} |",
        f"| healthy rate | {_pct(payload['source_health'].get('healthy_rate'))} |",
        f"| overdue | {payload['source_health'].get('overdue_sources', 0)} |",
        f"| backfill pending | {payload['source_health'].get('backfill_pending_sources', 0)} |",
        "",
        "Health is current-state operational evidence: latest scheduled run + durable SourceState/backoff/overdue state. It is not a competition benchmark score.",
        "",
        "## Rolling scheduled-monitoring throughput",
        "",
        "| Window | Runs OK | Provider fail | Runtime fail | Fresh | Fresh src/cat | Queue p95 | Exec p95 | Fresh p95 → Knowledge | Writes/obs | Evidence | Top-1 share |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key, item in payload["rolling_windows"].items():
        value = item["scheduled_monitoring"]
        lines.append(
            f"| {key} | {_pct(value['scheduled_run_success_rate'])} | "
            f"{_pct(value.get('provider_boundary_failure_rate'))} | "
            f"{_pct(value.get('runtime_owned_failure_rate'))} | "
            f"{value['fresh_external_changes']} | "
            f"{value['fresh_contributing_sources']}/{value['fresh_contributing_categories']} | "
            f"{_duration(value['queue_delay_p95_seconds'])} | "
            f"{_duration(value['execution_p95_seconds'])} | "
            f"{_duration(value['fresh_knowledge_latency_p95_seconds'])} | "
            f"{_number(value['canonical_writes_per_observation'])} | "
            f"{_bytes(value.get('evidence_physical_bytes', 0))} | "
            f"{_pct(value['fresh_top1_source_share'])} |"
        )

    current = payload["rolling_windows"]["1h"]["scheduled_monitoring"]
    lines.extend(
        [
            "",
            "Current conversion detail: "
            f"{_number(current['knowledge_revision_per_observation'])} KnowledgeRevision/Observation; "
            f"fresh Knowledge commit closure {_pct(current.get('fresh_knowledge_commit_rate'))}; "
            f"{_number(current['canonical_writes_per_observation'])} canonical writes/Observation; "
            f"{_number(current['chunks_per_document_revision'])} chunks/document revision. "
            f"The same window contains {current['backfill_observations']} backfill Observations and "
            f"{current['unclocked_first_seen']} unclocked first-seen Observations, both kept separate from fresh-change latency. "
            f"Terminal status mix: `{current.get('terminal_status_counts', {})}`. Provider-boundary failures and runtime-owned failures are reported separately so external 403/quota/network conditions do not masquerade as scheduler/storage failures.",
        ]
    )

    category_window = payload["rolling_windows"].get("24h") or next(
        iter(payload["rolling_windows"].values())
    )
    lines.extend(
        [
            "",
            "## Eight-category runtime view",
            "",
            f"Window `{category_window['window_start']}` → `{category_window['window_end']}`. Physical sources have exactly one measurement category, so category rows add back to physical totals without double counting.",
            "",
            "| Category | Catalog | Exec | Scheduled | Fresh | Backfill | Writes | Chunks | Text | Evidence | Run OK | Provider fail | Runtime fail |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for category, cfg in taxonomy["categories"].items():
        flow = category_window["categories"][category]
        lines.append(
            f"| `{category}` | {cfg['catalog_entries']} | {cfg['measurement_sources']} | "
            f"{cfg['scheduled_monitors']} | {flow['fresh_external_changes']} | "
            f"{flow['backfill_observations']} | {flow['canonical_writes']} | "
            f"{flow['document_chunks']} | {_bytes(flow['document_text_bytes'])} | "
            f"{_bytes(flow.get('evidence_physical_bytes', 0))} | "
            f"{_pct(flow['scheduled_run_success_rate'])} | "
            f"{_pct(flow.get('provider_boundary_failure_rate'))} | "
            f"{_pct(flow.get('runtime_owned_failure_rate'))} |"
        )

    source_rows = list(category_window.get("sources", {}).items())
    source_rows.sort(
        key=lambda item: (
            item[1].get("fresh_external_changes", 0),
            item[1].get("observations", 0),
            item[1].get("canonical_writes", 0),
        ),
        reverse=True,
    )
    lines.extend(
        [
            "",
            "## Source-level runtime drill-down",
            "",
            "| Source | Category | Fresh | Backfill | Observations | Writes | Chunks | Evidence | Run OK | Provider fail | Runtime fail |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for source_id, flow in source_rows:
        if not any(
            flow.get(key, 0)
            for key in (
                "fresh_external_changes",
                "backfill_observations",
                "observations",
                "scheduled_runs",
            )
        ):
            continue
        lines.append(
            f"| `{source_id}` | `{flow.get('measurement_category')}` | "
            f"{flow['fresh_external_changes']} | {flow['backfill_observations']} | "
            f"{flow['observations']} | {flow['canonical_writes']} | "
            f"{flow['document_chunks']} | {_bytes(flow.get('evidence_physical_bytes', 0))} | "
            f"{_pct(flow['scheduled_run_success_rate'])} | "
            f"{_pct(flow.get('provider_boundary_failure_rate'))} | "
            f"{_pct(flow.get('runtime_owned_failure_rate'))} |"
        )

    lines.extend(["", "## Evidence/storage integrity", ""])
    if artifact.get("status") == "available":
        public_epoch = artifact["public_epoch"]
        lines.extend(
            [
                "| Public runtime scope | Referenced artifacts | Present objects | Integrity |",
                "| --- | ---: | ---: | ---: |",
                f"| Since monitoring epoch | {public_epoch['referenced_objects']} | {public_epoch['present_objects']} | {_pct(public_epoch['integrity_rate'])} |",
                "",
                f"Current `{artifact.get('backend', 'unknown')}` evidence store: {artifact['physical_objects']} physical objects / {_bytes(artifact['physical_bytes'])}. PostgreSQL database size: {_bytes(storage['postgres_database_bytes'])}. Pre-epoch bootstrap artifact history is retained as an internal diagnostic and is outside public runtime claims.",
            ]
        )
    else:
        lines.append(
            f"Artifact store status: `{artifact.get('status')}` — `{artifact.get('error', 'unknown')}`."
        )

    lines.extend(
        [
            "",
            "## Metric contract",
            "",
            "- **Catalog entry**: one product-facing source commitment in `config/source-inventory.json`.",
            "- **Executable source**: one concrete `SourceDefinition` with adapter/runtime ownership.",
            "- **Scheduled monitor**: executable source with runtime `enabled=true` and `schedule_policy.enabled != false`.",
            "- **Fresh external change**: scheduled Observation outside backfill whose `updated_at ?? published_at` is within the configured fresh horizon when observed.",
            "- **Backfill**: Observation produced by a run whose input or output cursor has `backfill_pending=true`.",
            "- **Run success rate**: `(success + no_change) / terminal scheduled runs`; provider failures remain in the denominator.",
            "- **Provider-boundary failure rate**: `fetch_failed + rate_limited + auth_failed + schema_changed + provider_blocked` divided by terminal scheduled runs; it measures upstream access/transport/protocol availability.",
            "- **Runtime-owned failure rate**: `dependency_unavailable + internal_error + generic failed` divided by terminal scheduled runs; it isolates SecFusionAgent-owned execution/dependency failures.",
            "- **Queue delay**: AcquisitionRun creation → worker start; this isolates scheduler/worker backlog from provider latency.",
            "- **Execution time**: worker start → terminal AcquisitionRun; this surfaces slow or blocking providers.",
            "- **Change poll yield**: change-producing `success` runs divided by successful scheduled runs; this measures useful poll density, not correctness.",
            "- **Write amplification**: canonical Object/Claim/Relation writes per Observation; it measures knowledge conversion, not model accuracy.",
            "- **Fresh knowledge commit rate**: fresh scheduled changes that reached a KnowledgeRevision; this is the data-plane conversion closure ratio.",
            "- **Top-1 traffic share**: largest source's share of fresh scheduled changes; lower concentration indicates broader live-source participation.",
            "- **Evidence integrity**: distinct `EvidenceArtifact.storage_uri` values whose physical object exists in the active durable artifact store.",
            "",
            "`hourly_series` and `category_hourly_series` in `current.json` are the chart-ready time series for live/fresh/backfill/write/chunk/run-health curves.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Render data-plane runtime metrics Markdown")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    expected = render(payload)
    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
        if current != expected:
            raise SystemExit(f"stale generated data-plane report: {args.output}")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")


if __name__ == "__main__":
    main()
