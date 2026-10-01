from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
from hashlib import sha256
from urllib.parse import urlparse

from sqlalchemy import select

from apps.runtime_models import register_runtime_models
from packages.intelligence.storage.artifacts import ArtifactStore, FilesystemArtifactStore
from packages.intelligence.storage.evidence_models import EvidenceArtifactModel
from packages.intelligence.storage.factory import create_s3_artifact_store
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.sources.inventory import load_source_inventory


async def migrate(*, since: datetime, dry_run: bool) -> dict[str, int]:
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    source_stores: dict[str, ArtifactStore] = {}
    target_stores: dict[str, FilesystemArtifactStore] = {}
    counters = {"selected": 0, "migrated": 0, "missing": 0, "already_target": 0}
    try:
        async with factory() as session:
            rows = list(
                await session.scalars(
                    select(EvidenceArtifactModel)
                    .where(EvidenceArtifactModel.created_at >= since)
                    .order_by(EvidenceArtifactModel.created_at)
                )
            )
        counters["selected"] = len(rows)
        for artifact in rows:
            if artifact.storage_uri.startswith("artifact://"):
                counters["already_target"] += 1
                continue
            if not artifact.storage_uri.startswith("s3://"):
                continue
            bucket = urlparse(artifact.storage_uri).netloc
            if not bucket:
                raise RuntimeError(f"artifact URI has no bucket: {artifact.storage_uri}")
            source = source_stores.get(bucket)
            if source is None:
                source = create_s3_artifact_store(settings, bucket=bucket)
                source_stores[bucket] = source
            target = target_stores.get(bucket)
            if target is None:
                target = FilesystemArtifactStore(settings.artifact_root, bucket=bucket)
                await target.ensure_bucket()
                target_stores[bucket] = target
            if not await source.exists(artifact.storage_uri):
                counters["missing"] += 1
                continue
            body = await source.get(artifact.storage_uri)
            if sha256(body).hexdigest() != artifact.content_hash:
                raise RuntimeError(
                    f"artifact hash mismatch during migration: {artifact.artifact_id}"
                )
            write = await target.put(
                content_hash=artifact.content_hash,
                body=body,
                media_type=artifact.media_type,
            )
            if not await target.exists(write.storage_uri):
                raise RuntimeError(f"target artifact verification failed: {artifact.artifact_id}")
            if not dry_run:
                async with factory() as session, session.begin():
                    persisted = await session.get(EvidenceArtifactModel, artifact.artifact_id)
                    if persisted is None:
                        raise RuntimeError(
                            f"artifact disappeared during migration: {artifact.artifact_id}"
                        )
                    if persisted.storage_uri != artifact.storage_uri:
                        raise RuntimeError(
                            f"artifact URI changed concurrently: {artifact.artifact_id}"
                        )
                    persisted.storage_uri = write.storage_uri
            counters["migrated"] += 1
        return counters
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate live evidence from S3 to durable filesystem"
    )
    parser.add_argument("--since", type=datetime.fromisoformat)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.since is None:
        since = load_source_inventory().monitoring_measurement.public_epoch
    else:
        since = args.since
    if since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    result = asyncio.run(migrate(since=since.astimezone(UTC), dry_run=args.dry_run))
    print(result)


if __name__ == "__main__":
    main()
