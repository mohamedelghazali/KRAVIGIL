import logging
import os
from pathlib import Path
from typing import Iterator, List, Optional

import grpc

from shared.protocols import network_engine_pb2, network_engine_pb2_grpc

logger = logging.getLogger(__name__)


class NetworkEngineClient:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 50051,
        authorization_id: Optional[str] = None,
        root_cert_path: Optional[str] = None,
        client_cert_path: Optional[str] = None,
        client_key_path: Optional[str] = None,
    ) -> None:
        token = authorization_id or os.getenv("KRAVIGIL_ENGINE_AUTH_TOKEN")
        cert_path = root_cert_path or os.getenv("KRAVIGIL_TLS_CA")
        client_certificate_path = client_cert_path or os.getenv("KRAVIGIL_TLS_CLIENT_CERT")
        client_private_key_path = client_key_path or os.getenv("KRAVIGIL_TLS_CLIENT_KEY")

        if not token:
            raise ValueError("KRAVIGIL_ENGINE_AUTH_TOKEN is required")
        if not cert_path:
            raise ValueError("KRAVIGIL_TLS_CA is required")
        if not client_certificate_path:
            raise ValueError("KRAVIGIL_TLS_CLIENT_CERT is required for mutual TLS")
        if not client_private_key_path:
            raise ValueError("KRAVIGIL_TLS_CLIENT_KEY is required for mutual TLS")

        cert_file = Path(cert_path)
        client_cert_file = Path(client_certificate_path)
        client_key_file = Path(client_private_key_path)
        for label, path in (
            ("TLS CA certificate", cert_file),
            ("TLS client certificate", client_cert_file),
            ("TLS client private key", client_key_file),
        ):
            if not path.is_file():
                raise FileNotFoundError(f"{label} not found: {path}")

        credentials = grpc.ssl_channel_credentials(
            root_certificates=cert_file.read_bytes(),
            private_key=client_key_file.read_bytes(),
            certificate_chain=client_cert_file.read_bytes(),
        )
        self.authorization_id = token
        self.channel = grpc.secure_channel(
            f"{host}:{port}",
            credentials,
            options=[
                ("grpc.max_send_message_length", 4 * 1024 * 1024),
                ("grpc.max_receive_message_length", 4 * 1024 * 1024),
            ],
        )
        self.stub = network_engine_pb2_grpc.NetworkScannerStub(self.channel)

    def start_scan(
        self,
        scan_id: str,
        target_ip: str,
        ports: List[int],
        timeout_ms: int = 1500,
        rpc_timeout: float = 3600,
    ) -> Iterator:
        if not scan_id or not target_ip:
            raise ValueError("scan_id and target_ip are required")
        if not ports:
            raise ValueError("At least one port is required")
        if any(not isinstance(port, int) or port < 1 or port > 65535 for port in ports):
            raise ValueError("Every port must be between 1 and 65535")
        if timeout_ms < 100 or timeout_ms > 30000:
            raise ValueError("timeout_ms must be between 100 and 30000")

        request = network_engine_pb2.ScanRequest(
            scan_id=scan_id,
            authorization_id=self.authorization_id,
            target_ip=target_ip,
            ports=ports,
            timeout_ms=timeout_ms,
        )

        try:
            for event in self.stub.StartScan(request, timeout=rpc_timeout):
                yield event
                if event.event_type in {"COMPLETED", "CANCELLED", "ERROR"}:
                    break
        except grpc.RpcError as exc:
            logger.error("Network Engine stream failed: %s - %s", exc.code(), exc.details())
            raise RuntimeError(f"Network Engine failure: {exc.details()}") from exc

    def cancel_scan(self, scan_id: str) -> bool:
        if not scan_id:
            raise ValueError("scan_id is required")

        request = network_engine_pb2.CancelRequest(
            scan_id=scan_id,
            authorization_id=self.authorization_id,
        )
        try:
            response = self.stub.CancelScan(request, timeout=10)
            return response.accepted
        except grpc.RpcError as exc:
            logger.error("Cancel scan failed: %s - %s", exc.code(), exc.details())
            return False

    def close(self) -> None:
        self.channel.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
