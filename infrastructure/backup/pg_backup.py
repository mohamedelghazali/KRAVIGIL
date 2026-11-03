#!/usr/bin/env python3
"""Encrypted PostgreSQL backups uploaded to the private MinIO backup bucket."""
import hashlib
import logging
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from minio import Minio

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("kravigil.backup")


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be configured")
    return value


def run_backup() -> str:
    db_host = os.getenv("DB_HOST", "db")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "kravigil_db")
    db_user = os.getenv("DB_USER", "kravigil_admin")
    db_password = required("DB_PASSWORD")
    encryption_key = required("BACKUP_ENCRYPTION_KEY")
    endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
    access_key = required("MINIO_ACCESS_KEY")
    secret_key = required("MINIO_SECRET_KEY")
    bucket = os.getenv("MINIO_BACKUP_BUCKET", "kravigil-backups")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    object_prefix = f"postgresql/{datetime.now(timezone.utc):%Y/%m/%d}"
    object_name = f"kravigil-{stamp}.dump.gpg"

    with tempfile.TemporaryDirectory(prefix="kravigil-backup-") as temp_dir:
        raw_dump = Path(temp_dir) / f"kravigil-{stamp}.dump"
        encrypted_dump = Path(temp_dir) / object_name
        env = os.environ.copy()
        env["PGPASSWORD"] = db_password

        subprocess.run(
            [
                "pg_dump", "--host", db_host, "--port", db_port,
                "--username", db_user, "--dbname", db_name,
                "--format=custom", "--no-owner", "--no-acl",
                "--file", str(raw_dump),
            ],
            env=env,
            check=True,
            timeout=int(os.getenv("BACKUP_TIMEOUT_SECONDS", "14400")),
        )
        subprocess.run(
            [
                "pg_restore", "--list", str(raw_dump),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            timeout=300,
        )
        passphrase_file = Path(temp_dir) / "backup-passphrase"
        passphrase_file.write_text(encryption_key, encoding="utf-8")
        passphrase_file.chmod(0o600)
        subprocess.run(
            [
                "gpg", "--batch", "--yes", "--pinentry-mode", "loopback",
                "--passphrase-file", str(passphrase_file),
                "--symmetric", "--cipher-algo", "AES256",
                "--s2k-digest-algo", "SHA512", "--s2k-count", "65011712",
                "--output", str(encrypted_dump), str(raw_dump),
            ],
            check=True,
            timeout=int(os.getenv("BACKUP_TIMEOUT_SECONDS", "14400")),
        )

        digest_state = hashlib.sha256()
        with encrypted_dump.open("rb") as encrypted_file:
            for chunk in iter(lambda: encrypted_file.read(1024 * 1024), b""):
                digest_state.update(chunk)
        digest = digest_state.hexdigest()
        client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
        )
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)

        object_key = f"{object_prefix}/{object_name}"
        client.fput_object(
            bucket, object_key, str(encrypted_dump),
            content_type="application/octet-stream",
        )
        checksum_file = Path(temp_dir) / f"{object_name}.sha256"
        checksum_file.write_text(f"{digest}  {object_name}\n", encoding="ascii")
        client.fput_object(
            bucket, f"{object_key}.sha256", str(checksum_file),
            content_type="text/plain",
        )

        Path("/tmp/last-success").touch()
        logger.info(
            "Backup uploaded: bucket=%s key=%s size=%s sha256=%s",
            bucket, object_key, encrypted_dump.stat().st_size, digest,
        )
        return object_key


if __name__ == "__main__":
    run_backup()
