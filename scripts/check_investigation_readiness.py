from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from apps.runtime_models import register_runtime_models
from packages.evaluation.investigation_readiness import (
    MAX_PROSPECTIVE_FREEZE_LAG_SECONDS,
    assess_prospective_investigation_case,
)
from packages.investigation.state.contracts import CaseStateEventType
from packages.investigation.storage.models import CaseStateEventModel, InvestigationCaseModel
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory


async def _check(*, measured_at: datetime | None = None) -> dict[str, Any]:
    register_runtime_models()
    settings = get_settings()
    now = (measured_at or datetime.now(UTC)).astimezone(UTC)
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            cases = list(
                await session.scalars(
                    select(InvestigationCaseModel).order_by(
                        InvestigationCaseModel.created_at.desc(),
                        InvestigationCaseModel.case_id,
                    )
                )
            )
            case_rows: list[dict[str, Any]] = []
            for case in cases:
                decision_at = await session.scalar(
                    select(CaseStateEventModel.created_at)
                    .where(
                        CaseStateEventModel.case_id == case.case_id,
                        CaseStateEventModel.event_type
                        == CaseStateEventType.DECISION_CHANGED.value,
                    )
                    .order_by(CaseStateEventModel.case_revision.desc())
                    .limit(1)
                )
                assessment = assess_prospective_investigation_case(
                    created_at=case.created_at,
                    final_decision_at=decision_at,
                    frozen_at=now,
                    max_freeze_lag_seconds=MAX_PROSPECTIVE_FREEZE_LAG_SECONDS,
                )
                case_rows.append(
                    {
                        "case_id": case.case_id,
                        "case_status": case.status,
                        "created_at": case.created_at.isoformat(),
                        "final_decision_at": (
                            decision_at.isoformat() if decision_at is not None else None
                        ),
                        **assessment,
                    }
                )
    finally:
        await engine.dispose()

    provider_configured = bool(settings.model_base_url and settings.model_name)
    return {
        "generated_at": now.isoformat(),
        "model_provider_status": "configured" if provider_configured else "unconfigured",
        "launch_readiness": (
            "ready_to_launch_real_case"
            if provider_configured
            else "blocked_model_provider_unconfigured"
        ),
        "max_prospective_freeze_lag_seconds": MAX_PROSPECTIVE_FREEZE_LAG_SECONDS,
        "case_count": len(case_rows),
        "eligible_case_count": sum(item["eligible"] is True for item in case_rows),
        "cases": case_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Check whether existing Product Investigation cases can enter a prospective benchmark"
        )
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = asyncio.run(_check())
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
