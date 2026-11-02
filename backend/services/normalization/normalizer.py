from backend.database.models.observation import Observation
import uuid

class Normalizer:
    @staticmethod
    def from_network_event(tenant_id: str, scan_id: str, asset_id: str, event) -> Observation:
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
                "status": event.status
            }
        )
