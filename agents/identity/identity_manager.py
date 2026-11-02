import os
import ssl
import uuid
import logging
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography import x509
from cryptography.x509.oid import NameOID
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class IdentityManager:
    def __init__(self, agent_dir: str = "/etc/kravigil/agent"):
        self.agent_dir = agent_dir
        self.key_path = os.path.join(agent_dir, "agent.key")
        self.cert_path = os.path.join(agent_dir, "agent.crt")
        os.makedirs(agent_dir, exist_ok=True)

    def generate_identity(self, agent_name: str) -> tuple[str, str]:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
        
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, agent_name),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "KRAVIGIL Agent"),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName([x509.DNSName(agent_name)]),
            critical=False,
        ).sign(private_key, hashes.SHA256())

        with open(self.key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))

        with open(self.cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        fingerprint = cert.fingerprint(hashes.SHA256()).hex()
        public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')

        logger.info(f"Generated agent identity with fingerprint {fingerprint}")
        return fingerprint, public_key

    def get_ssl_context(self) -> ssl.SSLContext:
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        context.load_cert_chain(certfile=self.cert_path, keyfile=self.key_path)
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        return context
