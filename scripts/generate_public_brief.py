"""Generate a reviewed public report from explicitly selected retained documents.

No credentials, raw document bodies or model text are printed. This operator
entry point can be invoked after collection or by a timer; reads never generate.
"""

import argparse
import asyncio
import json
from datetime import datetime

import httpx

from apps.application.public_briefings import load_briefing_packet, publish_briefing
from apps.model_runtime import create_recorded_model_provider
from apps.runtime_models import register_runtime_models
from packages.reasoning.briefing import BriefingGenerator
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory


async def run(args: argparse.Namespace) -> None:
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    coordinates = {
        "topic": args.topic,
        "document_ids": args.document_id,
        "window_start": datetime.fromisoformat(args.window_start) if args.window_start else None,
        "window_end": datetime.fromisoformat(args.window_end) if args.window_end else None,
    }
    try:
        if not args.publish:
            async with factory() as session:
                packet = await load_briefing_packet(session, **coordinates)
                print(
                    json.dumps(
                        {
                            "mode": "validate_only",
                            "topic": packet.topic,
                            "documents": len(packet.materials),
                            "upstream_groups": packet.origin_count,
                            "materials": [
                                {
                                    "document_id": item.document_id,
                                    "title": item.title,
                                    "revision_id": item.revision_id,
                                    "published_at": str(item.published_at),
                                    "truncated": item.truncated,
                                }
                                for item in packet.materials
                            ],
                        },
                        ensure_ascii=False,
                    )
                )
            return
        async with httpx.AsyncClient(timeout=settings.model_timeout_seconds) as client:
            provider = create_recorded_model_provider(settings, factory, client)
            if provider is None:
                raise RuntimeError("public briefing requires a configured model provider")
            result = await publish_briefing(factory, BriefingGenerator(provider), **coordinates)
            print(
                json.dumps(
                    {
                        "brief_id": result.brief_id,
                        "status": result.status,
                        "report_url": f"/api/v1/intelligence/briefs/{result.brief_id}/report.html"
                        if result.status == "published"
                        else None,
                    },
                    ensure_ascii=False,
                )
            )
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--document-id", action="append", required=True)
    parser.add_argument(
        "--window-start", help="ISO timestamp with timezone; both boundaries required"
    )
    parser.add_argument("--window-end", help="Exclusive publication window end")
    parser.add_argument(
        "--publish", action="store_true", help="Generate, critique, persist if eligible"
    )
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
