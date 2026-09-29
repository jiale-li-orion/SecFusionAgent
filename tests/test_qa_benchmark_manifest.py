from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import create_async_engine

from apps.runtime_models import register_runtime_models
from packages.evaluation.benchmark import BenchmarkStore, DeploymentRevision
from packages.shared.config import Settings
from packages.shared.db import Base
from scripts import run_qa_benchmark as qa_runner
from scripts.run_qa_benchmark import QABenchmarkManifest, QABenchmarkManifestCase


def test_existing_smoke_manifest_remains_valid() -> None:
    manifest = QABenchmarkManifest.model_validate_json(
        Path("benchmarks/qa/smoke-v1.json").read_text(encoding="utf-8")
    )
    assert manifest.suite_id == "m6-qa-harness-smoke"
    assert len(manifest.cases) == 2
    assert all(item.prediction is not None for item in manifest.cases)


def test_real_product_candidate_is_pinned_live_product_content() -> None:
    manifest = QABenchmarkManifest.model_validate_json(
        Path("benchmarks/qa/real-product-v1.candidate.json").read_text(encoding="utf-8")
    )
    assert manifest.suite_id == "m6-real-product-qa"
    assert manifest.knowledge_revision == 596
    assert len(manifest.cases) == 13
    assert all(item.live_product_question is not None for item in manifest.cases)
    assert all("real" in item.tags and "candidate" in item.tags for item in manifest.cases)
    continuation = next(
        item for item in manifest.cases if item.case_id == "qa-real-3094-missing-cvss-continuation"
    )
    assert continuation.gold.completion_expectation == "continuation_requested"
    assert continuation.gold_provenance is not None
    assert continuation.gold_provenance.absence_checks[0].predicate == "cvss_score"


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


def test_live_product_question_manifest_requires_pinned_knowledge_revision() -> None:
    with pytest.raises(ValidationError, match="pinned knowledge_revision"):
        QABenchmarkManifest.model_validate(
            {
                "cases": [
                    {
                        "case_id": "qa-question-live-unpinned",
                        "live_product_question": {
                            "question": "What does current evidence establish?",
                            "cve_id": "CVE-2026-7273",
                            "task_kind": "lookup",
                        },
                        "gold": {
                            "case_id": "qa-question-live-unpinned",
                            "completion_expectation": "answered",
                        },
                    }
                ]
            }
        )


def test_manifest_rejects_mixing_two_live_product_denominators() -> None:
    with pytest.raises(ValidationError, match="cannot mix durable-Case live QA"):
        QABenchmarkManifest.model_validate(
            {
                "knowledge_revision": 596,
                "cases": [
                    {
                        "case_id": "qa-live-case",
                        "live_product_case_id": "investigation-live",
                        "gold": {
                            "case_id": "qa-live-case",
                            "completion_expectation": "answered",
                        },
                    },
                    {
                        "case_id": "qa-live-question",
                        "live_product_question": {
                            "question": "What is the CVSS score?",
                            "cve_id": "CVE-2026-7273",
                            "task_kind": "lookup",
                        },
                        "gold": {
                            "case_id": "qa-live-question",
                            "completion_expectation": "answered",
                        },
                    },
                ],
            }
        )
def test_live_product_case_is_an_explicit_prediction_source() -> None:
    case = QABenchmarkManifestCase.model_validate(
        {
            "case_id": "qa-live-1",
            "live_product_case_id": "investigation-live-1",
            "gold": {
                "case_id": "qa-live-1",
                "acceptable_unknowns": ["No evidence-backed conclusion is available."],
                "completion_expectation": "answered",
            },
        }
    )
    assert case.live_product_case_id == "investigation-live-1"
    assert case.product_case_id is None
    assert case.prediction is None


def test_live_product_case_rejects_supplied_latency() -> None:
    with pytest.raises(ValidationError, match="measures latency"):
        QABenchmarkManifestCase.model_validate(
            {
                "case_id": "qa-live-latency",
                "live_product_case_id": "investigation-live-1",
                "interactive_latency_seconds": 0.1,
                "gold": {
                    "case_id": "qa-live-latency",
                    "completion_expectation": "answered",
                },
            }
        )


def test_live_product_lookup_requires_bound_target_at_manifest_load() -> None:
    with pytest.raises(ValidationError, match="LOOKUP requires"):
        QABenchmarkManifestCase.model_validate(
            {
                "case_id": "qa-question-invalid-lookup",
                "live_product_question": {
                    "question": "What is known?",
                    "task_kind": "lookup",
                },
                "gold": {
                    "case_id": "qa-question-invalid-lookup",
                    "completion_expectation": "answered",
                },
            }
        )


def test_live_product_question_is_an_explicit_prediction_source() -> None:
    case = QABenchmarkManifestCase.model_validate(
        {
            "case_id": "qa-question-live-1",
            "live_product_question": {
                "question": "What does the current evidence establish?",
                "task_kind": "retrieve",
            },
            "gold": {
                "case_id": "qa-question-live-1",
                "acceptable_unknowns": ["No evidence-backed conclusion is available."],
                "completion_expectation": "answered",
            },
        }
    )
    assert case.live_product_question is not None
    assert case.live_product_question.task_kind.value == "retrieve"
    assert case.live_product_case_id is None
    assert case.product_case_id is None
    assert case.prediction is None


def test_live_product_question_rejects_supplied_latency() -> None:
    with pytest.raises(ValidationError, match="measures latency"):
        QABenchmarkManifestCase.model_validate(
            {
                "case_id": "qa-question-live-latency",
                "live_product_question": {
                    "question": "What is known?",
                    "task_kind": "retrieve",
                },
                "interactive_latency_seconds": 0.1,
                "gold": {
                    "case_id": "qa-question-live-latency",
                    "completion_expectation": "answered",
                },
            }
        )


@pytest.mark.asyncio
async def test_offline_runner_persists_staged_benchmark_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:", environment="test")

    async def fake_ensure_deployment(session, settings, **kwargs):
        del settings, kwargs
        deployment = DeploymentRevision(
            deployment_revision_id="deployment:qa-runner-test",
            git_commit="test",
            schema_revision="test",
            source_inventory_hash="a" * 64,
            vocabulary_revision="enrichment-v1",
            policy_revision="policy-test",
            capability_registry_revision="unbound",
            skill_registry_revision="seed-skills:test",
            model_provider_revision="unconfigured",
            configuration_digest="b" * 64,
            created_at=datetime(2026, 9, 29, tzinfo=UTC),
        )
        await BenchmarkStore().register_deployment(session, deployment)
        return deployment.deployment_revision_id

    monkeypatch.setattr(qa_runner, "get_settings", lambda: settings)
    monkeypatch.setattr(qa_runner, "create_engine", lambda database_url: engine)
    monkeypatch.setattr(qa_runner, "ensure_benchmark_deployment_revision", fake_ensure_deployment)

    manifest = QABenchmarkManifest.model_validate(
        {
            "suite_id": "m6-qa-runner-test",
            "cases": [
                {
                    "case_id": "qa-inline-1",
                    "prediction": {
                        "case_id": "qa-inline-1",
                        "unknowns": ["exploitability:unknown"],
                        "completion_status": "answered",
                        "interactive_latency_seconds": 0.1,
                    },
                    "gold": {
                        "case_id": "qa-inline-1",
                        "acceptable_unknowns": ["exploitability:unknown"],
                        "completion_expectation": "answered",
                    },
                }
            ],
        }
    )
    result = await qa_runner._run(
        manifest,
        suite_revision=1,
        deployment_revision_id=None,
    )
    assert result["execution_mode"] == "offline_scorer"
    assert result["case_count"] == 1
    assert result["case_scores"]["qa-inline-1"]["completion_correctness"] == 1.0


def test_manifest_rejects_mixed_live_and_offline_execution_modes() -> None:
    with pytest.raises(ValidationError, match="cannot mix live Product QA"):
        QABenchmarkManifest.model_validate(
            {
                "cases": [
                    {
                        "case_id": "qa-live",
                        "live_product_case_id": "investigation-live",
                        "gold": {
                            "case_id": "qa-live",
                            "completion_expectation": "answered",
                        },
                    },
                    {
                        "case_id": "qa-offline",
                        "prediction": {
                            "case_id": "qa-offline",
                            "completion_status": "answered",
                        },
                        "gold": {
                            "case_id": "qa-offline",
                            "completion_expectation": "answered",
                        },
                    },
                ]
            }
        )


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


def test_qa_manifest_accepts_closed_human_adjudication_history() -> None:
    case = QABenchmarkManifestCase.model_validate(
        {
            "case_id": "qa-adjudicated",
            "prediction": {
                "case_id": "qa-adjudicated",
                "conclusion_facts": ["affected:true"],
                "completion_status": "answered",
            },
            "gold": {
                "case_id": "qa-adjudicated",
                "required_facts": ["affected:true"],
                "completion_expectation": "answered",
            },
            "adjudications": [
                {
                    "adjudication_id": "adj-final",
                    "item_ref": "qa-adjudicated:fact:affected",
                    "annotator_ref": "human:reviewer-1",
                    "annotation": "Confirmed from frozen provider evidence.",
                    "evidence_refs": ["evidence:provider-1"],
                    "created_at": datetime(2026, 9, 28, tzinfo=UTC),
                    "final": True,
                }
            ],
        }
    )
    assert case.adjudications[0].final is True
