from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.evaluation_runtime import ensure_benchmark_deployment_revision
from apps.runtime_models import register_runtime_models
from packages.evaluation.benchmark import CompetitionReport
from packages.evaluation.benchmark.storage import BenchmarkCaseModel, BenchmarkSuiteModel
from packages.evaluation.competition_status import render_competition_report_markdown
from packages.evaluation.fault_recovery_status import render_fault_recovery_markdown
from packages.evaluation.m1_status import (
    render_m1_status_markdown,
    update_m1_readme_status,
)
from packages.intelligence.retrieval.validation import current_knowledge_revision
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from scripts.evaluate_real_enrichment import _run as run_structured_enrichment
from scripts.evaluate_redhat_csaf_vex import _run as run_csaf_enrichment
from scripts.export_competition_report import _export as export_competition_report
from scripts.probe_model_provider import probe_model_provider
from scripts.register_real_enrichment_benchmark import _register as register_enrichment_benchmark
from scripts.render_readme_evidence import render as render_readme_evidence
from scripts.run_fault_recovery_benchmark import _run as run_fault_recovery
from scripts.run_m1_benchmark import M1ExpectedEventManifest
from scripts.run_m1_benchmark import _run as run_m1
from scripts.run_qa_benchmark import QABenchmarkManifest
from scripts.run_qa_benchmark import _run as run_qa
from scripts.validate_qa_manifest import _validate

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ["docker", "compose", "-f", "deploy/docker-compose.yml", "--profile", "runtime"]
DATA_PLANE_SERVICES = ["scheduler", "worker-collection", "worker"]
M1_CURRENT = ROOT / "benchmarks/m1/current.json"
M1_EXPECTED_EVENTS = (
    ROOT / "benchmarks/m1/expected_events/github-target-repos-20261001T1000Z-1402Z.json"
)
STRUCTURED_PROVIDER_SNAPSHOT = (
    ROOT / "benchmarks/m3/provider_snapshots/structured-20261001T151331Z.json"
)
CSAF_CURRENT = ROOT / "benchmarks/m3/current-csaf-vex.json"


def _require_clean_worktree() -> None:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        raise RuntimeError(
            "formal QA batch requires a clean git worktree so DeploymentRevision is reproducible"
        )


def _compose(*args: str) -> None:
    subprocess.run([*COMPOSE, *args], cwd=ROOT, check=True)


async def _resolve_model() -> dict[str, Any]:
    initial = get_settings()
    probe = await probe_model_provider()
    resolved = probe.get("resolved_model_name")
    if not isinstance(resolved, str) or not resolved:
        raise RuntimeError("model provider probe did not resolve a model name")
    if not initial.model_name:
        os.environ["SECFUSION_MODEL_NAME"] = resolved
        get_settings.cache_clear()
    settings = get_settings()
    if settings.model_name != resolved:
        raise RuntimeError("resolved model identity does not match runtime settings")
    return probe


async def _world_and_next_revisions(
    suite_ids: list[str],
    *,
    case_ids_by_suite: dict[str, list[str]] | None = None,
) -> tuple[int, dict[str, int], str]:
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session, session.begin():
            world_revision = await current_knowledge_revision(session)
            next_revisions: dict[str, int] = {}
            for suite_id in suite_ids:
                next_revisions[suite_id] = await _next_suite_revision(
                    session,
                    suite_id,
                    (case_ids_by_suite or {}).get(suite_id, []),
                )
            deployment_revision_id = await ensure_benchmark_deployment_revision(
                session,
                settings,
                repo_root=ROOT,
            )
        return world_revision, next_revisions, deployment_revision_id
    finally:
        await engine.dispose()


async def _next_suite_revision(
    session: AsyncSession,
    suite_id: str,
    case_ids: list[str],
) -> int:
    current_suite_max = await session.scalar(
        select(func.max(BenchmarkSuiteModel.suite_revision)).where(
            BenchmarkSuiteModel.suite_id == suite_id
        )
    )
    current_case_max = None
    if case_ids:
        current_case_max = await session.scalar(
            select(func.max(BenchmarkCaseModel.case_revision)).where(
                BenchmarkCaseModel.case_id.in_(case_ids)
            )
        )
    return max(int(current_suite_max or 0), int(current_case_max or 0)) + 1


async def run_live_qa_batch(
    product_template: Path,
    session_template: Path,
) -> dict[str, Any]:
    _require_clean_worktree()
    provider_probe = await _resolve_model()

    (
        product_text,
        session_text,
        m1_current_text,
        m1_expected_text,
        structured_snapshot_text,
        csaf_current_text,
    ) = await asyncio.gather(
        asyncio.to_thread(product_template.read_text, encoding="utf-8"),
        asyncio.to_thread(session_template.read_text, encoding="utf-8"),
        asyncio.to_thread(M1_CURRENT.read_text, encoding="utf-8"),
        asyncio.to_thread(M1_EXPECTED_EVENTS.read_text, encoding="utf-8"),
        asyncio.to_thread(STRUCTURED_PROVIDER_SNAPSHOT.read_text, encoding="utf-8"),
        asyncio.to_thread(CSAF_CURRENT.read_text, encoding="utf-8"),
    )
    product = QABenchmarkManifest.model_validate_json(product_text)
    session = QABenchmarkManifest.model_validate_json(session_text)
    m1_current = json.loads(m1_current_text)
    expected_events = M1ExpectedEventManifest.model_validate_json(m1_expected_text)
    structured_snapshot = json.loads(structured_snapshot_text)
    csaf_current = json.loads(csaf_current_text)
    if not isinstance(m1_current, dict):
        raise ValueError("current M1 evidence must be a JSON object")
    if not isinstance(structured_snapshot, dict):
        raise ValueError("structured provider snapshot must be a JSON object")
    if not isinstance(csaf_current, dict):
        raise ValueError("current CSAF evidence must be a JSON object")
    raw_structured_cases = structured_snapshot.get("cases")
    if not isinstance(raw_structured_cases, dict):
        raise ValueError("structured provider snapshot cases must be an object")
    structured_cases = [str(item).upper() for item in raw_structured_cases]
    raw_csaf_cases = csaf_current.get("cases")
    if not isinstance(raw_csaf_cases, list) or not all(
        isinstance(item, str) for item in raw_csaf_cases
    ):
        raise ValueError("current CSAF evidence cases must be a string list")
    csaf_cases = [item.upper() for item in raw_csaf_cases]
    m1_suite_ref = m1_current.get("suite_ref")
    if not isinstance(m1_suite_ref, str) or "@" not in m1_suite_ref:
        raise ValueError("current M1 suite_ref is invalid")
    m1_suite_id = m1_suite_ref.rsplit("@", 1)[0]
    suite_ids = [
        product.suite_id,
        session.suite_id,
        m1_suite_id,
        "m3-real-structured",
        "m3-redhat-csaf-vex",
        "engineering-fault-recovery",
    ]

    quiesced = False
    try:
        # Product QA currently reads the live Knowledge head. A short controlled quiesce gives the
        # formal run one immutable world while the normal data plane remains the default operating
        # mode. The finally block restores all three long-lived services even on benchmark failure.
        _compose("stop", *DATA_PLANE_SERVICES)
        quiesced = True

        world_revision, revisions, deployment_revision_id = await _world_and_next_revisions(
            suite_ids,
            case_ids_by_suite={
                product.suite_id: [item.case_id for item in product.cases],
                session.suite_id: [item.case_id for item in session.sessions],
            },
        )
        product = product.model_copy(update={"knowledge_revision": world_revision})
        session = session.model_copy(update={"knowledge_revision": world_revision})

        product_preflight = await _validate(product)
        session_preflight = await _validate(session)
        for label, preflight in (
            ("product", product_preflight),
            ("session", session_preflight),
        ):
            if preflight.get("gold_provenance_status") != "valid":
                raise RuntimeError(f"{label} QA gold provenance is not valid")
            if preflight.get("live_runtime_world_status") != "ready":
                raise RuntimeError(f"{label} QA world pin is not ready")
            if preflight.get("model_provider_status") != "configured":
                raise RuntimeError(f"{label} QA model provider is not configured")

        product_result = await run_qa(
            product,
            suite_revision=revisions[product.suite_id],
            deployment_revision_id=deployment_revision_id,
        )
        session_result = await run_qa(
            session,
            suite_revision=revisions[session.suite_id],
            deployment_revision_id=deployment_revision_id,
        )

        window_start_raw = m1_current.get("window_start")
        window_end_raw = m1_current.get("window_end")
        if not isinstance(window_start_raw, str) or not isinstance(window_end_raw, str):
            raise ValueError("current M1 fixed window is missing")
        m1_result = await run_m1(
            window_start=datetime.fromisoformat(window_start_raw),
            window_end=datetime.fromisoformat(window_end_raw),
            suite_id=m1_suite_id,
            suite_revision=revisions[m1_suite_id],
            deployment_revision_id=deployment_revision_id,
            expected_events_manifest=expected_events,
            delivery_grace_seconds=int(m1_current.get("delivery_grace_seconds", 21600)),
        )

        structured_report = await run_structured_enrichment(
            structured_cases,
            structured_snapshot,
        )
        structured_registration = await register_enrichment_benchmark(
            structured_report,
            suite_id="m3-real-structured",
            suite_revision=revisions["m3-real-structured"],
            deployment_revision_id=deployment_revision_id,
        )

        csaf_report = await run_csaf_enrichment(csaf_cases)
        csaf_registration = await register_enrichment_benchmark(
            csaf_report,
            suite_id="m3-redhat-csaf-vex",
            suite_revision=revisions["m3-redhat-csaf-vex"],
            deployment_revision_id=deployment_revision_id,
        )

        fault_result = await run_fault_recovery(
            suite_revision=revisions["engineering-fault-recovery"],
            deployment_revision_id=deployment_revision_id,
        )

        run_ids = [
            m1_result["benchmark_run_id"],
            structured_registration["benchmark_run_id"],
            csaf_registration["benchmark_run_id"],
            fault_result["benchmark_run_id"],
            product_result["benchmark_run_id"],
            session_result["benchmark_run_id"],
        ]
        artifact_refs = list(
            dict.fromkeys(
                [
                    str(m1_result["provider_snapshot_ref"]),
                    str(structured_report["provider_snapshot_revision"]),
                    str(csaf_report["provider_snapshot_revision"]),
                    str(structured_report["prediction_world_ref"]),
                    str(csaf_report["prediction_world_ref"]),
                    f"knowledge-revision:{world_revision}",
                ]
            )
        )
        competition_report = await export_competition_report(
            run_ids,
            deployment_revision_id=deployment_revision_id,
            artifact_refs=artifact_refs,
        )
        return {
            "status": "completed",
            "knowledge_revision": world_revision,
            "deployment_revision_id": deployment_revision_id,
            "suite_revisions": revisions,
            "provider_probe": provider_probe,
            "product_manifest": product.model_dump(mode="json"),
            "session_manifest": session.model_dump(mode="json"),
            "product_preflight": product_preflight,
            "session_preflight": session_preflight,
            "product_result": product_result,
            "session_result": session_result,
            "m1_result": m1_result,
            "structured_report": structured_report,
            "structured_registration": structured_registration,
            "csaf_report": csaf_report,
            "csaf_registration": csaf_registration,
            "fault_result": fault_result,
            "competition_run_set": {
                "schema_version": "competition-run-set-v1",
                "deployment_revision_id": deployment_revision_id,
                "benchmark_run_ids": run_ids,
                "artifact_refs": artifact_refs,
            },
            "competition_report": competition_report.model_dump(mode="json"),
        }
    finally:
        if quiesced:
            _compose("up", "-d", *DATA_PLANE_SERVICES)


def _write_outputs(payload: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    qa_outputs = {
        "current-live-batch.json": payload,
        "current-product-manifest.json": payload["product_manifest"],
        "current-session-manifest.json": payload["session_manifest"],
        "current-product.json": payload["product_result"],
        "current-session.json": payload["session_result"],
    }
    for name, value in qa_outputs.items():
        _write_json(output_dir / name, value)

    m1_result = _require_dict(payload, "m1_result")
    _write_json(ROOT / "benchmarks/m1/current.json", m1_result)
    m1_markdown = render_m1_status_markdown(m1_result)
    (ROOT / "benchmarks/m1/current.md").write_text(m1_markdown, encoding="utf-8")
    update_m1_readme_status(ROOT / "benchmarks/m1/README.md", m1_markdown)

    structured_report = _require_dict(payload, "structured_report")
    csaf_report = _require_dict(payload, "csaf_report")
    _write_json(ROOT / "benchmarks/m3/current-structured.json", structured_report)
    _write_json(ROOT / "benchmarks/m3/current-csaf-vex.json", csaf_report)

    fault_result = _require_dict(payload, "fault_result")
    _write_json(ROOT / "benchmarks/fault-recovery/current.json", fault_result)
    (ROOT / "benchmarks/fault-recovery/current.md").write_text(
        render_fault_recovery_markdown(fault_result),
        encoding="utf-8",
    )

    run_set = _require_dict(payload, "competition_run_set")
    _write_json(ROOT / "benchmarks/competition/current-run-set.json", run_set)
    competition_payload = _require_dict(payload, "competition_report")
    _write_json(ROOT / "benchmarks/competition/current.json", competition_payload)
    report = CompetitionReport.model_validate(competition_payload)
    (ROOT / "benchmarks/competition/current.md").write_text(
        render_competition_report_markdown(report),
        encoding="utf-8",
    )
    render_readme_evidence(check=False)


def _require_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise TypeError(f"formal batch payload.{key} must be an object")
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Probe the configured model, freeze one deployment/world, run the complete formal "
            "M1/M3/M6/fault competition batch, publish current evidence, and always resume the "
            "long-lived data plane"
        )
    )
    parser.add_argument(
        "--product-template",
        type=Path,
        default=Path("benchmarks/qa/real-product-v1.candidate.json"),
    )
    parser.add_argument(
        "--session-template",
        type=Path,
        default=Path("benchmarks/qa/real-session-v1.candidate.json"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("benchmarks/qa"))
    args = parser.parse_args()
    payload = asyncio.run(run_live_qa_batch(args.product_template, args.session_template))
    _write_outputs(payload, args.output_dir)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
