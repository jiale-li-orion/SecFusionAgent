from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts.run_qa_benchmark import QABenchmarkManifest, QABenchmarkManifestCase


def test_existing_smoke_manifest_remains_valid() -> None:
    manifest = QABenchmarkManifest.model_validate_json(
        Path("benchmarks/qa/smoke-v1.json").read_text(encoding="utf-8")
    )
    assert manifest.suite_id == "m6-qa-harness-smoke"
    assert len(manifest.cases) == 2
    assert all(item.prediction is not None for item in manifest.cases)


def test_product_case_uses_persisted_case_as_prediction_source() -> None:
    case = QABenchmarkManifestCase.model_validate(
        {
            "case_id": "qa-product-1",
            "product_case_id": "investigation-1",
            "gold": {
                "case_id": "qa-product-1",
                "required_facts": ["affected:true"],
                "required_citation_facts": ["affected:true"],
                "completion_expectation": "answered",
            },
            "citation_support": {"0:evidence:nvd-1": True},
        }
    )
    assert case.prediction is None
    assert case.product_case_id == "investigation-1"
    assert case.citation_support == {"0:evidence:nvd-1": True}


def test_qa_manifest_case_requires_exactly_one_prediction_source() -> None:
    payload = {
        "case_id": "qa-invalid",
        "gold": {
            "case_id": "qa-invalid",
            "completion_expectation": "answered",
        },
    }
    with pytest.raises(ValidationError, match="exactly one"):
        QABenchmarkManifestCase.model_validate(payload)
