from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

import pytest
from pydantic import ValidationError

from packages.evaluation.m1_m3 import (
    PRODUCT_SOURCE_CATEGORIES,
    PRODUCT_SOURCE_CATEGORY_ORDER,
    EnrichmentFactKey,
    EnrichmentPrediction,
    MonitoringLatencySample,
    SourceDeliveryKey,
    SourcePortfolioCategory,
    monitoring_latency_report,
    score_enrichment,
    source_coverage_report,
    source_delivery_coverage,
)
from packages.intelligence.knowledge.vocabulary import EnrichmentDimension
from packages.sources.inventory import load_source_inventory


def _fact(
    *,
    value: str,
    dimension: EnrichmentDimension = EnrichmentDimension.SEVERITY,
    term: str = "cvss_score",
    kind: Literal["claim", "relation"] = "claim",
) -> EnrichmentFactKey:
    return EnrichmentFactKey(
        root_object_key="cve:CVE-2026-0001",
        root_object_type="Vulnerability",
        kind=kind,
        dimension=dimension,
        predicate_or_relation_type=term,
        normalized_value_or_target_id=value,
    )


def test_source_inventory_closes_all_eight_product_source_categories() -> None:
    report = source_coverage_report(load_source_inventory(Path("config/source-inventory.json")))
    assert len(report.portfolio_categories) == 8
    assert report.source_category_count == 8
    assert set(report.supported_source_categories) == PRODUCT_SOURCE_CATEGORIES
    assert tuple(report.supported_source_categories) == PRODUCT_SOURCE_CATEGORY_ORDER
    assert report.unsupported_source_categories == []
    assert SourcePortfolioCategory.ASSETS in report.supported_source_categories


def test_source_delivery_coverage_uses_fixed_window_gold_and_reports_unexpected_items() -> None:
    report = source_delivery_coverage(
        expected_keys=[
            SourceDeliveryKey(source_id="source-a", external_object_id="a", external_revision="r1"),
            SourceDeliveryKey(source_id="source-b", external_object_id="b", external_revision="r1"),
            SourceDeliveryKey(
                source_id="source-c", external_object_id="c", content_hash="sha256:c2"
            ),
        ],
        accepted_keys=[
            SourceDeliveryKey(source_id="source-a", external_object_id="a", external_revision="r1"),
            SourceDeliveryKey(
                source_id="source-c", external_object_id="c", content_hash="sha256:c2"
            ),
            SourceDeliveryKey(
                source_id="source-extra",
                external_object_id="unexpected",
                external_revision="r1",
            ),
        ],
    )
    assert report.expected_items == 3
    assert report.accepted_expected_items == 2
    assert report.missed_items == 1
    assert report.unexpected_items == 1
    assert report.coverage == pytest.approx(2 / 3)


def test_source_delivery_key_requires_revision_or_content_hash() -> None:
    with pytest.raises(ValidationError, match="external_revision or content_hash"):
        SourceDeliveryKey(source_id="source-a", external_object_id="a")


def test_monitoring_latency_reports_evaluable_coverage_and_p95() -> None:
    now = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
    report = monitoring_latency_report(
        [
            MonitoringLatencySample("a", now - timedelta(hours=1), now),
            MonitoringLatencySample("b", now - timedelta(hours=5), now),
            MonitoringLatencySample("c", now - timedelta(hours=7), now),
            MonitoringLatencySample("unknown-publish-time", None, now),
        ]
    )
    assert report.total_samples == 4
    assert report.evaluable_samples == 3
    assert report.evaluable_coverage == 0.75
    assert report.p50_seconds == 5 * 3600
    assert report.p95_seconds == 7 * 3600
    assert report.max_seconds == 7 * 3600
    assert report.within_6h_rate == pytest.approx(2 / 3)


def test_enrichment_score_is_closed_set_and_dimension_aware() -> None:
    cvss = _fact(value="9.8")
    exploit = _fact(
        value="true",
        dimension=EnrichmentDimension.EXPLOIT_STATE,
        term="known_exploited",
    )
    wrong_cvss = _fact(value="8.8")
    score = score_enrichment(
        gold=[cvss, exploit],
        predicted=[
            EnrichmentPrediction(
                fact=cvss, evidence_ref_ids=("evidence:cvss",), evidence_correct=True
            ),
            EnrichmentPrediction(
                fact=wrong_cvss, evidence_ref_ids=("evidence:wrong",), evidence_correct=True
            ),
        ],
    )
    assert (score.true_positive, score.false_positive, score.false_negative) == (1, 1, 1)
    assert score.micro_precision == 0.5
    assert score.micro_recall == 0.5
    by_dimension = {item.dimension: item for item in score.dimensions}
    assert by_dimension[EnrichmentDimension.SEVERITY].precision == 0.5
    assert by_dimension[EnrichmentDimension.SEVERITY].recall == 1.0
    assert by_dimension[EnrichmentDimension.EXPLOIT_STATE].precision == 0.0
    assert by_dimension[EnrichmentDimension.EXPLOIT_STATE].recall == 0.0


def test_enrichment_zero_predictions_do_not_report_perfect_precision_when_gold_exists() -> None:
    cvss = _fact(value="9.8")
    score = score_enrichment(gold=[cvss], predicted=[])
    assert score.micro_precision == 0.0
    assert score.micro_recall == 0.0


def test_valid_evidence_dominates_invalid_duplicate_for_same_fact() -> None:
    cvss = _fact(value="9.8")
    score = score_enrichment(
        gold=[cvss],
        predicted=[
            EnrichmentPrediction(fact=cvss, evidence_ref_ids=(), evidence_correct=False),
            EnrichmentPrediction(
                fact=cvss,
                evidence_ref_ids=("evidence:valid",),
                evidence_correct=True,
            ),
        ],
    )
    assert (score.true_positive, score.false_positive, score.false_negative) == (1, 0, 0)
    assert score.micro_precision == 1.0
    assert score.micro_recall == 1.0


def test_enrichment_prediction_without_valid_evidence_is_fp_and_leaves_gold_fn() -> None:
    cvss = _fact(value="9.8")
    score = score_enrichment(
        gold=[cvss],
        predicted=[EnrichmentPrediction(fact=cvss, evidence_ref_ids=(), evidence_correct=False)],
    )
    assert (score.true_positive, score.false_positive, score.false_negative) == (0, 1, 1)
    assert score.micro_precision == 0.0
    assert score.micro_recall == 0.0


def test_enrichment_fact_validates_relation_shape_and_required_qualifiers() -> None:
    fact = EnrichmentFactKey(
        root_object_key="cve:CVE-2026-0001",
        root_object_type="Vulnerability",
        kind="relation",
        dimension=EnrichmentDimension.VERSION_APPLICABILITY,
        predicate_or_relation_type="applicability-status",
        normalized_value_or_target_id="pkg:pypi/vllm",
        target_object_type="Package",
        qualifier_keys=("state", "source_semantics"),
        normalized_qualifier='{"source_semantics":"osv_range","state":"affected"}',
    )
    assert fact.target_object_type == "Package"

    with pytest.raises(ValidationError, match="target type does not match"):
        EnrichmentFactKey(
            root_object_key="cve:CVE-2026-0001",
            root_object_type="Vulnerability",
            kind="relation",
            dimension=EnrichmentDimension.VERSION_APPLICABILITY,
            predicate_or_relation_type="applicability-status",
            normalized_value_or_target_id="paper:wrong-target",
            target_object_type="ResearchWork",
            qualifier_keys=("state", "source_semantics"),
        )

    with pytest.raises(ValidationError, match="missing required qualifier"):
        EnrichmentFactKey(
            root_object_key="cve:CVE-2026-0001",
            root_object_type="Vulnerability",
            kind="relation",
            dimension=EnrichmentDimension.VERSION_APPLICABILITY,
            predicate_or_relation_type="applicability-status",
            normalized_value_or_target_id="pkg:pypi/vllm",
            target_object_type="Package",
            qualifier_keys=("state",),
        )


def test_supporting_graph_edges_do_not_enter_competition_fact_key() -> None:
    with pytest.raises(ValidationError, match="non-benchmarked canonical term"):
        EnrichmentFactKey(
            root_object_key="release:v1.0",
            root_object_type="Release",
            kind="relation",
            dimension=EnrichmentDimension.FIX_REMEDIATION,
            predicate_or_relation_type="release-contains-commit",
            normalized_value_or_target_id="commit:abc",
            target_object_type="Commit",
        )


def test_enrichment_fact_rejects_exploratory_or_wrong_dimension_terms() -> None:
    with pytest.raises(ValidationError, match="non-canonical term"):
        _fact(value="x", term="model_invented_relation")
    with pytest.raises(ValidationError, match="dimension does not match"):
        _fact(
            value="9.8",
            dimension=EnrichmentDimension.EXPLOIT_STATE,
            term="cvss_score",
        )
