import hashlib
import io
import logging
import tempfile
from datetime import timedelta
from typing import BinaryIO, Optional, Tuple
from minio import Minio
from minio.error import S3Error
from backend.core.config import get_settings

logger = logging.getLogger(__name__)
CHUNK_SIZE = 1024 * 1024

class MinIOClient:
    def __init__(self):
        settings = get_settings()
        self.client = Minio(settings.MINIO_ENDPOINT, access_key=settings.MINIO_ACCESS_KEY,
                            secret_key=settings.MINIO_SECRET_KEY, secure=settings.MINIO_SECURE)
        self.bucket = settings.MINIO_BUCKET
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info("Created evidence bucket %s", self.bucket)
        except S3Error:
            logger.exception("Failed to ensure MinIO bucket %s", self.bucket)
            raise

    def upload_stream(self, object_key: str, stream: BinaryIO, content_type: str,
                      size: Optional[int] = None) -> Tuple[str, str, int]:
        if not object_key or object_key.startswith("/") or ".." in object_key.split("/"):
            raise ValueError("Invalid object key")
        if not content_type:
            raise ValueError("content_type is required")
        digest, total = hashlib.sha256(), 0
        with tempfile.SpooledTemporaryFile(max_size=8 * CHUNK_SIZE, mode="w+b") as buffer:
            while True:
                chunk = stream.read(CHUNK_SIZE)
                if not chunk:
                    break
                if not isinstance(chunk, (bytes, bytearray)):
                    raise TypeError("Evidence stream must return bytes")
                digest.update(chunk)
                buffer.write(chunk)
                total += len(chunk)
            if size is not None and total != size:
                raise ValueError(f"Evidence size mismatch: expected {size}, received {total}")
            buffer.seek(0)
            try:
                self.client.put_object(self.bucket, object_key, buffer, total, content_type=content_type)
            except S3Error:
                logger.exception("MinIO upload failed for %s", object_key)
                raise
        sha = digest.hexdigest()
        logger.info("Uploaded evidence %s (%s bytes, sha256=%s)", object_key, total, sha)
        return object_key, sha, total

    def upload_bytes(self, object_key: str, data: bytes, content_type: str) -> Tuple[str, str, int]:
        return self.upload_stream(object_key, io.BytesIO(data), content_type, len(data))

    def download_stream(self, object_key: str, expected_sha256: Optional[str] = None) -> io.BytesIO:
        response = None
        try:
            response = self.client.get_object(self.bucket, object_key)
            digest, buffer = hashlib.sha256(), io.BytesIO()
            for chunk in response.stream(CHUNK_SIZE):
                digest.update(chunk)
                buffer.write(chunk)
            actual = digest.hexdigest()
            if expected_sha256 and actual.lower() != expected_sha256.lower():
                buffer.close()
                raise ValueError(f"SHA-256 mismatch: expected {expected_sha256}, got {actual}")
            buffer.seek(0)
            return buffer
        except S3Error:
            logger.exception("MinIO download failed for %s", object_key)
            raise
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    def delete_object(self, object_key: str) -> None:
        try:
            self.client.remove_object(self.bucket, object_key)
            logger.info("Deleted evidence object %s", object_key)
        except S3Error:
            logger.exception("MinIO delete failed for %s", object_key)
            raise

    def generate_presigned_url(self, object_key: str, expires_seconds: int = 300) -> str:
        if not 1 <= expires_seconds <= 604800:
            raise ValueError("Presigned URL expiry must be between 1 second and 7 days")
        try:
            return self.client.presigned_get_object(self.bucket, object_key,
                                                    expires=timedelta(seconds=expires_seconds))
        except S3Error:
            logger.exception("Presigned URL generation failed for %s", object_key)
            raise
