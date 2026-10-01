from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from apps.evaluation_runtime import validate_structured_qa_gold_provenance
from apps.runtime_models import register_runtime_models
from packages.intelligence.retrieval.validation import current_knowledge_revision
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from scripts.run_qa_benchmark import QABenchmarkManifest


def _live_runtime_world_status(
    manifest: QABenchmarkManifest,
    *,
    current_revision: int,
) -> str:
    requires_live_world_pin = bool(manifest.sessions) or any(
        item.live_product_question is not None for item in manifest.cases
    )
    if not requires_live_world_pin:
        return "not_applicable"
    assert manifest.knowledge_revision is not None
    if current_revision == manifest.knowledge_revision:
        return "ready"
    return "stale_requires_refresh_or_rebase"


def _model_provider_status(*, model_base_url: str | None, model_name: str | None) -> str:
    return "configured" if model_base_url and model_name else "unconfigured"


async def _validate(manifest: QABenchmarkManifest) -> dict[str, Any]:
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            current_revision = await current_knowledge_revision(session)
            live_runtime_world_status = _live_runtime_world_status(
                manifest,
                current_revision=current_revision,
            )
            model_provider_status = _model_provider_status(
                model_base_url=settings.model_base_url,
                model_name=settings.model_name,
            )

            structured_cases = 0
            for item in manifest.cases:
                provenance = item.gold_provenance
                if provenance is None or provenance.mode != "structured_authority":
                    continue
                assert manifest.knowledge_revision is not None
                await validate_structured_qa_gold_provenance(
                    session,
                    gold=item.gold,
                    evidence_refs=provenance.evidence_refs,
                    source_ids=provenance.source_ids,
                    knowledge_revision=manifest.knowledge_revision,
                    absence_checks=[
                        (check.subject_key, check.predicate)
                        for check in provenance.absence_checks
                    ],
                )
                structured_cases += 1

            structured_session_turns = 0
            for session_case in manifest.sessions:
                for turn in session_case.turns:
                    provenance = turn.gold_provenance
                    if provenance is None or provenance.mode != "structured_authority":
                        continue
                    assert manifest.knowledge_revision is not None
                    await validate_structured_qa_gold_provenance(
                        session,
                        gold=turn.gold,
                        evidence_refs=provenance.evidence_refs,
                        source_ids=provenance.source_ids,
                        knowledge_revision=manifest.knowledge_revision,
                        absence_checks=[
                            (check.subject_key, check.predicate)
                            for check in provenance.absence_checks
                        ],
                    )
                    structured_session_turns += 1

            return {
                "suite_id": manifest.suite_id,
                "case_count": len(manifest.cases),
                "session_count": len(manifest.sessions),
                "structured_authority_case_count": structured_cases,
                "structured_authority_session_turn_count": structured_session_turns,
                "knowledge_revision": manifest.knowledge_revision,
                "current_knowledge_revision": current_revision,
                "gold_provenance_status": "valid",
                "live_runtime_world_status": live_runtime_world_status,
                "model_provider_status": model_provider_status,
                "status": "valid",
            }
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate QA manifest world pin and structured gold provenance without a model"
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest = QABenchmarkManifest.model_validate_json(
        args.manifest.read_text(encoding="utf-8")
    )
    result = asyncio.run(_validate(manifest))
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
