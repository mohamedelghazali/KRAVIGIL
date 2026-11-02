import hashlib
import pytest
from backend.services.evidence.minio_client import MinIOClient

@pytest.mark.integration
def test_evidence_hash_matches_on_upload():
    client = MinIOClient()
    data = b"test evidence data for hashing"
    expected = hashlib.sha256(data).hexdigest()
    key, actual, size = client.upload_bytes(f"test/{expected}.bin", data, "application/octet-stream")
    assert actual == expected
    assert size == len(data)
    client.delete_object(key)

@pytest.mark.integration
def test_evidence_hash_verification_on_download():
    client = MinIOClient()
    data = b"test data"
    expected = hashlib.sha256(data).hexdigest()
    key, _, _ = client.upload_bytes(f"test/verify_{expected}.bin", data, "application/octet-stream")
    try:
        stream = client.download_stream(key, expected)
        assert stream.read() == data
        stream.close()
    finally:
        client.delete_object(key)

@pytest.mark.integration
def test_evidence_hash_mismatch_is_rejected():
    client = MinIOClient()
    key, _, _ = client.upload_bytes("test/hash-mismatch.bin", b"original content", "application/octet-stream")
    try:
        with pytest.raises(ValueError, match="SHA-256 mismatch"):
            client.download_stream(key, "0" * 64)
    finally:
        client.delete_object(key)
