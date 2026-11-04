#!/usr/bin/env python3
"""Verify, decrypt, and restore one encrypted KRAVIGIL PostgreSQL backup."""
import hashlib
import logging
import os
import subprocess
import tempfile
from pathlib import Path

from minio import Minio

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("kravigil.restore")
CHUNK_SIZE = 1024 * 1024


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be configured")
    return value


def _read_object(client: Minio, bucket: str, key: str, destination: Path) -> None:
    response = client.get_object(bucket, key)
    try:
        with destination.open("wb") as output:
            for chunk in response.stream(CHUNK_SIZE):
                output.write(chunk)
    finally:
        response.close()
        response.release_conn()


def _read_object_text(client: Minio, bucket: str, key: str) -> str:
    response = client.get_object(bucket, key)
    try:
        return response.read().decode("ascii")
    finally:
        response.close()
        response.release_conn()


def run_restore() -> str:
    backup_key = required("BACKUP_OBJECT_KEY")
    if not backup_key.startswith("postgresql/") or not backup_key.endswith(".dump.gpg"):
        raise ValueError("BACKUP_OBJECT_KEY must identify a PostgreSQL .dump.gpg object")

    production_db_name = os.getenv("DB_NAME", "kravigil_db")
    target_db_name = required("RESTORE_DB_NAME")
    if target_db_name == production_db_name:
        raise RuntimeError("Refusing to restore into DB_NAME; use a separate isolated database")
    if required("RESTORE_CONFIRMATION") != target_db_name:
        raise RuntimeError("RESTORE_CONFIRMATION must exactly match RESTORE_DB_NAME")

    target_host = required("RESTORE_DB_HOST")
    target_port = os.getenv("RESTORE_DB_PORT", "5432")
    target_user = required("RESTORE_DB_USER")
    target_password = required("RESTORE_DB_PASSWORD")
    encryption_key = required("BACKUP_ENCRYPTION_KEY")
    endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
    access_key = required("MINIO_ACCESS_KEY")
    secret_key = required("MINIO_SECRET_KEY")
    bucket = os.getenv("MINIO_BACKUP_BUCKET", "kravigil-backups")
    checksum_key = f"{backup_key}.sha256"

    client = Minio(
        endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
    )

    with tempfile.TemporaryDirectory(prefix="kravigil-restore-") as temp_dir:
        work_dir = Path(temp_dir)
        encrypted_dump = work_dir / "backup.dump.gpg"
        raw_dump = work_dir / "backup.dump"
        passphrase_file = work_dir / "backup-passphrase"

        _read_object(client, bucket, backup_key, encrypted_dump)
        checksum_text = _read_object_text(client, bucket, checksum_key).strip()
        checksum_parts = checksum_text.split()
        if len(checksum_parts) != 2 or checksum_parts[1] != Path(backup_key).name:
            raise ValueError("Backup checksum sidecar is malformed or references a different backup")
        expected_digest = checksum_parts[0].lower()
        if len(expected_digest) != 64 or any(c not in "0123456789abcdef" for c in expected_digest):
            raise ValueError("Backup checksum sidecar contains an invalid SHA-256 digest")

        digest_state = hashlib.sha256()
        with encrypted_dump.open("rb") as encrypted_file:
            for chunk in iter(lambda: encrypted_file.read(CHUNK_SIZE), b""):
                digest_state.update(chunk)
        actual_digest = digest_state.hexdigest()
        if actual_digest != expected_digest:
            raise ValueError(
                f"Backup SHA-256 mismatch: expected {expected_digest}, got {actual_digest}"
            )

        passphrase_file.write_text(encryption_key, encoding="utf-8")
        passphrase_file.chmod(0o600)
        subprocess.run(
            [
                "gpg", "--batch", "--yes", "--pinentry-mode", "loopback",
                "--passphrase-file", str(passphrase_file),
                "--output", str(raw_dump), "--decrypt", str(encrypted_dump),
            ],
            check=True,
            timeout=int(os.getenv("RESTORE_TIMEOUT_SECONDS", "14400")),
        )
        subprocess.run(
            ["pg_restore", "--list", str(raw_dump)],
            check=True,
            stdout=subprocess.DEVNULL,
            timeout=300,
        )

        restore_env = os.environ.copy()
        restore_env["PGPASSWORD"] = target_password
        subprocess.run(
            [
                "pg_restore", "--clean", "--if-exists", "--no-owner", "--no-acl",
                "--exit-on-error", "--single-transaction",
                "--host", target_host, "--port", target_port,
                "--username", target_user, "--dbname", target_db_name,
                str(raw_dump),
            ],
            env=restore_env,
            check=True,
            timeout=int(os.getenv("RESTORE_TIMEOUT_SECONDS", "14400")),
        )

    logger.info(
        "Backup %s restored into isolated database %s on %s",
        backup_key, target_db_name, target_host,
    )
    return target_db_name


if __name__ == "__main__":
    run_restore()
