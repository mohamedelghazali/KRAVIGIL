import logging
import uuid
from collections.abc import Mapping
from typing import Any

from backend.database.models.observation import Observation
from shared.protocols import network_engine_pb2

logger = logging.getLogger(__name__)


class Normalizer:
    @staticmethod
    def from_network_event(
        tenant_id: uuid.UUID,
        scan_id: uuid.UUID,
        asset_id: uuid.UUID,
        event: network_engine_pb2.ScanEvent,
    ) -> Observation | None:
        try:
            if event.event_type != "PORT_OPEN" or not 1 <= event.port <= 65535:
                return None
            return Observation(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                scan_id=scan_id,
                asset_id=asset_id,
                engine_id="network_cpp",
                event_type=event.event_type,
                raw_data={
                    "target_ip": event.target_ip,
                    "port": event.port,
                    "status": event.status,
                    "engine_version": event.engine_version or None,
                },
            )
        except (AttributeError, TypeError, ValueError):
            logger.exception("Normalization failed for network event")
            return None

    @staticmethod
    def from_nuclei_result(
        tenant_id: uuid.UUID,
        scan_id: uuid.UUID,
        asset_id: uuid.UUID,
        result: Mapping[str, Any],
    ) -> Observation:
        if not isinstance(result, Mapping):
            raise TypeError("Nuclei result must be a mapping")
        return Observation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            scan_id=scan_id,
            asset_id=asset_id,
            engine_id="nuclei",
            event_type="VULNERABILITY_FOUND",
            raw_data={
                "title": result.get("name"),
                "severity": result.get("severity"),
                "description": result.get("description"),
                "matched_at": result.get("matched_at"),
                "cve_id": result.get("cve_id"),
                "cwe_id": result.get("cwe_id"),
                "template_id": result.get("template_id"),
                "engine_version": result.get("engine_version"),
            },
        )

    @staticmethod
    def from_cloud_result(
        tenant_id: uuid.UUID,
        scan_id: uuid.UUID,
        asset_id: uuid.UUID,
        result: Mapping[str, Any],
    ) -> Observation:
        if not isinstance(result, Mapping):
            raise TypeError("Cloud result must be a mapping")
        raw = result.get("raw")
        raw_data = raw if isinstance(raw, Mapping) else {}
        return Observation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            scan_id=scan_id,
            asset_id=asset_id,
            engine_id="cloud_scanner",
            event_type="CLOUD_MISCONFIGURATION",
            raw_data={
                "title": result.get("title"),
                "severity": result.get("severity"),
                "description": result.get("description"),
                "resource_arn": raw_data.get("resource_arn"),
                "engine_version": result.get("engine_version"),
            },
        )
