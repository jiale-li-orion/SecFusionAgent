from packages.evaluation.benchmark.metrics import CORE_METRICS
from packages.evaluation.metric_contract import (
    EVALUATION_METRIC_GROUPS,
    validate_evaluation_metric_contract,
)


def test_evaluation_metric_contract_is_fully_registered() -> None:
    validate_evaluation_metric_contract()
    assert len(EVALUATION_METRIC_GROUPS) >= 10
    grouped = {name for group in EVALUATION_METRIC_GROUPS for name in group.metric_names}
    assert set(CORE_METRICS) <= grouped


def test_core_metric_catalog_has_unique_names() -> None:
    names = list(CORE_METRICS)
    assert len(names) == len(set(names))
