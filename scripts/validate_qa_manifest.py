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


async def _validate(manifest: QABenchmarkManifest) -> dict[str, Any]:
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            current_revision = await current_knowledge_revision(session)
            if any(item.live_product_question is not None for item in manifest.cases):
                assert manifest.knowledge_revision is not None
                if current_revision != manifest.knowledge_revision:
                    raise ValueError(
                        "live Product QA manifest is pinned to a different Knowledge revision: "
                        f"manifest={manifest.knowledge_revision}, current={current_revision}"
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
                )
                structured_cases += 1

            return {
                "suite_id": manifest.suite_id,
                "case_count": len(manifest.cases),
                "structured_authority_case_count": structured_cases,
                "knowledge_revision": manifest.knowledge_revision,
                "current_knowledge_revision": current_revision,
                "status": "valid",
            }
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate QA manifest world pin and structured gold provenance without a model"
    )
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    manifest = QABenchmarkManifest.model_validate_json(
        args.manifest.read_text(encoding="utf-8")
    )
    result = asyncio.run(_validate(manifest))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
