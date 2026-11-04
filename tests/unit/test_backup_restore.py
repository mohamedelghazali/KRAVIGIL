import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import infrastructure.backup.pg_restore as restore_module


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.closed = False
        self.released = False

    def stream(self, chunk_size):
        yield self.payload

    def read(self):
        return self.payload

    def close(self):
        self.closed = True

    def release_conn(self):
        self.released = True


class FakeMinio:
    def __init__(self, endpoint, access_key, secret_key, secure):
        self.objects = {
            "postgresql/2026/11/04/kravigil-test.dump.gpg": b"encrypted-dump",
        }
        key = "postgresql/2026/11/04/kravigil-test.dump.gpg"
        digest = hashlib.sha256(self.objects[key]).hexdigest()
        self.objects[f"{key}.sha256"] = f"{digest}  kravigil-test.dump.gpg\n".encode()

    def get_object(self, bucket, key):
        if key not in self.objects:
            raise FileNotFoundError(key)
        return FakeResponse(self.objects[key])


def _set_restore_environment(monkeypatch):
    values = {
        "BACKUP_OBJECT_KEY": "postgresql/2026/11/04/kravigil-test.dump.gpg",
        "DB_NAME": "kravigil_db",
        "RESTORE_DB_NAME": "kravigil_recovery_test",
        "RESTORE_CONFIRMATION": "kravigil_recovery_test",
        "RESTORE_DB_HOST": "127.0.0.1",
        "RESTORE_DB_PORT": "5432",
        "RESTORE_DB_USER": "restore_user",
        "RESTORE_DB_PASSWORD": "restore-password",
        "BACKUP_ENCRYPTION_KEY": "independently-escrowed-passphrase",
        "MINIO_ENDPOINT": "minio.example:9000",
        "MINIO_ACCESS_KEY": "access",
        "MINIO_SECRET_KEY": "secret",
        "MINIO_BACKUP_BUCKET": "kravigil-backups",
        "MINIO_SECURE": "true",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def test_restore_verifies_checksum_and_uses_isolated_single_transaction(
    monkeypatch,
):
    _set_restore_environment(monkeypatch)
    monkeypatch.setattr(restore_module, "Minio", FakeMinio)
    commands = []

    def fake_run(command, **kwargs):
        commands.append((command, kwargs))
        if command[0] == "gpg":
            output_path = Path(command[command.index("--output") + 1])
            output_path.write_bytes(b"restored-archive")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(restore_module.subprocess, "run", fake_run)

    assert restore_module.run_restore() == "kravigil_recovery_test"
    gpg_command = next(command for command, _ in commands if command[0] == "gpg")
    restore_command, restore_kwargs = next(
        (command, kwargs)
        for command, kwargs in commands
        if command[0] == "pg_restore" and "--dbname" in command
    )
    assert "--single-transaction" in restore_command
    assert "--exit-on-error" in restore_command
    assert restore_command[restore_command.index("--dbname") + 1] == "kravigil_recovery_test"
    assert restore_kwargs["env"]["PGPASSWORD"] == "restore-password"
    assert "--passphrase-file" in gpg_command


def test_restore_refuses_production_database(monkeypatch):
    _set_restore_environment(monkeypatch)
    monkeypatch.setenv("RESTORE_DB_NAME", "kravigil_db")
    monkeypatch.setenv("RESTORE_CONFIRMATION", "kravigil_db")
    with pytest.raises(RuntimeError, match="Refusing to restore into DB_NAME"):
        restore_module.run_restore()


def test_restore_requires_exact_confirmation(monkeypatch):
    _set_restore_environment(monkeypatch)
    monkeypatch.setenv("RESTORE_CONFIRMATION", "wrong-database")
    with pytest.raises(RuntimeError, match="must exactly match"):
        restore_module.run_restore()


def test_restore_rejects_checksum_mismatch_before_decryption(monkeypatch):
    _set_restore_environment(monkeypatch)

    class BadChecksumMinio(FakeMinio):
        def __init__(self, endpoint, access_key, secret_key, secure):
            super().__init__(endpoint, access_key, secret_key, secure)
            key = "postgresql/2026/11/04/kravigil-test.dump.gpg.sha256"
            self.objects[key] = (
                "0" * 64 + "  kravigil-test.dump.gpg\n"
            ).encode()

    monkeypatch.setattr(restore_module, "Minio", BadChecksumMinio)
    monkeypatch.setattr(
        restore_module.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("subprocess must not run for a bad checksum"),
    )
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        restore_module.run_restore()
