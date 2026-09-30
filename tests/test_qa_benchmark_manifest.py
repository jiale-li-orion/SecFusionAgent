from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import create_async_engine

from apps.evaluation_runtime import (
    ProductQuestionQAExecution,
    ProductQuestionSessionTrace,
    ProductQuestionSessionTurnTrace,
)
from apps.runtime_models import register_runtime_models
from packages.evaluation.benchmark import BenchmarkStore, DeploymentRevision
from packages.evaluation.qa import QAPrediction
from packages.shared.config import Settings
from packages.shared.db import Base
from packages.task_runtime.contracts.models import TaskKind
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
    assert manifest.knowledge_revision == 606
    assert len(manifest.cases) == 14
    assert all(item.live_product_question is not None for item in manifest.cases)
    assert all("real" in item.tags and "candidate" in item.tags for item in manifest.cases)
    continuation = next(
        item for item in manifest.cases if item.case_id == "qa-real-3094-missing-cvss-continuation"
    )
    assert continuation.gold.completion_expectation == "continuation_requested"
    assert continuation.gold_provenance is not None
    assert continuation.gold_provenance.absence_checks[0].predicate == "cvss_score"
    multihop = next(
        item
        for item in manifest.cases
        if item.case_id == "qa-real-48746-pr-merge-commit-multihop"
    )
    assert multihop.gold.required_relation_paths == [
        [
            "cve:CVE-2026-48746",
            "references-development-object",
            "github:vllm-project/vllm:pull:43426",
            "merged-as",
            "git:commit:2b94d1c0caf69d4108d720986f4e792960b02cf7",
        ]
    ]


def test_real_session_candidate_is_pinned_two_turn_product_content() -> None:
    manifest = QABenchmarkManifest.model_validate_json(
        Path("benchmarks/qa/real-session-v1.candidate.json").read_text(encoding="utf-8")
    )
    assert manifest.suite_id == "m6-real-product-qa-session"
    assert manifest.knowledge_revision == 606
    assert manifest.cases == []
    assert len(manifest.sessions) == 1
    session_case = manifest.sessions[0]
    assert session_case.state_carry_policy == "targets_and_outcomes_v1"
    assert [turn.turn_id for turn in session_case.turns] == ["cvss", "epss-followup"]
    assert session_case.turns[0].question.cve_id == "CVE-2026-7273"
    assert session_case.turns[1].question.cve_id is None
    assert session_case.turns[1].question.object_id is None
    assert session_case.turns[1].expected_target_keys == ["cve:CVE-2026-7273"]


def test_session_case_rejects_followup_that_rebinds_target() -> None:
    with pytest.raises(ValidationError, match="must rely on Product session target carry"):
        QABenchmarkManifest.model_validate(
            {
                "knowledge_revision": 606,
                "sessions": [
                    {
                        "case_id": "qa-session-invalid-rebind",
                        "turns": [
                            {
                                "turn_id": "one",
                                "question": {
                                    "question": "What is the score?",
                                    "cve_id": "CVE-2026-7273",
                                    "task_kind": "lookup",
                                },
                                "gold": {
                                    "case_id": "qa-session-invalid-rebind#turn:one",
                                    "completion_expectation": "answered",
                                },
                            },
                            {
                                "turn_id": "two",
                                "question": {
                                    "question": "What about EPSS?",
                                    "cve_id": "CVE-2026-7273",
                                    "task_kind": "lookup",
                                },
                                "expected_target_keys": ["cve:CVE-2026-7273"],
                                "gold": {
                                    "case_id": "qa-session-invalid-rebind#turn:two",
                                    "completion_expectation": "answered",
                                },
                            },
                        ],
                    }
                ],
            }
        )


def test_session_trace_metrics_use_durable_context_chain_and_target_keys() -> None:
    manifest = QABenchmarkManifest.model_validate_json(
        Path("benchmarks/qa/real-session-v1.candidate.json").read_text(encoding="utf-8")
    )
    turns = [
        ProductQuestionSessionTurnTrace(
            turn_index=1,
            request_id="request-1",
            target_keys=["cve:CVE-2026-7273"],
            knowledge_revision=606,
            context_id="context:1",
            parent_context_id=None,
            decision_ref="decision:1",
        ),
        ProductQuestionSessionTurnTrace(
            turn_index=2,
            request_id="request-2",
            target_keys=["cve:CVE-2026-7273"],
            knowledge_revision=606,
            context_id="context:2",
            parent_context_id="context:1",
            decision_ref="decision:2",
        ),
    ]
    assert qa_runner._session_context_chain_correctness(turns) == 1.0
    assert (
        qa_runner._session_target_carry_correctness(turns, manifest.sessions[0].turns)
        == 1.0
    )
    broken = [turns[0], turns[1].model_copy(update={"parent_context_id": "context:other"})]
    assert qa_runner._session_context_chain_correctness(broken) == 0.0
    assert qa_runner._session_retrieval_overlap_rate(turns, manifest.sessions[0].turns) is None

    retrieval_turns = [
        turns[0].model_copy(
            update={"retrieval_refs": ["document-chunk:a@1", "document-chunk:b@1"]}
        ),
        turns[1].model_copy(
            update={"retrieval_refs": ["document-chunk:b@1", "document-chunk:c@1"]}
        ),
    ]
    expected_turns = [
        manifest.sessions[0].turns[0].model_copy(
            update={
                "question": manifest.sessions[0].turns[0].question.model_copy(
                    update={"task_kind": TaskKind.RETRIEVE}
                )
            }
        ),
        manifest.sessions[0].turns[1].model_copy(
            update={
                "question": manifest.sessions[0].turns[1].question.model_copy(
                    update={"task_kind": TaskKind.RETRIEVE}
                )
            }
        ),
    ]
    assert qa_runner._session_retrieval_overlap_rate(retrieval_turns, expected_turns) == 0.5


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


def test_live_product_question_rejects_supplied_relation_paths() -> None:
    with pytest.raises(ValidationError, match="derived from runtime ContextManifest"):
        QABenchmarkManifestCase.model_validate(
            {
                "case_id": "qa-question-live-path",
                "live_product_question": {
                    "question": "Which commit was the referenced PR merged as?",
                    "cve_id": "CVE-2026-48746",
                    "task_kind": "lookup",
                },
                "relation_paths": [
                    [
                        "cve:CVE-2026-48746",
                        "references-development-object",
                        "github:vllm-project/vllm:pull:43426",
                        "merged-as",
                        "git:commit:2b94d1c0",
                    ]
                ],
                "gold": {
                    "case_id": "qa-question-live-path",
                    "completion_expectation": "answered",
                },
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


@pytest.mark.asyncio
async def test_session_runner_reuses_product_session_and_scores_each_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        environment="test",
        model_base_url="http://127.0.0.1:9",
        model_name="fixture-session-model",
    )

    async def fake_ensure_deployment(session, settings, **kwargs):
        del settings, kwargs
        deployment = DeploymentRevision(
            deployment_revision_id="deployment:qa-session-runner-test",
            git_commit="test",
            schema_revision="test",
            source_inventory_hash="a" * 64,
            vocabulary_revision="enrichment-v1",
            policy_revision="policy-test",
            capability_registry_revision="unbound",
            skill_registry_revision="seed-skills:test",
            model_provider_revision="fixture-session-model",
            configuration_digest="c" * 64,
            created_at=datetime(2026, 9, 30, tzinfo=UTC),
        )
        await BenchmarkStore().register_deployment(session, deployment)
        return deployment.deployment_revision_id

    calls: list[tuple[str, str | None]] = []

    async def fake_execute(factory, **kwargs):
        del factory
        benchmark_case_id = kwargs["benchmark_case_id"]
        incoming_session = kwargs["session_id"]
        calls.append((benchmark_case_id, incoming_session))
        turn_index = len(calls)
        fact = "fact:one" if turn_index == 1 else "fact:two"
        return ProductQuestionQAExecution(
            prediction=QAPrediction(
                case_id=benchmark_case_id,
                conclusion_facts=[fact],
                completion_status="answered",
                execution_refs=[f"execution:turn-{turn_index}"],
            ),
            session_id="question-session:test",
            turn_index=turn_index,
        )

    async def fake_trace(session, session_id):
        del session
        assert session_id == "question-session:test"
        return ProductQuestionSessionTrace(
            session_id=session_id,
            turns=[
                ProductQuestionSessionTurnTrace(
                    turn_index=1,
                    request_id="request-1",
                    target_keys=["cve:CVE-2026-7273"],
                    knowledge_revision=606,
                    context_id="context:1",
                    decision_ref="decision:1",
                ),
                ProductQuestionSessionTurnTrace(
                    turn_index=2,
                    request_id="request-2",
                    target_keys=["cve:CVE-2026-7273"],
                    knowledge_revision=606,
                    context_id="context:2",
                    parent_context_id="context:1",
                    decision_ref="decision:2",
                ),
            ],
        )

    monkeypatch.setattr(qa_runner, "get_settings", lambda: settings)
    monkeypatch.setattr(qa_runner, "create_engine", lambda database_url: engine)
    monkeypatch.setattr(qa_runner, "ensure_benchmark_deployment_revision", fake_ensure_deployment)
    monkeypatch.setattr(qa_runner, "create_recorded_model_provider", lambda *args: object())
    monkeypatch.setattr(qa_runner, "execute_product_question_qa_execution", fake_execute)
    monkeypatch.setattr(qa_runner, "load_product_question_session_trace", fake_trace)

    manifest = QABenchmarkManifest.model_validate(
        {
            "suite_id": "m6-qa-session-runner-test",
            "knowledge_revision": 606,
            "sessions": [
                {
                    "case_id": "qa-session-test",
                    "turns": [
                        {
                            "turn_id": "one",
                            "question": {
                                "question": "What is fact one?",
                                "cve_id": "CVE-2026-7273",
                                "task_kind": "lookup",
                            },
                            "expected_target_keys": ["cve:CVE-2026-7273"],
                            "gold": {
                                "case_id": "qa-session-test#turn:one",
                                "required_facts": ["fact:one"],
                                "completion_expectation": "answered",
                            },
                        },
                        {
                            "turn_id": "two",
                            "question": {
                                "question": "What about fact two?",
                                "task_kind": "lookup",
                            },
                            "expected_target_keys": ["cve:CVE-2026-7273"],
                            "gold": {
                                "case_id": "qa-session-test#turn:two",
                                "required_facts": ["fact:two"],
                                "completion_expectation": "answered",
                            },
                        },
                    ],
                }
            ],
        }
    )
    result = await qa_runner._run(
        manifest,
        suite_revision=1,
        deployment_revision_id=None,
    )
    assert result["execution_mode"] == "live_external"
    session_score = result["session_scores"]["qa-session-test"]
    assert session_score["context_chain_correctness"] == 1.0
    assert session_score["target_carry_correctness"] == 1.0
    assert session_score["turn_scores"]["one"]["answer_accuracy"] == 1.0
    assert session_score["turn_scores"]["two"]["answer_accuracy"] == 1.0
    assert calls == [
        ("qa-session-test#turn:one", None),
        ("qa-session-test#turn:two", "question-session:test"),
    ]


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
