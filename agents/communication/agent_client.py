import base64
import hashlib
import json
import time
import logging
from urllib.parse import urlsplit

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from typing import Any, Dict
from agents.identity.identity_manager import IdentityManager
from agents.execution.local_scanner import LocalScanner

logger = logging.getLogger(__name__)

class AgentClient:
    def __init__(self, control_plane_url: str):
        parsed_control_plane = urlsplit(control_plane_url)
        if parsed_control_plane.scheme != "https" and parsed_control_plane.hostname not in {
            "localhost", "127.0.0.1", "::1"
        }:
            raise ValueError("Agent control-plane connections must use HTTPS")
        self.control_plane_url = control_plane_url.rstrip("/")
        self.identity = IdentityManager()
        self.fingerprint, self.public_key = self.identity.generate_identity("kravigil-agent")
        with open(self.identity.key_path, "rb") as key_file:
            self.private_key = serialization.load_pem_private_key(
                key_file.read(), password=None
            )
        self.client = httpx.Client(verify=self.identity.get_ssl_context(), timeout=30.0)
        self.scanner = LocalScanner()
        self.headers = {"X-Agent-Fingerprint": self.fingerprint}

    def _signed_request(self, method: str, url: str, payload: Dict[str, Any] | None = None):
        body = b"" if payload is None else json.dumps(
            payload, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        timestamp = str(int(time.time()))
        parsed = urlsplit(url)
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        body_hash = hashlib.sha256(body).hexdigest()
        message = "\n".join(
            (method.upper(), path, timestamp, body_hash)
        ).encode("utf-8")
        signature = self.private_key.sign(
            message, padding.PKCS1v15(), hashes.SHA256()
        )
        headers = {
            "X-Agent-Fingerprint": self.fingerprint,
            "X-Agent-Timestamp": timestamp,
            "X-Agent-Signature": base64.urlsafe_b64encode(signature).decode("ascii").rstrip("="),
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"
        return self.client.request(method, url, content=body, headers=headers)

    def enroll(self, agent_name: str, version: str, ip_address: str, admin_token: str) -> bool:
        payload = {
            "name": agent_name,
            "certificate_fingerprint": self.fingerprint,
            "public_key": self.public_key,
            "version": version,
            "ip_address": ip_address
        }
        if not admin_token or not admin_token.strip():
            logger.error("Enrollment requires an administrator access token")
            return False
        try:
            response = self.client.post(
                f"{self.control_plane_url}/api/v1/agents/enroll",
                json=payload,
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            if response.status_code == 201:
                logger.info("Agent enrolled successfully")
                return True
            logger.error(f"Enrollment failed: {response.text}")
            return False
        except Exception as e:
            logger.error(f"Enrollment request failed: {e}")
            return False

    def send_heartbeat(self, status: str, ip_address: str) -> bool:
        payload = {"status": status, "ip_address": ip_address}
        try:
            response = self._signed_request(
                "POST", f"{self.control_plane_url}/api/v1/agents/heartbeat", payload
            )
            return response.status_code == 200
        except Exception as e:
            return False

    def poll_and_execute(self) -> None:
        try:
            response = self._signed_request("GET", f"{self.control_plane_url}/api/v1/agent-tasks/poll")
            if response.status_code != 200:
                return

            tasks = response.json()
            for task in tasks:
                self._execute_task(task)
        except Exception as e:
            logger.error(f"Polling failed: {e}")

    def _execute_task(self, task: Dict[str, Any]) -> None:
        task_id = task["id"]
        command = task["command_type"]
        params = task["parameters"]

        logger.info(f"Executing task {task_id} - {command}")

        try:
            if command == "START_SCAN":
                target_ip = params.get("target_ip")
                ports = params.get("ports", [22, 80, 443])
                observations = self.scanner.scan_target(target_ip, ports)

                payload = {
                    "status": "COMPLETED",
                    "observations": observations
                }
            else:
                payload = {
                    "status": "FAILED",
                    "error_message": f"Unknown command: {command}"
                }

            self._signed_request(
                "POST", f"{self.control_plane_url}/api/v1/agent-tasks/{task_id}/submit", payload
            )
        except Exception as e:
            logger.error(f"Task execution failed {task_id}: {e}")
            self._signed_request(
                "POST",
                f"{self.control_plane_url}/api/v1/agent-tasks/{task_id}/submit",
                {"status": "FAILED", "error_message": str(e)},
            )

    def run_loop(self, interval_seconds: int = 10):
        while True:
            try:
                self.send_heartbeat(status="ONLINE", ip_address="127.0.0.1")
                self.poll_and_execute()
                time.sleep(interval_seconds)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Agent loop error: {e}")
                time.sleep(10)
