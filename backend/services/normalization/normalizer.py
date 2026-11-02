import uuid
import logging
from backend.database.models.observation import Observation
from shared.protocols import network_engine_pb2

logger = logging.getLogger(__name__)

class Normalizer:
    @staticmethod
    def from_network_event(tenant_id: uuid.UUID, scan_id: uuid.UUID, asset_id: uuid.UUID, event: network_engine_pb2.ScanEvent) -> Observation | None:
        try:
            if event.event_type == "PORT_OPEN":
                return Observation(
                    id=uuid.uuid4(), tenant_id=tenant_id, scan_id=scan_id, asset_id=asset_id,
                    engine_id="network_cpp", event_type=event.event_type,
                    raw_data={"target_ip": event.target_ip, "port": event.port, "status": event.status, "details": event.details}
                )
        except Exception as e:
            logger.error(f"Normalization failed for network event: {e}")
        return None

    @staticmethod
    def from_nuclei_result(tenant_id: uuid.UUID, scan_id: uuid.UUID, asset_id: uuid.UUID, result: dict) -> Observation:
        return Observation(
            id=uuid.uuid4(), tenant_id=tenant_id, scan_id=scan_id, asset_id=asset_id,
            engine_id="nuclei", event_type="VULNERABILITY_FOUND",
            raw_data={
                "title": result.get("name"), "severity": result.get("severity"),
                "description": result.get("description"), "matched_at": result.get("matched_at"),
                "cve_id": result.get("cve_id"), "cwe_id": result.get("cwe_id"), "template_id": result.get("template_id")
            }
        )

    @staticmethod
    def from_semgrep_result(tenant_id: uuid.UUID, scan_id: uuid.UUID, asset_id: uuid.UUID, result: dict) -> Observation:
        return Observation(
            id=uuid.uuid4(), tenant_id=tenant_id, scan_id=scan_id, asset_id=asset_id,
            engine_id="semgrep", event_type="CODE_VULNERABILITY",
            raw_data={
                "title": result.get("check_id"), "severity": result.get("severity"),
                "description": result.get("message"), "path": result.get("path"),
                "line": result.get("line"), "cwe_id": result.get("cwe_id")
            }
        )

    @staticmethod
    def from_gitleaks_result(tenant_id: uuid.UUID, scan_id: uuid.UUID, asset_id: uuid.UUID, result: dict) -> Observation:
        return Observation(
            id=uuid.uuid4(), tenant_id=tenant_id, scan_id=scan_id, asset_id=asset_id,
            engine_id="gitleaks", event_type="SECRET_FOUND",
            raw_data={
                "title": result.get("title"), "severity": result.get("severity"),
                "description": result.get("description"), "file": result.get("file"),
                "line": result.get("line"), "rule_id": result.get("rule_id")
            }
        )

    @staticmethod
    def from_trivy_result(tenant_id: uuid.UUID, scan_id: uuid.UUID, asset_id: uuid.UUID, result: dict) -> Observation:
        return Observation(
            id=uuid.uuid4(), tenant_id=tenant_id, scan_id=scan_id, asset_id=asset_id,
            engine_id="trivy", event_type="CONTAINER_VULNERABILITY",
            raw_data={
                "title": result.get("title"), "severity": result.get("severity"),
                "description": result.get("description"), "cve_id": result.get("cve_id"),
                "package_name": result.get("package_name"), "installed_version": result.get("installed_version"),
                "fixed_version": result.get("fixed_version")
            }
        )
