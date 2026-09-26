from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import ceil
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.intelligence.knowledge.vocabulary import (
    VOCABULARY_REVISION,
    EnrichmentDimension,
    canonical_term,
)
from packages.sources.inventory import SourceInventory


class SourcePortfolioCategory(StrEnum):
    VULNERABILITY = "vulnerability"
    DEVELOPMENT = "development"
    ACADEMIC = "academic"
    VENDOR = "vendor"
    INDEPENDENT = "independent"
    NORMATIVE = "normative"
    INCIDENTS = "incidents"
    ASSETS = "assets"


PRODUCT_SOURCE_CATEGORY_ORDER: tuple[SourcePortfolioCategory, ...] = (
    SourcePortfolioCategory.VULNERABILITY,
    SourcePortfolioCategory.DEVELOPMENT,
    SourcePortfolioCategory.ACADEMIC,
    SourcePortfolioCategory.VENDOR,
    SourcePortfolioCategory.INDEPENDENT,
    SourcePortfolioCategory.NORMATIVE,
    SourcePortfolioCategory.ASSETS,
    SourcePortfolioCategory.INCIDENTS,
)
PRODUCT_SOURCE_CATEGORIES = frozenset(PRODUCT_SOURCE_CATEGORY_ORDER)


class SourceCoverageReport(BaseModel):
    supported_source_categories: list[SourcePortfolioCategory]
    unsupported_source_categories: list[SourcePortfolioCategory]
    portfolio_categories: list[SourcePortfolioCategory]

    @property
    def source_category_count(self) -> int:
        return len(self.supported_source_categories)


@dataclass(frozen=True, slots=True)
class MonitoringLatencySample:
    sample_id: str
    published_at: datetime | None
    available_at: datetime

    @property
    def latency_seconds(self) -> float | None:
        if self.published_at is None:
            return None
        value = (self.available_at - self.published_at).total_seconds()
        if value < 0:
            raise ValueError(f"negative monitoring latency for sample={self.sample_id}")
        return value


class SourceDeliveryKey(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_id: str
    external_object_id: str
    external_revision: str | None = None
    content_hash: str | None = None

    @model_validator(mode="after")
    def require_revision_or_hash(self) -> SourceDeliveryKey:
        if not self.external_revision and not self.content_hash:
            raise ValueError("source delivery key requires external_revision or content_hash")
        return self


class SourceDeliveryCoverageReport(BaseModel):
    expected_items: int
    accepted_expected_items: int
    missed_items: int
    unexpected_items: int
    coverage: float


class MonitoringLatencyReport(BaseModel):
    total_samples: int
    evaluable_samples: int
    evaluable_coverage: float
    p50_seconds: float | None
    p95_seconds: float | None
    max_seconds: float | None
    within_6h_rate: float | None


class EnrichmentFactKey(BaseModel):
    model_config = ConfigDict(frozen=True)

    root_object_key: str
    root_object_type: str
    kind: Literal["claim", "relation"]
    dimension: EnrichmentDimension
    predicate_or_relation_type: str
    normalized_value_or_target_id: str
    target_object_type: str | None = None
    qualifier_keys: tuple[str, ...] = ()
    normalized_qualifier: str = "{}"
    temporal_scope: str = "current"
    vocabulary_revision: str = VOCABULARY_REVISION

    @model_validator(mode="after")
    def validate_vocabulary(self) -> EnrichmentFactKey:
        term = canonical_term(self.kind, self.predicate_or_relation_type)
        if term is None:
            raise ValueError(
                f"enrichment fact uses non-canonical term: {self.predicate_or_relation_type}"
            )
        if term.dimension is not self.dimension:
            raise ValueError(
                "enrichment fact dimension does not match canonical vocabulary: "
                f"{self.predicate_or_relation_type} -> {term.dimension.value}"
            )
        if not term.benchmarked:
            raise ValueError(
                f"enrichment fact uses non-benchmarked canonical term: "
                f"{self.predicate_or_relation_type}"
            )
        if term.subject_types and self.root_object_type not in term.subject_types:
            raise ValueError(
                "enrichment fact root type does not match canonical vocabulary: "
                f"{self.root_object_type} not in {term.subject_types}"
            )
        if term.target_types:
            if self.target_object_type not in term.target_types:
                raise ValueError(
                    "enrichment fact target type does not match canonical vocabulary: "
                    f"{self.target_object_type!r} not in {term.target_types}"
                )
        elif self.kind == "claim" and self.target_object_type is not None:
            raise ValueError("claim enrichment fact cannot have target_object_type")
        if not set(term.required_qualifier_keys) <= set(self.qualifier_keys):
            raise ValueError(
                "enrichment fact is missing required qualifier keys: "
                f"{term.required_qualifier_keys}"
            )
        if self.vocabulary_revision != VOCABULARY_REVISION:
            raise ValueError(
                f"unsupported vocabulary_revision={self.vocabulary_revision!r}; "
                f"expected {VOCABULARY_REVISION!r}"
            )
        return self


class EnrichmentPrediction(BaseModel):
    model_config = ConfigDict(frozen=True)

    fact: EnrichmentFactKey
    evidence_ref_ids: tuple[str, ...] = ()
    evidence_correct: bool = False

    @property
    def evidence_valid(self) -> bool:
        return bool(self.evidence_ref_ids) and self.evidence_correct


class EnrichmentBenchmarkCase(BaseModel):
    case_id: str
    world_snapshot: str
    source_availability_snapshot: str
    source_revisions: list[str] = Field(default_factory=list)
    vocabulary_revision: str = VOCABULARY_REVISION
    evaluator_revision: str
    gold: list[EnrichmentFactKey]


class EnrichmentDimensionScore(BaseModel):
    dimension: EnrichmentDimension
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float


class EnrichmentScore(BaseModel):
    true_positive: int
    false_positive: int
    false_negative: int
    micro_precision: float
    micro_recall: float
    dimension_macro_precision: float
    dimension_macro_recall: float
    dimensions: list[EnrichmentDimensionScore]


def source_coverage_report(inventory: SourceInventory) -> SourceCoverageReport:
    portfolio = {SourcePortfolioCategory(item.category) for item in inventory.entries}
    supported = {
        SourcePortfolioCategory(item.category)
        for item in inventory.entries
        if item.coverage == "owned" and item.mode in {"fixed_provider", "grouped_member"}
    }
    source_supported = [item for item in PRODUCT_SOURCE_CATEGORY_ORDER if item in supported]
    source_unsupported = [item for item in PRODUCT_SOURCE_CATEGORY_ORDER if item not in supported]
    return SourceCoverageReport(
        supported_source_categories=source_supported,
        unsupported_source_categories=source_unsupported,
        portfolio_categories=sorted(portfolio, key=str),
    )


def source_delivery_coverage(
    *,
    expected_keys: Iterable[SourceDeliveryKey],
    accepted_keys: Iterable[SourceDeliveryKey],
) -> SourceDeliveryCoverageReport:
    expected = set(expected_keys)
    accepted = set(accepted_keys)
    matched = expected & accepted
    missed = expected - accepted
    unexpected = accepted - expected
    return SourceDeliveryCoverageReport(
        expected_items=len(expected),
        accepted_expected_items=len(matched),
        missed_items=len(missed),
        unexpected_items=len(unexpected),
        coverage=len(matched) / len(expected) if expected else 1.0,
    )


def monitoring_latency_report(
    samples: Iterable[MonitoringLatencySample],
) -> MonitoringLatencyReport:
    values = list(samples)
    latencies = [value for item in values if (value := item.latency_seconds) is not None]
    total = len(values)
    evaluable = len(latencies)
    if not latencies:
        return MonitoringLatencyReport(
            total_samples=total,
            evaluable_samples=0,
            evaluable_coverage=0.0 if total else 1.0,
            p50_seconds=None,
            p95_seconds=None,
            max_seconds=None,
            within_6h_rate=None,
        )
    ordered = sorted(latencies)
    return MonitoringLatencyReport(
        total_samples=total,
        evaluable_samples=evaluable,
        evaluable_coverage=evaluable / total if total else 1.0,
        p50_seconds=_nearest_rank(ordered, 0.50),
        p95_seconds=_nearest_rank(ordered, 0.95),
        max_seconds=ordered[-1],
        within_6h_rate=sum(value <= 6 * 3600 for value in ordered) / evaluable,
    )


def score_enrichment(
    *,
    gold: Iterable[EnrichmentFactKey],
    predicted: Iterable[EnrichmentPrediction],
) -> EnrichmentScore:
    gold_set = set(gold)
    predictions = list(predicted)
    valid_predicted_set = {item.fact for item in predictions if item.evidence_valid}
    invalid_predicted_set = {item.fact for item in predictions if not item.evidence_valid}
    invalid_only_set = invalid_predicted_set - valid_predicted_set
    all_predicted_set = valid_predicted_set | invalid_only_set

    tp_set = gold_set & valid_predicted_set
    fp_set = (valid_predicted_set - gold_set) | invalid_only_set
    fn_set = gold_set - tp_set

    dimensions = sorted(
        {item.dimension for item in gold_set | all_predicted_set},
        key=str,
    )
    dimension_scores: list[EnrichmentDimensionScore] = []
    for dimension in dimensions:
        d_gold = {item for item in gold_set if item.dimension == dimension}
        d_valid = {item for item in valid_predicted_set if item.dimension == dimension}
        d_invalid = {item for item in invalid_only_set if item.dimension == dimension}
        d_tp_set = d_gold & d_valid
        d_tp = len(d_tp_set)
        d_fp = len((d_valid - d_gold) | d_invalid)
        d_fn = len(d_gold - d_tp_set)
        dimension_scores.append(
            EnrichmentDimensionScore(
                dimension=dimension,
                true_positive=d_tp,
                false_positive=d_fp,
                false_negative=d_fn,
                precision=_precision(d_tp, d_fp, d_fn),
                recall=_recall(d_tp, d_fn),
            )
        )

    tp = len(tp_set)
    fp = len(fp_set)
    fn = len(fn_set)
    return EnrichmentScore(
        true_positive=tp,
        false_positive=fp,
        false_negative=fn,
        micro_precision=_precision(tp, fp, fn),
        micro_recall=_recall(tp, fn),
        dimension_macro_precision=(
            sum(item.precision for item in dimension_scores) / len(dimension_scores)
            if dimension_scores
            else 1.0
        ),
        dimension_macro_recall=(
            sum(item.recall for item in dimension_scores) / len(dimension_scores)
            if dimension_scores
            else 1.0
        ),
        dimensions=dimension_scores,
    )


def _precision(tp: int, fp: int, fn: int) -> float:
    denominator = tp + fp
    if denominator:
        return tp / denominator
    return 1.0 if fn == 0 else 0.0


def _recall(tp: int, fn: int) -> float:
    denominator = tp + fn
    return tp / denominator if denominator else 1.0


def _nearest_rank(ordered: list[float], percentile: float) -> float:
    rank = max(1, ceil(percentile * len(ordered)))
    return ordered[rank - 1]
