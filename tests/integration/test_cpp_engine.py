from datetime import datetime, timedelta
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from engines.network_cpp.grpc_client import NetworkEngineClient


def _write_test_ca(path: Path) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "KRAVIGIL test CA")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow() - timedelta(minutes=1))
        .not_valid_after(datetime.utcnow() + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))


@pytest.mark.integration
def test_grpc_client_enforces_credentials_and_validates_scan_arguments(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("KRAVIGIL_ENGINE_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("KRAVIGIL_TLS_CA", raising=False)
    with pytest.raises(ValueError, match="KRAVIGIL_ENGINE_AUTH_TOKEN"):
        NetworkEngineClient(host="localhost", port=50051)

    ca_file = tmp_path / "test-ca.pem"
    _write_test_ca(ca_file)
    client = NetworkEngineClient(
        host="localhost",
        port=50051,
        authorization_id="integration-test-token",
        root_cert_path=str(ca_file),
    )
    try:
        with pytest.raises(ValueError, match="port"):
            list(client.start_scan("scan-invalid-port", "127.0.0.1", [0]))
        with pytest.raises(ValueError, match="scan_id"):
            list(client.start_scan("", "127.0.0.1", [443]))
        with pytest.raises(ValueError, match="timeout_ms"):
            list(client.start_scan("scan-invalid-timeout", "127.0.0.1", [443], timeout_ms=1))
    finally:
        client.close()
