from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apps.evaluation_runtime import InvestigationCompletionTrace
from packages.evaluation.investigation_readiness import (
    assess_prospective_investigation_case,
    render_investigation_readiness_markdown,
)
from scripts.run_investigation_benchmark import (
    MAX_PROSPECTIVE_FREEZE_LAG_SECONDS,
    InvestigationBenchmarkManifest,
    InvestigationBenchmarkManifestCase,
    _measurement_status,
    _version_reasoning_sources_match_gold,
)
from scripts.run_prospective_investigation_probe import (
    _claim_supports_expected_fixed_version,
    _relation_supports_expected_fixed_version,
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

    with pytest.raises(ValueError, match="not frozen promptly after creation"):
        _measurement_status(
            item,
            _trace(
                created_at=frozen_at
                - timedelta(seconds=MAX_PROSPECTIVE_FREEZE_LAG_SECONDS + 1)
            ),
            frozen_at=frozen_at,
            measured_at=frozen_at + timedelta(minutes=1),
        )

    with pytest.raises(ValueError, match="already had a final decision before"):
        _measurement_status(
            item,
            _trace(
                created_at=frozen_at - timedelta(minutes=4),
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


def test_investigation_readiness_rejects_old_or_decided_cases() -> None:
    frozen_at = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
    old = assess_prospective_investigation_case(
        created_at=frozen_at - timedelta(minutes=6),
        final_decision_at=None,
        frozen_at=frozen_at,
        max_freeze_lag_seconds=MAX_PROSPECTIVE_FREEZE_LAG_SECONDS,
    )
    assert old["eligible"] is False
    assert old["rejection_reason"] == "freeze_lag_exceeded"

    decided = assess_prospective_investigation_case(
        created_at=frozen_at - timedelta(minutes=2),
        final_decision_at=frozen_at - timedelta(seconds=1),
        frozen_at=frozen_at,
        max_freeze_lag_seconds=MAX_PROSPECTIVE_FREEZE_LAG_SECONDS,
    )
    assert decided["eligible"] is False
    assert decided["rejection_reason"] == "final_decision_already_visible"


def test_investigation_readiness_markdown_projects_machine_result() -> None:
    payload = {
        "generated_at": "2026-10-01T16:00:00+00:00",
        "model_provider_status": "unconfigured",
        "launch_readiness": "blocked_model_provider_unconfigured",
        "case_count": 1,
        "eligible_case_count": 0,
        "cases": [
            {
                "case_id": "case-1",
                "case_status": "active",
                "created_at": "2026-09-27T13:20:15+00:00",
                "final_decision_at": None,
                "eligible": False,
                "freeze_lag_seconds": 300000.0,
                "rejection_reason": "freeze_lag_exceeded",
            }
        ],
    }
    rendered = render_investigation_readiness_markdown(payload)
    assert "blocked_model_provider_unconfigured" in rendered
    assert "`freeze_lag_exceeded`" in rendered


def test_version_reasoning_gold_requires_relation_anchor_but_allows_same_target_claim() -> None:
    assert _version_reasoning_sources_match_gold(
        ["relation:rel-fixed", "claim:claim-details"],
        allowed_relation_ids={"rel-fixed"},
        allowed_claim_ids={"claim-details"},
    )
    assert not _version_reasoning_sources_match_gold(
        ["claim:claim-details"],
        allowed_relation_ids={"rel-fixed"},
        allowed_claim_ids={"claim-details"},
    )
    assert not _version_reasoning_sources_match_gold(
        ["relation:rel-wrong", "claim:claim-details"],
        allowed_relation_ids={"rel-fixed"},
        allowed_claim_ids={"claim-details"},
    )
    assert not _version_reasoning_sources_match_gold(
        ["relation:rel-fixed", "evidence:e-1"],
        allowed_relation_ids={"rel-fixed"},
        allowed_claim_ids=set(),
    )


def test_prospective_version_gold_miner_accepts_fixed_boundary_forms() -> None:
    assert _relation_supports_expected_fixed_version(
        relation_type="fixed-version",
        target_canonical_key="software-version:pip:vllm:0.22.0",
        qualifier={},
        expected_fixed_version="0.22.0",
    )
    assert _relation_supports_expected_fixed_version(
        relation_type="affects-package",
        target_canonical_key="package:pip:vllm",
        qualifier={"first_patched_version": "0.22.0"},
        expected_fixed_version="0.22.0",
    )
    assert _relation_supports_expected_fixed_version(
        relation_type="applicability-status",
        target_canonical_key="package:pip:vllm",
        qualifier={"state": "affected", "version_range": ">= 0.3.0, < 0.22.0"},
        expected_fixed_version="0.22.0",
    )
    assert _claim_supports_expected_fixed_version(
        predicate="osv_details",
        value="This vulnerability is fixed in 0.22.0.",
        expected_fixed_version="0.22.0",
    )
