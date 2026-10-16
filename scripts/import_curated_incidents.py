"""Import an operator-reviewed JSON manifest using retained evidence; safe to replay."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from apps.runtime_models import register_runtime_models
from packages.intelligence.incident.curation import CuratedIncident, IncidentCurationService
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory


async def run(path: Path) -> list[dict[str, object]]:
    specs = [
        CuratedIncident.model_validate(item)
        for item in json.loads(await asyncio.to_thread(path.read_text))
    ]
    if not 1 <= len(specs) <= 50:
        raise ValueError("manifest must contain 1..50 incidents")
    register_runtime_models()
    engine = create_engine(get_settings().database_url)
    factory = create_session_factory(engine)
    try:
        results = []
        # All-or-nothing: a bad evidence pin leaves no partial curated catalog.
        async with factory() as session, session.begin():
            for spec in specs:
                incident_id, replay = await IncidentCurationService().import_incident(session, spec)
                results.append({"key": spec.key, "incident_id": incident_id, "replay": replay})
        return results
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.manifest)), ensure_ascii=False, indent=2))
