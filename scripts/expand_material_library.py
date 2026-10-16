"""Bounded, resumable public corpus backfill through existing M1/M2 owners.

Does not advance scheduled discovery cursors or call models. Existing documents
are skipped; accepted bytes, publication metadata and provenance use ordinary
managed ingestion. Run outcomes remain in acquisition_runs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import select

from apps.runtime_models import register_runtime_models
from packages.intelligence.documents.parsers import HTMLDocumentParser, PDFDocumentParser
from packages.intelligence.documents.service import ManagedDocumentService
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.storage.document_models import DocumentModel
from packages.intelligence.storage.factory import create_artifact_store
from packages.monitoring.registration import synchronize_monitoring_sources
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.sources.adapters.arxiv import ArxivAdapter
from packages.sources.adapters.html_index import HTMLIndexAdapter
from packages.sources.contracts import AcquisitionTrigger, QuerySpec, RetentionMode, SourceState
from packages.sources.registry.loader import load_source_definitions


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-id", action="append", required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--url", action="append", default=[])
    parser.add_argument("--max-seconds", type=int, default=600)
    args = parser.parse_args(argv)
    if not 60 <= args.max_seconds <= 3600:
        parser.error("--max-seconds must be 60..3600 per source")
    if not 1 <= args.limit <= 500:
        parser.error("--limit must be 1..500 per source")
    if args.url and (len(args.source_id) != 1 or len(args.url) > args.limit):
        parser.error("--url requires one source and at most --limit URLs")
    return args


async def run(args: argparse.Namespace) -> None:
    register_runtime_models()
    settings = get_settings()
    definitions = load_source_definitions(Path(settings.source_registry_path))
    sources = {s.source_id: s for s in definitions}
    selected = [sources[sid] for sid in dict.fromkeys(args.source_id)]
    if any(
        s.adapter_type not in {"arxiv", "html_index"}
        or s.retention_mode != RetentionMode.DURABLE_MANAGED
        or s.access_rights.get("classification") != "public"
        for s in selected
    ):
        raise ValueError("backfill supports public durable HTML/arXiv sources only")
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    service = ManagedDocumentService(
        EvidenceIngress(create_artifact_store(settings)),
        {
            "text/html": HTMLDocumentParser(),
            "application/xhtml+xml": HTMLDocumentParser(),
            "application/pdf": PDFDocumentParser(),
        },
    )
    try:
        async with factory() as session, session.begin():
            await synchronize_monitoring_sources(session, definitions)
        async with httpx.AsyncClient(timeout=45, follow_redirects=True) as client:
            for source in selected:
                now = datetime.now(UTC)
                run_id = str(uuid4())
                stats: dict[str, Any] = {
                    "source_id": source.source_id,
                    "run_id": run_id,
                    "retained": 0,
                    "replayed": 0,
                    "skipped": 0,
                    "failed": 0,
                }
                async with factory() as session, session.begin():
                    session.add(
                        AcquisitionRunModel(
                            run_id=run_id,
                            source_id=source.source_id,
                            trigger="on_demand",
                            query_spec={
                                "purpose": "corpus_backfill",
                                "execution_driver": "operator",
                                "limit": args.limit,
                                "urls": args.url,
                            },
                            status="running",
                            cursor_in={"backfill_pending": True},
                            cursor_out={},
                            attempt=1,
                            created_at=now,
                            started_at=now,
                        )
                    )
                    existing = set(
                        await session.scalars(
                            select(DocumentModel.external_object_id).where(
                                DocumentModel.source_id == source.source_id
                            )
                        )
                    )
                adapter = (
                    ArxivAdapter(client)
                    if source.adapter_type == "arxiv"
                    else HTMLIndexAdapter(client)
                )
                deadline = monotonic() + args.max_seconds
                try:
                    if args.url:
                        refs = args.url
                    else:
                        discovery = dict(source.discovery_method)
                        discovery.update(initial_limit=args.limit, max_items=args.limit)
                        batch = await adapter.discover(
                            source.model_copy(update={"discovery_method": discovery}), SourceState()
                        )
                        refs = batch.items[: args.limit]
                    for ref in refs:
                        if monotonic() >= deadline:
                            stats["failed"] += 1
                            stats["stop_reason"] = "time_budget_exhausted"
                            break
                        if not isinstance(ref, str) and ref.external_object_id in existing:
                            stats["skipped"] += 1
                            continue
                        try:
                            if isinstance(ref, str):
                                envelopes = await adapter.query(
                                    source,
                                    QuerySpec(filters={"url": ref}),
                                    acquisition_run_id=run_id,
                                    trigger=AcquisitionTrigger.ON_DEMAND,
                                )
                            else:
                                envelopes = [
                                    await adapter.fetch(
                                        source,
                                        ref,
                                        acquisition_run_id=run_id,
                                        trigger=AcquisitionTrigger.ON_DEMAND,
                                    )
                                ]
                            for envelope in envelopes:
                                async with factory() as session, session.begin():
                                    result = await service.ingest(session, source, envelope)
                                stats["replayed" if result.replay else "retained"] += 1
                                print(
                                    json.dumps(
                                        {
                                            "source_id": source.source_id,
                                            "document_id": result.document_id,
                                            "revision_id": result.document_revision_id,
                                            "url": envelope.canonical_url,
                                            "chunks": result.chunk_count,
                                            "replay": result.replay,
                                        },
                                        ensure_ascii=False,
                                    ),
                                    flush=True,
                                )
                        except Exception as exc:
                            stats["failed"] += 1
                            print(
                                json.dumps(
                                    {
                                        "source_id": source.source_id,
                                        "error": type(exc).__name__,
                                        "target": ref
                                        if isinstance(ref, str)
                                        else ref.canonical_url,
                                    },
                                    ensure_ascii=False,
                                ),
                                flush=True,
                            )
                        await asyncio.sleep(
                            max(
                                3,
                                float(
                                    str(source.rate_limit_policy.get("polite_interval_seconds", 3))
                                ),
                            )
                        )
                except asyncio.CancelledError:
                    stats["failed"] += 1
                    stats["stop_reason"] = "operator_interrupted"
                except Exception as exc:
                    stats["failed"] += 1
                    print(
                        json.dumps(
                            {"source_id": source.source_id, "discovery_error": type(exc).__name__}
                        ),
                        flush=True,
                    )
                async with factory() as session, session.begin():
                    row = await session.get(AcquisitionRunModel, run_id)
                    if row is None:
                        raise RuntimeError("backfill run disappeared")
                    row.status = "success" if not stats["failed"] else "internal_error"
                    row.error_code = "backfill_incomplete" if stats["failed"] else None
                    row.finished_at = datetime.now(UTC)
                    row.cursor_out = {"backfill_pending": False, "backfill_result": stats}
                print(json.dumps({"summary": stats}, ensure_ascii=False), flush=True)
                if stats.get("stop_reason") == "operator_interrupted":
                    break
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
