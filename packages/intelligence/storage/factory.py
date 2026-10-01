from __future__ import annotations

import boto3

from packages.intelligence.storage.artifacts import (
    ArtifactStore,
    FilesystemArtifactStore,
    S3ArtifactStore,
)
from packages.shared.config import Settings


def create_artifact_store(
    settings: Settings,
    *,
    bucket: str | None = None,
) -> ArtifactStore:
    resolved_bucket = bucket or settings.s3_bucket
    if settings.artifact_store_backend == "filesystem":
        return FilesystemArtifactStore(settings.artifact_root, bucket=resolved_bucket)
    return create_s3_artifact_store(settings, bucket=resolved_bucket)


def create_s3_artifact_store(
    settings: Settings,
    *,
    bucket: str | None = None,
) -> S3ArtifactStore:
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )
    return S3ArtifactStore(client, bucket=bucket or settings.s3_bucket)
