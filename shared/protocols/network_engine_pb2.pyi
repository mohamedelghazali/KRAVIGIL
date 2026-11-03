"""Type declarations for the generated network_engine_pb2 module."""
from typing import Iterable


class ScanRequest:
    scan_id: str
    authorization_id: str
    target_ip: str
    ports: Iterable[int]
    timeout_ms: int

    def __init__(
        self,
        *,
        scan_id: str = ...,
        authorization_id: str = ...,
        target_ip: str = ...,
        ports: Iterable[int] = ...,
        timeout_ms: int = ...,
    ) -> None: ...


class ScanEvent:
    scan_id: str
    event_type: str
    target_ip: str
    port: int
    status: str
    engine_version: str
    error_message: str
    completed_ports: int
    total_ports: int


class CancelRequest:
    scan_id: str
    authorization_id: str

    def __init__(
        self, *, scan_id: str = ..., authorization_id: str = ...
    ) -> None: ...


class CancelResponse:
    accepted: bool
    message: str
