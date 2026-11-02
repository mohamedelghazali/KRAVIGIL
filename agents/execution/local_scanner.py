import logging
import socket
import concurrent.futures
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class LocalScanner:
    def __init__(self, timeout_ms: int = 1500):
        self.timeout_seconds = timeout_ms / 1000.0

    def scan_target(self, target_ip: str, ports: List[int]) -> List[Dict[str, Any]]:
        logger.info(f"Local scan started for {target_ip} on {len(ports)} ports")
        results = []

        def check_port(port):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(self.timeout_seconds)
                    result = s.connect_ex((target_ip, port))
                    if result == 0:
                        return port
            except Exception:
                pass
            return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
            future_to_port = {executor.submit(check_port, port): port for port in ports}
            for future in concurrent.futures.as_completed(future_to_port):
                port = future.result()
                if port:
                    results.append({
                        "event_type": "PORT_OPEN",
                        "target_ip": target_ip,
                        "port": port,
                        "status": "OPEN",
                        "engine": "agent_local_scanner"
                    })

        logger.info(f"Local scan completed for {target_ip}. Found {len(results)} open ports.")
        return results
