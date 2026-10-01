# ruff: noqa: E501, RUF001
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVAL_BEGIN = "<!-- BEGIN GENERATED EVALUATION STATUS -->"
EVAL_END = "<!-- END GENERATED EVALUATION STATUS -->"
MONITORING_BEGIN = "<!-- BEGIN GENERATED MONITORING STATUS -->"
MONITORING_END = "<!-- END GENERATED MONITORING STATUS -->"
ENRICHMENT_BEGIN = "<!-- BEGIN GENERATED ENRICHMENT STATUS -->"
ENRICHMENT_END = "<!-- END GENERATED ENRICHMENT STATUS -->"
QA_BEGIN = "<!-- BEGIN GENERATED QA STATUS -->"
QA_END = "<!-- END GENERATED QA STATUS -->"


def _load(relative: str) -> dict[str, Any]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _metric_map(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["metric_name"]: item for item in report["metrics"]}


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.3f}%"


def _number(value: float | int | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    return f"{float(value):.6g}"


def _duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds >= 3600:
        return f"{seconds:.3f}s ({seconds / 3600:.2f}h)"
    if seconds >= 60:
        return f"{seconds:.3f}s ({seconds / 60:.2f}min)"
    return f"{seconds:.3f}s"


def _target_table(report: dict[str, Any], *, chinese: bool = False) -> list[str]:
    header = (
        "| 决赛目标 | 指标 | 当前值 | 阈值 | 状态 |"
        if chinese
        else "| Finals target | Metric | Observed | Threshold | Status |"
    )
    rows = [header, "| --- | --- | ---: | ---: | --- |"]
    for target in report["target_checks"]:
        observed = target["observed_value"]
        metric_name = target["metric_name"]
        is_ratio_target = (
            "precision" in metric_name or "recall" in metric_name or "accuracy" in metric_name
        )
        if is_ratio_target:
            observed_text = _pct(float(observed)) if observed is not None else "—"
            threshold_text = _pct(float(target["threshold"]))
        elif metric_name.endswith("latency_seconds"):
            observed_text = _duration(float(observed)) if observed is not None else "—"
            threshold_text = _duration(float(target["threshold"]))
        else:
            observed_text = _number(observed)
            threshold_text = _number(target["threshold"])
        rows.append(
            f"| `{target['target_name']}` | `{metric_name}` | {observed_text} | "
            f"{target['comparator']} {threshold_text} | **{target['status']}** |"
        )
    return rows


def _evaluation_block(*, chinese: bool = False) -> str:
    report = _load("benchmarks/competition/current.json")
    m1 = _load("benchmarks/m1/current.json")
    fault = _load("benchmarks/fault-recovery/current.json")
    metrics = _metric_map(report)
    title = "## 当前正式评测证据（自动生成）" if chinese else "## Current formal evaluation evidence (generated)"
    note = (
        "本段由 `benchmarks/**/current*.json` 自动渲染。修改评测结果后运行 `make evidence-doc`；`make evidence-doc-check` 会在 Markdown 与结构化结果漂移时失败。"
        if chinese
        else "This block is rendered from `benchmarks/**/current*.json`. Run `make evidence-doc` after benchmark changes; `make evidence-doc-check` fails when Markdown drifts from structured evidence."
    )
    lines = [title, "", note, "", *_target_table(report, chinese=chinese), ""]
    if chinese:
        lines.extend(
            [
                f"当前 CompetitionReport：`{report['report_id']}`；Deployment：`{report['deployment_revision_id']}`。",
                "",
                f"M1 固定窗口 `{m1['window_start']}` → `{m1['window_end']}`："
                f"{m1['latency']['evaluable_samples']}/{m1['latency']['total_samples']} 个样本可评，"
                f"p50 {_duration(m1['latency']['p50_seconds'])}，"
                f"p95 {_duration(m1['latency']['p95_seconds'])}，"
                f"≤6h {_pct(m1['latency']['within_6h_rate'])}；"
                f"source category={m1['source_category_count']}。",
                "",
                f"M3 当前选定 run 聚合：TP={_number(metrics['m3.true_positive']['value'])}，"
                f"FP={_number(metrics['m3.false_positive']['value'])}，"
                f"FN={_number(metrics['m3.false_negative']['value'])}，"
                f"precision={_pct(metrics['m3.micro_precision']['value'])}，"
                f"recall={_pct(metrics['m3.micro_recall']['value'])}。"
                f"工程故障恢复 `{fault['suite_ref']}` 为 {_pct(fault['success_rate'])}（{len(fault['cases'])} cases）。",
                "",
                "当前未评项：" + "、".join(report["unevaluated_competition_areas"]) + "。",
                "",
                "复现入口：`make benchmark-query METRIC=m3.micro_precision` 直接回查 PostgreSQL 的 BenchmarkRun/MetricObservation；`make competition-render-doc` 重新渲染报告；`make evidence-doc` 更新全部证据投影；`make evidence-doc-check` 做无写入一致性检查。",
            ]
        )
    else:
        lines.extend(
            [
                f"Current CompetitionReport: `{report['report_id']}` on `{report['deployment_revision_id']}`.",
                "",
                f"M1 fixed window `{m1['window_start']}` → `{m1['window_end']}`: "
                f"{m1['latency']['evaluable_samples']}/{m1['latency']['total_samples']} evaluable samples, "
                f"p50 {_duration(m1['latency']['p50_seconds'])}, "
                f"p95 {_duration(m1['latency']['p95_seconds'])}, "
                f"within 6h {_pct(m1['latency']['within_6h_rate'])}; "
                f"source categories={m1['source_category_count']}.",
                "",
                f"Selected M3 runs aggregate to TP={_number(metrics['m3.true_positive']['value'])}, "
                f"FP={_number(metrics['m3.false_positive']['value'])}, "
                f"FN={_number(metrics['m3.false_negative']['value'])}, "
                f"precision={_pct(metrics['m3.micro_precision']['value'])}, "
                f"recall={_pct(metrics['m3.micro_recall']['value'])}. "
                f"Controlled engineering recovery `{fault['suite_ref']}` is {_pct(fault['success_rate'])} "
                f"across {len(fault['cases'])} cases.",
                "",
                "Unevaluated competition areas: "
                + ", ".join(f"`{item}`" for item in report["unevaluated_competition_areas"])
                + ".",
                "",
                "Query the durable rows with `make benchmark-query METRIC=m3.micro_precision`; reproduce the report projection with `make competition-render-doc`; refresh every maintained evidence projection with `make evidence-doc`; verify without writes with `make evidence-doc-check`.",
            ]
        )
    return "\n".join(lines)


def _monitoring_block() -> str:
    m1 = _load("benchmarks/m1/current.json")
    provisional = m1["source_delivery_provisional"]
    diagnostics = m1["monitoring_diagnostics"]
    return "\n".join(
        [
            "## Current M1 evidence (generated)",
            "",
            f"Suite `{m1['suite_ref']}`, run `{m1['benchmark_run_id']}`, deployment `{m1['deployment_revision_id']}`.",
            "",
            "| Measurement | Current result |",
            "| --- | ---: |",
            f"| Product source categories | {m1['source_category_count']} |",
            f"| Raw scheduled candidates | {m1['raw_latency_candidate_count']} |",
            f"| Excluded bootstrap/backfill candidates | {m1['excluded_nonsteady_count']} |",
            f"| Evaluable steady-state samples | {m1['latency']['evaluable_samples']}/{m1['latency']['total_samples']} |",
            f"| End-to-end p50 | {_duration(m1['latency']['p50_seconds'])} |",
            f"| End-to-end p95 | {_duration(m1['latency']['p95_seconds'])} |",
            f"| End-to-end max | {_duration(m1['latency']['max_seconds'])} |",
            f"| Within 6h | {_pct(m1['latency']['within_6h_rate'])} |",
            f"| Delivery status | `{m1['source_delivery_status']}` |",
            f"| Provisional independent-provider delivery | {provisional['accepted_expected_items']}/{provisional['expected_items']} ({_pct(provisional['coverage'])}) |",
            "",
            "Latency is source event time → earliest Knowledge commit. `monitoring_diagnostics` keeps provider-discovery, queue-dispatch and ingestion-commit components separate; bootstrap/input/output backfill stays outside the steady-state denominator.",
            "",
            f"Current diagnostic split: raw={diagnostics['raw_candidate_count']}, eligible={diagnostics['eligible_count']}, excluded={diagnostics['excluded_count']}. Read the complete machine result in `benchmarks/m1/current.json` and reproduce the Markdown projection with `make m1-render-doc`.",
        ]
    )


def _enrichment_block() -> str:
    report = _load("benchmarks/competition/current.json")
    structured = _load("benchmarks/m3/current-structured.json")
    csaf = _load("benchmarks/m3/current-csaf-vex.json")
    metrics = _metric_map(report)
    dimensions = sorted(
        name.removeprefix("m3.dimension.").removesuffix(".precision")
        for name in metrics
        if name.startswith("m3.dimension.") and name.endswith(".precision")
    )
    lines = [
        "## Current M3 formal evidence (generated)",
        "",
        f"Competition aggregation: TP={_number(metrics['m3.true_positive']['value'])}, FP={_number(metrics['m3.false_positive']['value'])}, FN={_number(metrics['m3.false_negative']['value'])}, micro precision={_pct(metrics['m3.micro_precision']['value'])}, micro recall={_pct(metrics['m3.micro_recall']['value'])}.",
        "",
        "| Dimension | TP | FP | FN | Precision | Recall |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for dimension in dimensions:
        prefix = f"m3.dimension.{dimension}."
        lines.append(
            f"| `{dimension}` | {_number(metrics[prefix + 'true_positive']['value'])} | "
            f"{_number(metrics[prefix + 'false_positive']['value'])} | "
            f"{_number(metrics[prefix + 'false_negative']['value'])} | "
            f"{_pct(metrics[prefix + 'precision']['value'])} | {_pct(metrics[prefix + 'recall']['value'])} |"
        )
    lines.extend(
        [
            "",
            f"Structured replay freezes gold at `{structured['provider_snapshot_revision']}` and predictions at `{structured['prediction_world_ref']}`; CSAF/VEX freezes gold at `{csaf['provider_snapshot_revision']}` and predictions at `{csaf['prediction_world_ref']}`. Later Knowledge revisions cannot retroactively improve either score.",
            "",
            "Inspect exact gold/predictions/missing/extra facts in `benchmarks/m3/current-structured.json` and `benchmarks/m3/current-csaf-vex.json`; the CompetitionReport aggregation is rendered from durable BenchmarkRun metrics, not copied from this README.",
        ]
    )
    return "\n".join(lines)


def _qa_block() -> str:
    live_batch_path = ROOT / "benchmarks/qa/current-live-batch.json"
    if live_batch_path.exists():
        live = _load("benchmarks/qa/current-live-batch.json")
        if live.get("status") == "completed":
            report = _load("benchmarks/competition/current.json")
            metrics = _metric_map(report)
            product_result = live.get("product_result")
            session_result = live.get("session_result")
            provider_probe = live.get("provider_probe")
            product_result = product_result if isinstance(product_result, dict) else {}
            session_result = session_result if isinstance(session_result, dict) else {}
            provider_probe = provider_probe if isinstance(provider_probe, dict) else {}

            def metric(name: str) -> str:
                item = metrics.get(name)
                if item is None:
                    return "—"
                value = item.get("value")
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    return "—"
                if name.endswith("_seconds"):
                    return _duration(float(value))
                return _pct(float(value))

            return "\n".join(
                [
                    "## Current M6 formal evidence (generated)",
                    "",
                    f"Deployment `{live.get('deployment_revision_id', 'unknown')}`, Knowledge head `knowledge-revision:{live.get('knowledge_revision', 'unknown')}`, resolved model `{provider_probe.get('actual_model') or provider_probe.get('resolved_model_name') or 'unknown'}`.",
                    "",
                    "| Metric | Current result |",
                    "| --- | ---: |",
                    f"| Answer accuracy | {metric('m6.answer_accuracy')} |",
                    f"| Groundedness | {metric('m6.groundedness')} |",
                    f"| Citation correctness | {metric('m6.citation_correctness')} |",
                    f"| Multi-hop correctness | {metric('m6.multi_hop_correctness')} |",
                    f"| Interactive latency | {metric('m6.interactive_latency_seconds')} |",
                    "",
                    f"Product run `{product_result.get('benchmark_run_id', 'unknown')}` / `{product_result.get('suite_ref', 'unknown')}`; session run `{session_result.get('benchmark_run_id', 'unknown')}` / `{session_result.get('suite_ref', 'unknown')}`. `make benchmark-query METRIC=m6.answer_accuracy` drills into durable per-case observations.",
                ]
            )

    product = _load("benchmarks/qa/current-product-preflight.json")
    session = _load("benchmarks/qa/current-session-preflight.json")
    return "\n".join(
        [
            "## Current M6 readiness (generated)",
            "",
            "| Denominator | Gold | Pinned world | Observed DB head | Gold provenance | Live-world status | Provider |",
            "| --- | ---: | ---: | ---: | --- | --- | --- |",
            f"| Product QA | {product['structured_authority_case_count']} cases | {product['knowledge_revision']} | {product['current_knowledge_revision']} | `{product['gold_provenance_status']}` | `{product['live_runtime_world_status']}` | `{product['model_provider_status']}` |",
            f"| Session QA | {session['structured_authority_session_turn_count']} turns / {session['session_count']} sessions | {session['knowledge_revision']} | {session['current_knowledge_revision']} | `{session['gold_provenance_status']}` | `{session['live_runtime_world_status']}` | `{session['model_provider_status']}` |",
            "",
            "Preflight is deliberately not a QA score. `make qa-preflight` refreshes historical-pin validation; `make qa-live-preflight` rebases an in-memory copy to the current Knowledge head and proves that the reviewed gold still holds without spending model calls. With provider credentials configured, `make model-provider-probe` verifies auth + structured output; `make qa-live` then repeats current-world validation, runs product and session suites on one frozen DeploymentRevision, and restores the long-lived data plane even if the batch fails.",
        ]
    )


def _replace(path: Path, begin: str, end: str, body: str, *, check: bool) -> bool:
    text = path.read_text(encoding="utf-8")
    if text.count(begin) != 1 or text.count(end) != 1:
        raise RuntimeError(f"generated block markers are missing or duplicated: {path}")
    start = text.index(begin) + len(begin)
    stop = text.index(end)
    expected = text[:start] + "\n" + body.rstrip() + "\n" + text[stop:]
    if expected == text:
        return False
    if check:
        raise RuntimeError(f"generated README evidence is stale: {path}")
    path.write_text(expected, encoding="utf-8")
    return True


def render(*, check: bool) -> list[str]:
    specs = [
        (ROOT / "README.md", EVAL_BEGIN, EVAL_END, _evaluation_block()),
        (ROOT / "README.zh.md", EVAL_BEGIN, EVAL_END, _evaluation_block(chinese=True)),
        (ROOT / "packages/monitoring/README.md", MONITORING_BEGIN, MONITORING_END, _monitoring_block()),
        (ROOT / "packages/enrichment/README.md", ENRICHMENT_BEGIN, ENRICHMENT_END, _enrichment_block()),
        (ROOT / "packages/evaluation/README.md", EVAL_BEGIN, EVAL_END, _evaluation_block()),
        (ROOT / "benchmarks/README.md", EVAL_BEGIN, EVAL_END, _evaluation_block()),
        (ROOT / "benchmarks/qa/README.md", QA_BEGIN, QA_END, _qa_block()),
    ]
    changed: list[str] = []
    for path, begin, end, body in specs:
        if _replace(path, begin, end, body, check=check):
            changed.append(str(path.relative_to(ROOT)))
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Render current benchmark evidence into README blocks")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    changed = render(check=args.check)
    if not args.check:
        print("updated: " + (", ".join(changed) if changed else "none"))


if __name__ == "__main__":
    main()
