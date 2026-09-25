from __future__ import annotations

import boto3

from packages.intelligence.storage.artifacts import S3ArtifactStore
from packages.shared.config import Settings


def create_s3_artifact_store(settings: Settings) -> S3ArtifactStore:
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )
    return S3ArtifactStore(client, bucket=settings.s3_bucket)
