import base64
import hashlib
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.database.models.agent import Agent
from backend.database.session import get_db

AGENT_SIGNATURE_MAX_SKEW_SECONDS = 300


def _canonical_request(method: str, path: str, timestamp: str, body: bytes) -> bytes:
    body_hash = hashlib.sha256(body).hexdigest()
    return "\n".join(
        (method.upper(), path, timestamp, body_hash)
    ).encode("utf-8")


async def get_authenticated_agent(
    request: Request,
    db: Session = Depends(get_db),
) -> Agent:
    fingerprint = request.headers.get("X-Agent-Fingerprint", "")
    timestamp = request.headers.get("X-Agent-Timestamp", "")
    signature = request.headers.get("X-Agent-Signature", "")
    if not fingerprint or not timestamp or not signature:
        raise HTTPException(status_code=401, detail="Agent authentication headers missing")

    try:
        issued_at = int(timestamp)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid agent request timestamp")

    if abs(int(time.time()) - issued_at) > AGENT_SIGNATURE_MAX_SKEW_SECONDS:
        raise HTTPException(status_code=401, detail="Expired agent request signature")

    agent = db.query(Agent).filter(
        Agent.certificate_fingerprint == fingerprint,
        Agent.status != "REVOKED",
    ).first()
    if agent is None:
        raise HTTPException(status_code=401, detail="Agent not found or revoked")

    body = await request.body()
    path = request.url.path
    if request.url.query:
        path = f"{path}?{request.url.query}"
    message = _canonical_request(request.method, path, timestamp, body)

    try:
        public_key = serialization.load_pem_public_key(agent.public_key.encode("utf-8"))
        if not isinstance(public_key, rsa.RSAPublicKey) or public_key.key_size < 2048:
            raise HTTPException(status_code=401, detail="Unsupported agent public key")
        decoded_signature = base64.urlsafe_b64decode(
            signature + "=" * (-len(signature) % 4)
        )
        public_key.verify(
            decoded_signature,
            message,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except (ValueError, TypeError, InvalidSignature):
        raise HTTPException(status_code=401, detail="Invalid agent request signature")

    return agent
