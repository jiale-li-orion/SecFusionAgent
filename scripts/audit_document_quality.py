"""Audit up to 100 retained documents; explicitly opt in to parser-version replay."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from apps.runtime_models import register_runtime_models
from packages.intelligence.documents.maintenance import DocumentQualityMaintenance
from packages.intelligence.storage.factory import create_artifact_store
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.sources.registry.loader import load_source_definitions


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--document-id",
        action="append",
        default=[],
        help="Document identity to inspect; repeat to select several documents",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum latest document revisions to inspect (1-100; default 20)",
    )
    parser.add_argument(
        "--reparse",
        action="store_true",
        help="Create current-parser revisions from retained evidence; "
        "preserves old revisions and uses ordinary indexing outbox events",
    )
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100")
    if len(set(args.document_id)) > args.limit:
        parser.error("number of selected document IDs must not exceed --limit")
    return args


async def run(args: argparse.Namespace) -> dict[str, Any]:
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    maintenance = DocumentQualityMaintenance(create_artifact_store(settings))
    try:
        async with factory() as session:
            audits = await maintenance.audit_documents(
                session,
                document_ids=args.document_id,
                limit=args.limit,
            )
        reparses: list[dict[str, Any]] = []
        if args.reparse:
            sources = {
                source.source_id: source
                for source in load_source_definitions(Path(settings.source_registry_path))
            }
            for audit in audits:
                source = sources.get(audit.source_id)
                if source is None or audit.status != "audited":
                    reparses.append(
                        {
                            "document_id": audit.document_id,
                            "status": "skipped",
                            "reason": "source_definition_missing"
                            if source is None
                            else audit.status,
                        }
                    )
                    continue
                async with factory() as session, session.begin():
                    result = await maintenance.reparse_revision(
                        session,
                        document_revision_id=audit.document_revision_id,
                        source=source,
                    )
                reparses.append(
                    {
                        "document_id": audit.document_id,
                        "status": "replay" if result.replay else "reparsed",
                        "observation_id": result.observation_id,
                        "document_revision_id": result.document_revision_id,
                        "chunk_count": result.chunk_count,
                    }
                )
        return {
            "mode": "reparse" if args.reparse else "audit_read_only",
            "limit": args.limit,
            "summary": {
                "documents": len(audits),
                "stored_publication_dates": sum(
                    bool(row.publication.get("stored_published_at")) for row in audits
                ),
                "retained_publication_dates": sum(
                    bool(
                        row.publication.get("retained_published_at")
                        or row.publication.get("published_date")
                    )
                    for row in audits
                ),
                "retained_usable": sum(
                    row.retained_quality is not None and row.retained_quality.get("usable") is True
                    for row in audits
                ),
                "unreadable_or_unsupported": sum(row.status != "audited" for row in audits),
            },
            "documents": [row.model_dump(mode="json") for row in audits],
            "reparses": reparses,
        }
    finally:
        await engine.dispose()


def main() -> None:
    print(json.dumps(asyncio.run(run(parse_args())), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
