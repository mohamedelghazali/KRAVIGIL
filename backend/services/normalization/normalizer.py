import logging
import uuid
from typing import Optional

from backend.database.models.observation import Observation

logger = logging.getLogger(__name__)


class Normalizer:
    @staticmethod
    def from_network_event(
        tenant_id: uuid.UUID,
        scan_id: uuid.UUID,
        asset_id: uuid.UUID,
        event,
    ) -> Optional[Observation]:
        try:
            if event.event_type != "PORT_OPEN":
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
                    "port": int(event.port),
                    "status": event.status,
                    "engine_version": event.engine_version,
                },
            )
        except (AttributeError, TypeError, ValueError) as exc:
            logger.exception("Failed to normalize network event: %s", exc)
            return None
