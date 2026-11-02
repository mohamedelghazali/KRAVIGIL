import time
import logging
import httpx
from typing import Dict, Any
from agents.identity.identity_manager import IdentityManager

logger = logging.getLogger(__name__)

class AgentClient:
    def __init__(self, control_plane_url: str):
        self.control_plane_url = control_plane_url
        self.identity = IdentityManager()
        self.fingerprint, self.public_key = self.identity.generate_identity("kravigil-agent")
        self.client = httpx.Client(verify=self.identity.get_ssl_context(), timeout=30.0)

    def enroll(self, agent_name: str, version: str, ip_address: str) -> bool:
        payload = {
            "name": agent_name,
            "certificate_fingerprint": self.fingerprint,
            "public_key": self.public_key,
            "version": version,
            "ip_address": ip_address
        }
        try:
            response = self.client.post(f"{self.control_plane_url}/api/v1/agents/enroll", json=payload)
            if response.status_code == 201:
                logger.info("Agent enrolled successfully")
                return True
            else:
                logger.error(f"Enrollment failed: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Enrollment request failed: {e}")
            return False

    def send_heartbeat(self, status: str, ip_address: str) -> bool:
        payload = {
            "certificate_fingerprint": self.fingerprint,
            "status": status,
            "ip_address": ip_address
        }
        try:
            response = self.client.post(f"{self.control_plane_url}/api/v1/agents/heartbeat", json=payload)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Heartbeat failed: {e}")
            return False

    def run_heartbeat_loop(self, interval_seconds: int = 60):
        while True:
            try:
                self.send_heartbeat(status="ONLINE", ip_address="127.0.0.1")
                time.sleep(interval_seconds)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
                time.sleep(10)
