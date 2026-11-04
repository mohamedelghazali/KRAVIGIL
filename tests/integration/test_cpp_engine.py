from datetime import datetime, timedelta
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from engines.network_cpp.grpc_client import NetworkEngineClient


def _write_test_credentials(ca_path: Path, cert_path: Path, key_path: Path) -> None:
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "KRAVIGIL integration test CA")]
    )
    now = datetime.utcnow()
    ca_certificate = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )
    ca_path.write_bytes(ca_certificate.public_bytes(serialization.Encoding.PEM))

    client_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    client_name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "kravigil-test-client")]
    )
    client_certificate = (
        x509.CertificateBuilder()
        .subject_name(client_name)
        .issuer_name(ca_name)
        .public_key(client_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )
    cert_path.write_bytes(client_certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        client_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )


@pytest.mark.integration
def test_grpc_client_requires_mutual_tls_credentials_and_validates_scan_arguments(
    monkeypatch, tmp_path
):
    for name in (
        "KRAVIGIL_ENGINE_AUTH_TOKEN",
        "KRAVIGIL_TLS_CA",
        "KRAVIGIL_TLS_CLIENT_CERT",
        "KRAVIGIL_TLS_CLIENT_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValueError, match="KRAVIGIL_ENGINE_AUTH_TOKEN"):
        NetworkEngineClient(host="localhost", port=50051)

    ca_file = tmp_path / "test-ca.pem"
    client_cert_file = tmp_path / "client.crt"
    client_key_file = tmp_path / "client.key"
    _write_test_credentials(ca_file, client_cert_file, client_key_file)

    with pytest.raises(ValueError, match="KRAVIGIL_TLS_CLIENT_CERT"):
        NetworkEngineClient(
            host="localhost",
            port=50051,
            authorization_id="integration-test-token",
            root_cert_path=str(ca_file),
        )

    client = NetworkEngineClient(
        host="localhost",
        port=50051,
        authorization_id="integration-test-token",
        root_cert_path=str(ca_file),
        client_cert_path=str(client_cert_file),
        client_key_path=str(client_key_file),
    )
    try:
        with pytest.raises(ValueError, match="port"):
            list(client.start_scan("scan-invalid-port", "127.0.0.1", [0]))
        with pytest.raises(ValueError, match="scan_id"):
            list(client.start_scan("", "127.0.0.1", [443]))
        with pytest.raises(ValueError, match="timeout_ms"):
            list(
                client.start_scan(
                    "scan-invalid-timeout", "127.0.0.1", [443], timeout_ms=1
                )
            )
    finally:
        client.close()
