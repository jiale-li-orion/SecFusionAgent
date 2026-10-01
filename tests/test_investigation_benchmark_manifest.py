from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apps.evaluation_runtime import InvestigationCompletionTrace
from scripts.run_investigation_benchmark import (
    InvestigationBenchmarkManifest,
    InvestigationBenchmarkManifestCase,
    _measurement_status,
)


def _trace(
    *,
    created_at: datetime,
    final_decision_at: datetime | None = None,
) -> InvestigationCompletionTrace:
    return InvestigationCompletionTrace(
        case_id="product-case-1",
        case_status="active",
        case_revision=3,
        case_created_at=created_at,
        final_decision_ref=("decision:1" if final_decision_at is not None else None),
        final_decision_case_revision=(2 if final_decision_at is not None else None),
        final_decision_event_revision=(3 if final_decision_at is not None else None),
        final_decision_at=final_decision_at,
        time_to_final_decision_seconds=(
            (final_decision_at - created_at).total_seconds()
            if final_decision_at is not None
            else None
        ),
        investigation_episode_count=1,
        terminal_episode_count=(1 if final_decision_at is not None else 0),
        active_episode_count=(0 if final_decision_at is not None else 1),
        open_evidence_need_count=(0 if final_decision_at is not None else 1),
    )


def test_manifest_requires_unique_cases_and_deadline_after_freeze() -> None:
    frozen_at = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
    deadline = frozen_at + timedelta(hours=1)
    manifest = InvestigationBenchmarkManifest(
        frozen_at=frozen_at,
        cases=[
            InvestigationBenchmarkManifestCase(
                case_id="long-1",
                product_case_id="product-case-1",
                measurement_deadline=deadline,
            )
        ],
    )
    assert manifest.frozen_at == frozen_at
    assert manifest.cases[0].measurement_deadline == deadline

    with pytest.raises(ValueError, match="measurement_deadline must be after"):
        InvestigationBenchmarkManifest(
            frozen_at=frozen_at,
            cases=[
                InvestigationBenchmarkManifestCase(
                    case_id="long-1",
                    product_case_id="product-case-1",
                    measurement_deadline=frozen_at,
                )
            ],
        )

    with pytest.raises(ValueError, match="Product Case cannot appear twice"):
        InvestigationBenchmarkManifest(
            frozen_at=frozen_at,
            cases=[
                InvestigationBenchmarkManifestCase(
                    case_id="long-1",
                    product_case_id="product-case-1",
                    measurement_deadline=deadline,
                ),
                InvestigationBenchmarkManifestCase(
                    case_id="long-2",
                    product_case_id="product-case-1",
                    measurement_deadline=deadline,
                ),
            ],
        )


def test_measurement_status_keeps_open_case_pending_until_deadline() -> None:
    frozen_at = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
    item = InvestigationBenchmarkManifestCase(
        case_id="long-1",
        product_case_id="product-case-1",
        measurement_deadline=frozen_at + timedelta(hours=2),
    )
    trace = _trace(created_at=frozen_at - timedelta(minutes=5))

    pending = _measurement_status(
        item,
        trace,
        frozen_at=frozen_at,
        measured_at=frozen_at + timedelta(minutes=30),
    )
    assert pending.status == "pending"
    assert pending.final_decision_present is False

    expired = _measurement_status(
        item,
        trace,
        frozen_at=frozen_at,
        measured_at=frozen_at + timedelta(hours=3),
    )
    assert expired.status == "ready"
    assert expired.final_decision_present is False


def test_measurement_status_rejects_retrospective_case_selection() -> None:
    frozen_at = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
    item = InvestigationBenchmarkManifestCase(
        case_id="long-1",
        product_case_id="product-case-1",
        measurement_deadline=frozen_at + timedelta(hours=2),
    )
    with pytest.raises(ValueError, match="created after manifest frozen_at"):
        _measurement_status(
            item,
            _trace(created_at=frozen_at + timedelta(seconds=1)),
            frozen_at=frozen_at,
            measured_at=frozen_at + timedelta(minutes=1),
        )

    with pytest.raises(ValueError, match="already had a final decision before"):
        _measurement_status(
            item,
            _trace(
                created_at=frozen_at - timedelta(minutes=10),
                final_decision_at=frozen_at - timedelta(seconds=1),
            ),
            frozen_at=frozen_at,
            measured_at=frozen_at + timedelta(minutes=1),
        )


def test_measurement_status_accepts_decision_after_prospective_freeze() -> None:
    frozen_at = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
    decision_at = frozen_at + timedelta(minutes=10)
    item = InvestigationBenchmarkManifestCase(
        case_id="long-1",
        product_case_id="product-case-1",
        measurement_deadline=frozen_at + timedelta(hours=1),
    )
    status = _measurement_status(
        item,
        _trace(
            created_at=frozen_at - timedelta(minutes=5),
            final_decision_at=decision_at,
        ),
        frozen_at=frozen_at,
        measured_at=frozen_at + timedelta(minutes=20),
    )
    assert status.status == "ready"
    assert status.final_decision_at == decision_at
