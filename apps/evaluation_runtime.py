from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.evaluation.benchmark import (
    BenchmarkStore,
    DeploymentRevision,
    MeasurementSource,
    MetricDirection,
)
from packages.evaluation.benchmark.metrics import metric_definition
from packages.evaluation.benchmark.storage import DeploymentRevisionModel
from packages.evaluation.m1_m3 import EnrichmentScore
from packages.evaluation.qa import QAScore
from packages.intelligence.knowledge.vocabulary import VOCABULARY_REVISION
from packages.investigation.skills.seeds import seeded_skills
from packages.runtime.policy.loader import load_runtime_policy
from packages.shared.config import Settings


class M3BenchmarkRecorder:
    """Project existing M3 scorer output into TD3 durable metric observations."""

    def __init__(self, store: BenchmarkStore | None = None) -> None:
        self._store = store or BenchmarkStore()

    async def record_case_score(
        self,
        session: AsyncSession,
        *,
        case_run_id: str,
        score: EnrichmentScore,
        subject_ref: str,
    ) -> None:
        for metric_name, value, direction in (
            (
                "m3.micro_precision",
                score.micro_precision,
                MetricDirection.HIGHER_IS_BETTER,
            ),
            (
                "m3.micro_recall",
                score.micro_recall,
                MetricDirection.HIGHER_IS_BETTER,
            ),
            (
                "m3.true_positive",
                float(score.true_positive),
                MetricDirection.INFORMATIONAL,
            ),
            (
                "m3.false_positive",
                float(score.false_positive),
                MetricDirection.LOWER_IS_BETTER,
            ),
            (
                "m3.false_negative",
                float(score.false_negative),
                MetricDirection.LOWER_IS_BETTER,
            ),
        ):
            await self._store.observe_metric(
                session,
                case_run_id=case_run_id,
                metric_name=metric_name,
                value=value,
                direction=direction,
                measurement_source=MeasurementSource.SCORER,
                subject_ref=subject_ref,
            )

        for dimension in score.dimensions:
            prefix = f"m3.dimension.{dimension.dimension.value}"
            for suffix, value, direction in (
                (
                    "precision",
                    dimension.precision,
                    MetricDirection.HIGHER_IS_BETTER,
                ),
                (
                    "recall",
                    dimension.recall,
                    MetricDirection.HIGHER_IS_BETTER,
                ),
                (
                    "true_positive",
                    float(dimension.true_positive),
                    MetricDirection.INFORMATIONAL,
                ),
                (
                    "false_positive",
                    float(dimension.false_positive),
                    MetricDirection.LOWER_IS_BETTER,
                ),
                (
                    "false_negative",
                    float(dimension.false_negative),
                    MetricDirection.LOWER_IS_BETTER,
                ),
            ):
                await self._store.observe_metric(
                    session,
                    case_run_id=case_run_id,
                    metric_name=f"{prefix}.{suffix}",
                    value=value,
                    direction=direction,
                    measurement_source=MeasurementSource.SCORER,
                    subject_ref=subject_ref,
                )


class QABenchmarkRecorder:
    def __init__(self, store: BenchmarkStore | None = None) -> None:
        self._store = store or BenchmarkStore()

    async def record_case_score(
        self,
        session: AsyncSession,
        *,
        case_run_id: str,
        score: QAScore,
        subject_ref: str,
    ) -> None:
        values: list[tuple[str, float]] = [
            ("m6.answer_accuracy", score.answer_accuracy),
            ("m6.groundedness", score.groundedness),
            ("m6.citation_correctness", score.citation_correctness),
            ("m6.citation_completeness", score.citation_completeness),
            ("m6.unknown_correctness", score.unknown_correctness),
            ("m6.conflict_handling", score.conflict_handling),
            ("m6.completion_correctness", score.completion_correctness),
        ]
        if score.multi_hop_correctness is not None:
            values.append(("m6.multi_hop_correctness", score.multi_hop_correctness))
        if score.interactive_latency_seconds is not None:
            values.append(("m6.interactive_latency_seconds", score.interactive_latency_seconds))
        for metric_name, value in values:
            definition = metric_definition(metric_name)
            await self._store.observe_metric(
                session,
                case_run_id=case_run_id,
                metric_name=metric_name,
                value=value,
                direction=definition.direction,
                measurement_source=MeasurementSource.SCORER,
                subject_ref=subject_ref,
            )


async def capture_current_deployment_revision(
    session: AsyncSession,
    settings: Settings,
    *,
    repo_root: Path = Path("."),
) -> DeploymentRevision:
    schema_revision = await session.scalar(text("SELECT version_num FROM alembic_version"))
    if not isinstance(schema_revision, str) or not schema_revision:
        raise RuntimeError("cannot resolve current Alembic schema revision")
    git_revision = _git_working_revision(repo_root)
    source_inventory_hash = _file_hash(repo_root / "config/source-inventory.json")
    policy = load_runtime_policy(repo_root / settings.runtime_policy_path)
    skill_registry_revision = _skill_registry_digest()
    model_provider_revision = (
        f"openai-compatible:{settings.model_name}" if settings.model_name else "unconfigured"
    )
    semantic_config = {
        "environment": settings.environment,
        "schema_revision": schema_revision,
        "source_inventory_hash": source_inventory_hash,
        "vocabulary_revision": VOCABULARY_REVISION,
        "policy_revision": policy.policy_revision,
        "capability_registry_revision": "unbound",
        "skill_registry_revision": skill_registry_revision,
        "model_provider_revision": model_provider_revision,
        "embedding_model_name": settings.embedding_model_name,
        "embedding_dimensions": settings.embedding_dimensions,
        "hot_cache_ttl_seconds": settings.hot_cache_ttl_seconds,
        "task_event_stream_name": settings.task_event_stream_name,
    }
    configuration_digest = _digest_json(semantic_config)
    identity_payload = {
        "git_revision": git_revision,
        **semantic_config,
        "configuration_digest": configuration_digest,
    }
    deployment_id = f"deployment:{_digest_json(identity_payload)[:32]}"
    return DeploymentRevision(
        deployment_revision_id=deployment_id,
        git_commit=git_revision,
        schema_revision=schema_revision,
        source_inventory_hash=source_inventory_hash,
        vocabulary_revision=VOCABULARY_REVISION,
        policy_revision=policy.policy_revision,
        capability_registry_revision="unbound",
        skill_registry_revision=skill_registry_revision,
        model_provider_revision=model_provider_revision,
        configuration_digest=configuration_digest,
        created_at=datetime.now(UTC),
    )


async def ensure_benchmark_deployment_revision(
    session: AsyncSession,
    settings: Settings,
    *,
    deployment_revision_id: str | None = None,
    repo_root: Path = Path("."),
) -> str:
    """Resolve a pinned benchmark deployment or freeze the current repo state once."""

    if deployment_revision_id is not None:
        existing = await session.get(DeploymentRevisionModel, deployment_revision_id)
        if existing is None:
            raise LookupError(f"deployment revision not found: {deployment_revision_id}")
        current = await capture_current_deployment_revision(
            session,
            settings,
            repo_root=repo_root,
        )
        if current.deployment_revision_id != deployment_revision_id:
            raise RuntimeError(
                "current repository/runtime coordinate no longer matches the pinned "
                f"deployment revision: expected={deployment_revision_id} "
                f"current={current.deployment_revision_id}"
            )
        return deployment_revision_id
    deployment = await capture_current_deployment_revision(
        session,
        settings,
        repo_root=repo_root,
    )
    await BenchmarkStore().register_deployment(session, deployment)
    return deployment.deployment_revision_id


def _git_working_revision(repo_root: Path) -> str:
    head = _git(repo_root, "rev-parse", "HEAD").decode().strip()
    diff = _git(repo_root, "diff", "HEAD", "--binary")
    untracked_raw = _git(
        repo_root,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
    )
    untracked_paths = [item.decode() for item in untracked_raw.split(b"\0") if item]
    hasher = sha256()
    hasher.update(diff)
    for relative in sorted(untracked_paths):
        path = repo_root / relative
        if not path.is_file():
            continue
        hasher.update(relative.encode())
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    dirty_digest = hasher.hexdigest()
    if not diff and not untracked_paths:
        return head
    return f"{head}+dirty.{dirty_digest[:16]}"


def _git(repo_root: Path, *args: str) -> bytes:
    return subprocess.check_output(
        ["git", *args],
        cwd=repo_root,
        stderr=subprocess.DEVNULL,
    )


def _file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _skill_registry_digest() -> str:
    payload = [skill.model_dump(mode="json") for skill in seeded_skills()]
    return f"seed-skills:{_digest_json(payload)[:24]}"


def _digest_json(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
