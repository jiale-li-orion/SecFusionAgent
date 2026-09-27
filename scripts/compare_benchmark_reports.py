from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from apps.runtime_models import register_runtime_models
from packages.evaluation.benchmark import CompetitionReport, RegressionGate, RegressionRule
from packages.evaluation.benchmark.storage import CompetitionReportModel
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory


async def _load_report(session: AsyncSession, report_id: str) -> CompetitionReport:
    model = await session.get(CompetitionReportModel, report_id)
    if model is None:
        raise LookupError(f"competition report not found: {report_id}")
    return CompetitionReport.model_validate(model.payload_json)


async def _compare(
    baseline_report_id: str,
    candidate_report_id: str,
    rules: list[RegressionRule],
) -> dict[str, object]:
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            baseline = await _load_report(session, baseline_report_id)
            candidate = await _load_report(session, candidate_report_id)
        result = RegressionGate().evaluate(
            baseline=baseline,
            candidate=candidate,
            rules=rules,
        )
        return result.model_dump(mode="json")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare two durable competition reports with explicit regression rules"
    )
    parser.add_argument("baseline_report_id")
    parser.add_argument("candidate_report_id")
    parser.add_argument("--rules", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    raw_rules = json.loads(args.rules.read_text(encoding="utf-8"))
    if not isinstance(raw_rules, list):
        raise ValueError("regression rules file must contain a JSON list")
    rules = [RegressionRule.model_validate(item) for item in raw_rules]
    payload = asyncio.run(_compare(args.baseline_report_id, args.candidate_report_id, rules))
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
