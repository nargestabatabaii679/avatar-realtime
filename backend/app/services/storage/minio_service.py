from __future__ import annotations

import io
import uuid
from datetime import timedelta
from pathlib import Path
from typing import AsyncIterator, Optional

import structlog
from minio import Minio
from minio.commonconfig import ENABLED, Filter
from minio.error import S3Error
from minio.lifecycleconfig import LifecycleConfig, Rule, Expiration

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_client: Optional[Minio] = None


def get_minio_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
    return _client


BUCKETS = {
    "avatars": settings.MINIO_BUCKET_AVATARS,
    "voices": settings.MINIO_BUCKET_VOICES,
    "videos": settings.MINIO_BUCKET_VIDEOS,
    "documents": settings.MINIO_BUCKET_DOCUMENTS,
    "temp": "avatar-temp",
    "thumbnails": "avatar-thumbnails",
}


async def init_buckets() -> None:
    """Create all required buckets on startup if they don't exist."""
    client = get_minio_client()
    for name, bucket in BUCKETS.items():
        try:
            if not client.bucket_exists(bucket):
                client.make_bucket(bucket)
                logger.info("bucket_created", bucket=bucket)
            else:
                logger.debug("bucket_exists", bucket=bucket)
        except S3Error as e:
            logger.error("bucket_init_failed", bucket=bucket, error=str(e))
            raise

    # Set lifecycle: auto-delete temp files after 24 hours
    try:
        client.set_bucket_lifecycle(
            BUCKETS["temp"],
            LifecycleConfig(
                [
                    Rule(
                        ENABLED,
                        rule_filter=Filter(prefix=""),
                        rule_id="expire-temp",
                        expiration=Expiration(days=1),
                    )
                ]
            ),
        )
    except Exception:
        pass  # Lifecycle may not be supported in all MinIO versions


async def upload_file(
    bucket_key: str,
    object_name: str,
    data: bytes | io.BytesIO,
    content_type: str = "application/octet-stream",
    metadata: Optional[dict] = None,
) -> str:
    """Upload bytes or BytesIO to MinIO. Returns the object path."""
    client = get_minio_client()
    bucket = BUCKETS.get(bucket_key, bucket_key)

    if isinstance(data, bytes):
        stream = io.BytesIO(data)
        size = len(data)
    else:
        stream = data
        stream.seek(0, 2)
        size = stream.tell()
        stream.seek(0)

    client.put_object(
        bucket_name=bucket,
        object_name=object_name,
        data=stream,
        length=size,
        content_type=content_type,
        metadata=metadata or {},
    )
    logger.info("file_uploaded", bucket=bucket, object=object_name, size=size)
    return f"{bucket}/{object_name}"


async def upload_file_path(
    bucket_key: str,
    object_name: str,
    file_path: str | Path,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload a local file path to MinIO."""
    client = get_minio_client()
    bucket = BUCKETS.get(bucket_key, bucket_key)
    client.fput_object(
        bucket_name=bucket,
        object_name=object_name,
        file_path=str(file_path),
        content_type=content_type,
    )
    return f"{bucket}/{object_name}"


async def download_file(bucket_key: str, object_name: str) -> bytes:
    """Download object and return bytes."""
    client = get_minio_client()
    bucket = BUCKETS.get(bucket_key, bucket_key)
    response = client.get_object(bucket, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


async def download_to_path(bucket_key: str, object_name: str, dest_path: str | Path) -> None:
    """Download object to a local file path."""
    client = get_minio_client()
    bucket = BUCKETS.get(bucket_key, bucket_key)
    client.fget_object(bucket, object_name, str(dest_path))


def get_presigned_url(
    bucket_key: str,
    object_name: str,
    expires: timedelta = timedelta(hours=1),
    method: str = "GET",
) -> str:
    """Generate a presigned URL for download (GET) or upload (PUT)."""
    client = get_minio_client()
    bucket = BUCKETS.get(bucket_key, bucket_key)
    if method.upper() == "PUT":
        return client.presigned_put_object(bucket, object_name, expires=expires)
    return client.presigned_get_object(bucket, object_name, expires=expires)


async def delete_object(bucket_key: str, object_name: str) -> None:
    """Delete a single object."""
    client = get_minio_client()
    bucket = BUCKETS.get(bucket_key, bucket_key)
    try:
        client.remove_object(bucket, object_name)
        logger.info("object_deleted", bucket=bucket, object=object_name)
    except S3Error as e:
        if e.code != "NoSuchKey":
            raise


async def delete_prefix(bucket_key: str, prefix: str) -> int:
    """Delete all objects under a given prefix. Returns count deleted."""
    client = get_minio_client()
    bucket = BUCKETS.get(bucket_key, bucket_key)
    objects = client.list_objects(bucket, prefix=prefix, recursive=True)
    count = 0
    for obj in objects:
        client.remove_object(bucket, obj.object_name)
        count += 1
    logger.info("prefix_deleted", bucket=bucket, prefix=prefix, count=count)
    return count


async def object_exists(bucket_key: str, object_name: str) -> bool:
    """Check if an object exists."""
    client = get_minio_client()
    bucket = BUCKETS.get(bucket_key, bucket_key)
    try:
        client.stat_object(bucket, object_name)
        return True
    except S3Error as e:
        if e.code == "NoSuchKey":
            return False
        raise


async def get_storage_usage(org_id: str) -> dict[str, int]:
    """Calculate storage usage per resource type for an organization."""
    client = get_minio_client()
    usage: dict[str, int] = {}
    for resource_type, bucket in BUCKETS.items():
        if resource_type == "temp":
            continue
        try:
            total = 0
            for obj in client.list_objects(bucket, prefix=f"{org_id}/", recursive=True):
                total += obj.size or 0
            usage[resource_type] = total
        except Exception:
            usage[resource_type] = 0
    return usage


def generate_object_name(org_id: str, resource_type: str, filename: str, unique: bool = True) -> str:
    """Generate a structured object name: {org_id}/{resource_type}/{uuid}_{filename}"""
    suffix = f"{uuid.uuid4().hex}_" if unique else ""
    safe_name = Path(filename).name
    return f"{org_id}/{resource_type}/{suffix}{safe_name}"
