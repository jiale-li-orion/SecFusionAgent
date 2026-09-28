from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import JsonValue
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps import evaluation_runtime
from apps.runtime_models import register_runtime_models
from packages.evaluation.benchmark import BenchmarkStore, DeploymentRevision
from packages.investigation.state.contracts import InvestigationState, InvestigationStateItem
from packages.reasoning.citation import DecisionCitation
from packages.reasoning.decision import ConclusionType, DecisionConclusion, DecisionResult
from packages.shared.config import Settings
from packages.shared.db import Base


def _deployment(identity: str) -> DeploymentRevision:
    return DeploymentRevision(
        deployment_revision_id=identity,
        git_commit="abc+dirty.123",
        schema_revision="20260927_0025",
        source_inventory_hash="a" * 64,
        vocabulary_revision="enrichment-v1",
        policy_revision="policy-v1",
        capability_registry_revision="unbound",
        skill_registry_revision="seed-skills:test",
        model_provider_revision="unconfigured",
        configuration_digest="b" * 64,
        created_at=datetime(2026, 9, 27, tzinfo=UTC),
    )


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _state(*, current_decision: dict[str, JsonValue] | None = None) -> InvestigationState:
    return InvestigationState(
        case_id="product-case-1",
        case_revision=5,
        goal="Determine whether the deployment is affected",
        targets=["vulnerability:CVE-2026-0001"],
        confirmed=[
            InvestigationStateItem(
                proposition="affected:true",
                target_ref="vulnerability:CVE-2026-0001",
                evidence_refs=["evidence:nvd-1"],
                writer="M3",
                reason_code="structured_fact",
                updated_revision=4,
            )
        ],
        updated_at=datetime(2026, 9, 28, tzinfo=UTC),
        current_decision=current_decision,
    )


def _decision() -> DecisionResult:
    return DecisionResult(
        decision_id="decision:abc",
        case_id="product-case-1",
        case_revision=4,
        conclusions=[
            DecisionConclusion(
                statement="affected:true",
                type=ConclusionType.FACT,
                evidence_refs=["evidence:nvd-1"],
            ),
            DecisionConclusion(
                statement="upgrade:recommended",
                type=ConclusionType.RECOMMENDATION,
            ),
        ],
        conflicts=["vendor-status-conflict"],
        unknowns=["exploitability:unknown"],
        assumptions=["deployment-version:1.2.3"],
        citations=[
            DecisionCitation(
                conclusion_index=0,
                evidence_ref="evidence:nvd-1",
                source_ref="source:nvd-cves-2:CVE-2026-0001",
            )
        ],
        stop_reason="answer_supported",
        model_prompt_revision="decision-model-v1",
    )


def test_project_decision_to_qa_prediction_uses_m4_support_and_omits_recommendation() -> None:
    decision = _decision()
    state = _state(current_decision=decision.model_dump(mode="json"))
    prediction = evaluation_runtime.project_decision_to_qa_prediction(
        benchmark_case_id="qa-affected-1",
        decision=decision,
        state=state,
        relation_paths=[
            ["deployment:1", "affected-by", "vulnerability:CVE-2026-0001"]
        ],
        interactive_latency_seconds=0.42,
    )
    assert prediction.case_id == "qa-affected-1"
    assert prediction.conclusion_facts == ["affected:true"]
    assert prediction.unknowns == ["exploitability:unknown"]
    assert prediction.conflicts == ["vendor-status-conflict"]
    assert prediction.assumptions == ["deployment-version:1.2.3"]
    assert prediction.citations[0].supports is True
    assert prediction.relation_paths == [
        ["deployment:1", "affected-by", "vulnerability:CVE-2026-0001"]
    ]
    assert "case:product-case-1" in prediction.execution_refs
    assert "decision:abc" in prediction.execution_refs


def test_project_decision_to_qa_prediction_requires_adjudication_for_paraphrase() -> None:
    decision = _decision().model_copy(deep=True)
    decision.conclusions[0].statement = "The deployment is affected."
    state = _state(current_decision=decision.model_dump(mode="json"))
    without_adjudication = evaluation_runtime.project_decision_to_qa_prediction(
        benchmark_case_id="qa-affected-1",
        decision=decision,
        state=state,
    )
    assert without_adjudication.citations[0].supports is False
    with_adjudication = evaluation_runtime.project_decision_to_qa_prediction(
        benchmark_case_id="qa-affected-1",
        decision=decision,
        state=state,
        citation_support={(0, "evidence:nvd-1"): True},
    )
    assert with_adjudication.citations[0].supports is True


def test_project_decision_to_qa_prediction_rejects_stale_adjudication() -> None:
    decision = _decision()
    state = _state(current_decision=decision.model_dump(mode="json"))
    with pytest.raises(ValueError, match="does not match decision citation"):
        evaluation_runtime.project_decision_to_qa_prediction(
            benchmark_case_id="qa-affected-1",
            decision=decision,
            state=state,
            citation_support={(1, "evidence:missing"): True},
        )


def test_project_continuation_state_to_qa_prediction_preserves_gap_state() -> None:
    state = _state()
    state.unknowns = [
        InvestigationStateItem(
            proposition="exploitability:unknown",
            target_ref="vulnerability:CVE-2026-0001",
            evidence_refs=[],
            writer="M6",
            reason_code="insufficient_evidence",
            updated_revision=5,
        )
    ]
    state.conflicts = [
        InvestigationStateItem(
            proposition="vendor-status-conflict",
            target_ref="vulnerability:CVE-2026-0001",
            evidence_refs=["evidence:nvd-1"],
            writer="M4",
            reason_code="source_conflict",
            updated_revision=5,
        )
    ]
    prediction = evaluation_runtime.project_continuation_state_to_qa_prediction(
        benchmark_case_id="qa-continue-1",
        state=state,
        evidence_need_refs=["evidence-need:need-1"],
    )
    assert prediction.conclusion_facts == []
    assert prediction.completion_status == "continuation_requested"
    assert prediction.unknowns == ["exploitability:unknown"]
    assert prediction.conflicts == ["vendor-status-conflict"]
    assert "evidence-need:need-1" in prediction.execution_refs


@pytest.mark.asyncio
async def test_pinned_deployment_fails_closed_when_current_coordinate_drifts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, factory = await _database()
    pinned = _deployment("deployment:pinned")
    drifted = _deployment("deployment:drifted")
    try:
        async with factory() as session, session.begin():
            await BenchmarkStore().register_deployment(session, pinned)

        async def fake_capture(*args, **kwargs):
            del args, kwargs
            return drifted

        monkeypatch.setattr(
            evaluation_runtime,
            "capture_current_deployment_revision",
            fake_capture,
        )
        async with factory() as session:
            with pytest.raises(RuntimeError, match="no longer matches"):
                await evaluation_runtime.ensure_benchmark_deployment_revision(
                    session,
                    Settings(),
                    deployment_revision_id=pinned.deployment_revision_id,
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_pinned_deployment_accepts_same_current_coordinate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, factory = await _database()
    pinned = _deployment("deployment:pinned")
    try:
        async with factory() as session, session.begin():
            await BenchmarkStore().register_deployment(session, pinned)

        async def fake_capture(*args, **kwargs):
            del args, kwargs
            return pinned

        monkeypatch.setattr(
            evaluation_runtime,
            "capture_current_deployment_revision",
            fake_capture,
        )
        async with factory() as session:
            resolved = await evaluation_runtime.ensure_benchmark_deployment_revision(
                session,
                Settings(),
                deployment_revision_id=pinned.deployment_revision_id,
            )
            assert resolved == pinned.deployment_revision_id
    finally:
        await engine.dispose()
