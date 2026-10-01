from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from packages.evaluation.benchmark import CompetitionReport
from packages.evaluation.competition_status import render_competition_report_markdown
from scripts.export_competition_report import CompetitionRunSet, _validate_provider_snapshot_refs


def test_competition_run_set_requires_unique_explicit_runs() -> None:
    with pytest.raises(ValidationError, match="benchmark ids must be unique"):
        CompetitionRunSet(
            deployment_revision_id="deployment:test",
            benchmark_run_ids=["run-1", "run-1"],
        )


def test_competition_markdown_preserves_not_evaluated_state() -> None:
    report = CompetitionReport(
        report_id="report-1",
        report_digest="digest-1",
        deployment_revision_id="deployment:test",
        benchmark_run_ids=["run-1"],
        generated_at=datetime(2026, 10, 1, tzinfo=UTC),
        metrics=[],
        target_checks=[],
        unevaluated_competition_areas=["M6 QA quality", "Agent runtime"],
    )
    rendered = render_competition_report_markdown(report)
    assert "GENERATED from CompetitionReport JSON" in rendered
    assert "- M6 QA quality" in rendered
    assert "- Agent runtime" in rendered


def test_competition_run_set_must_cover_selected_provider_snapshots() -> None:
    with pytest.raises(ValueError, match="omit provider snapshots"):
        _validate_provider_snapshot_refs(
            run_world_snapshot_refs=["provider-snapshot:m3-world", None],
            case_artifact_refs=[
                ["provider-snapshot:m1-delivery", "m1-latency-samples:digest"]
            ],
            declared_artifact_refs=["provider-snapshot:m1-delivery"],
        )

    _validate_provider_snapshot_refs(
        run_world_snapshot_refs=["provider-snapshot:m3-world", None],
        case_artifact_refs=[["provider-snapshot:m1-delivery"]],
        declared_artifact_refs=[
            "provider-snapshot:m1-delivery",
            "provider-snapshot:m3-world",
        ],
    )
