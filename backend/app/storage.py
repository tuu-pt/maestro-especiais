from dataclasses import dataclass
from typing import Annotated, Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import Depends

from app.config import Settings, get_settings


def make_s3_client(settings: Settings) -> Any:
    """S3 client for any S3-compatible store (SeaweedFS in development)."""
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        aws_access_key_id=settings.s3_access_key or None,
        aws_secret_access_key=settings.s3_secret_key or None,
        region_name=settings.s3_region,
        config=Config(
            connect_timeout=3,
            read_timeout=60,
            retries={"max_attempts": 1},
            s3={"addressing_style": "path"},
        ),
    )


def ensure_bucket(client: Any, bucket: str) -> bool:
    """Create the bucket if missing. Returns True when it had to be created."""
    try:
        client.head_bucket(Bucket=bucket)
        return False
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") not in {"404", "NoSuchBucket"}:
            raise
    client.create_bucket(Bucket=bucket)
    return True


@dataclass
class ObjectStore:
    """Project files in the S3 bucket. Keys never contain original file names."""

    client: Any
    bucket: str

    def put(self, key: str, data: bytes, content_type: str | None = None) -> None:
        extra = {"ContentType": content_type} if content_type else {}
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, **extra)

    def get(self, key: str) -> bytes:
        return bytes(self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read())


def get_store(settings: Annotated[Settings, Depends(get_settings)]) -> ObjectStore:
    return ObjectStore(make_s3_client(settings), settings.s3_bucket)
