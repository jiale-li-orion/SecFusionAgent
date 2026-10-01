from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from apps.runtime_models import register_runtime_models
from packages.evaluation.benchmark import CompetitionReport, CompetitionReportService
from packages.evaluation.benchmark.storage import BenchmarkCaseRunModel, BenchmarkRunModel
from packages.evaluation.competition_status import render_competition_report_markdown
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory


class CompetitionRunSet(BaseModel):
    schema_version: str = "competition-run-set-v1"
    deployment_revision_id: str = Field(min_length=1)
    benchmark_run_ids: list[str] = Field(min_length=1)
    artifact_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_run_set(self) -> CompetitionRunSet:
        if self.schema_version != "competition-run-set-v1":
            raise ValueError("unsupported competition run-set schema")
        if len(set(self.benchmark_run_ids)) != len(self.benchmark_run_ids):
            raise ValueError("competition run-set benchmark ids must be unique")
        if len(set(self.artifact_refs)) != len(self.artifact_refs):
            raise ValueError("competition run-set artifact refs must be unique")
        return self


def _load_run_set(path: Path) -> CompetitionRunSet:
    return CompetitionRunSet.model_validate_json(path.read_text(encoding="utf-8"))


def _validate_provider_snapshot_refs(
    *,
    run_world_snapshot_refs: list[str | None],
    case_artifact_refs: list[list[str]],
    declared_artifact_refs: list[str],
) -> None:
    if not declared_artifact_refs:
        return
    required = {
        ref
        for ref in run_world_snapshot_refs
        if isinstance(ref, str) and ref.startswith("provider-snapshot:")
    }
    required.update(
        ref
        for refs in case_artifact_refs
        for ref in refs
        if ref.startswith("provider-snapshot:")
    )
    missing = sorted(required - set(declared_artifact_refs))
    if missing:
        raise ValueError(
            "competition report artifact refs omit provider snapshots bound to selected runs: "
            f"{missing}"
        )


async def _export(
    run_ids: list[str],
    *,
    deployment_revision_id: str | None,
    artifact_refs: list[str],
) -> CompetitionReport:
    if not run_ids:
        raise ValueError("at least one benchmark run id is required")
    if len(set(run_ids)) != len(run_ids):
        raise ValueError("benchmark run ids must be unique")
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session, session.begin():
            runs = list(
                await session.scalars(
                    select(BenchmarkRunModel).where(BenchmarkRunModel.benchmark_run_id.in_(run_ids))
                )
            )
            by_id = {item.benchmark_run_id: item for item in runs}
            missing = [item for item in run_ids if item not in by_id]
            if missing:
                raise LookupError(f"benchmark runs not found: {missing}")
            deployment_ids = {item.deployment_revision_id for item in runs}
            if len(deployment_ids) != 1:
                raise ValueError(
                    "competition report cannot mix benchmark runs from different deployments"
                )
            resolved_deployment_id = next(iter(deployment_ids))
            if (
                deployment_revision_id is not None
                and resolved_deployment_id != deployment_revision_id
            ):
                raise ValueError(
                    "selected benchmark runs do not belong to the requested deployment revision"
                )
            artifact_rows = list(
                await session.scalars(
                    select(BenchmarkCaseRunModel.artifact_refs_json).where(
                        BenchmarkCaseRunModel.benchmark_run_id.in_(run_ids)
                    )
                )
            )
            _validate_provider_snapshot_refs(
                run_world_snapshot_refs=[item.world_snapshot_ref for item in runs],
                case_artifact_refs=[list(item) for item in artifact_rows],
                declared_artifact_refs=artifact_refs,
            )
            return await CompetitionReportService().generate_and_persist(
                session,
                deployment_revision_id=resolved_deployment_id,
                benchmark_run_ids=run_ids,
                artifact_refs=artifact_refs,
            )
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate and persist a competition report from completed benchmark runs"
    )
    parser.add_argument("run_ids", nargs="*", help="legacy positional benchmark run ids")
    parser.add_argument("--run-id", action="append", default=[])
    parser.add_argument("--deployment-revision-id")
    parser.add_argument("--artifact-ref", action="append", default=[])
    parser.add_argument("--run-set-manifest", type=Path)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--output", type=Path, help="legacy alias for --json-output")
    args = parser.parse_args()
    run_ids = [*args.run_ids, *args.run_id]
    deployment_revision_id = args.deployment_revision_id
    artifact_refs = list(args.artifact_ref)
    if args.run_set_manifest is not None:
        if run_ids or deployment_revision_id is not None or artifact_refs:
            parser.error(
                "--run-set-manifest cannot be combined with run IDs, deployment ID, "
                "or artifact refs"
            )
        run_set = _load_run_set(args.run_set_manifest)
        run_ids = list(run_set.benchmark_run_ids)
        deployment_revision_id = run_set.deployment_revision_id
        artifact_refs = list(run_set.artifact_refs)
    report = asyncio.run(
        _export(
            run_ids,
            deployment_revision_id=deployment_revision_id,
            artifact_refs=artifact_refs,
        )
    )
    payload = report.model_dump(mode="json")
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    json_output = args.json_output or args.output
    if json_output is not None:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(rendered, encoding="utf-8")
    if args.markdown_output is not None:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(
            render_competition_report_markdown(report),
            encoding="utf-8",
        )
    print(rendered, end="")


if __name__ == "__main__":
    main()
