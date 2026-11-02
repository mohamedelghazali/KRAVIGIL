import socket
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class SIEMDispatcher:
    @staticmethod
    def _format_cef(event_type: str, data: Dict[str, Any]) -> str:
        cef_header = "CEF:0|KRAVIGIL|Core|1.0|"
        severity = 5
        if "critical" in str(data).lower(): severity = 10
        elif "high" in str(data).lower(): severity = 8
        elif "medium" in str(data).lower(): severity = 5
        
        extension = " ".join([f"{k}={v}" for k, v in data.items() if isinstance(v, (str, int))])
        return f"{cef_header}{event_type}|{event_type}|{severity}|src=127.0.0.1 {extension}"

    @staticmethod
    def send_syslog(siem_config: Dict[str, Any], event_type: str, data: Dict[str, Any]) -> bool:
        if not siem_config or not siem_config.get("enabled"):
            return False

        host = siem_config.get("host")
        port = int(siem_config.get("port", 514))
        protocol = siem_config.get("protocol", "udp").lower()

        if not host:
            return False

        cef_message = SIEMDispatcher._format_cef(event_type, data)
        syslog_msg = f"<134>1 {cef_message}"

        try:
            if protocol == "tcp":
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(5.0)
                    s.connect((host, port))
                    s.sendall(syslog_msg.encode('utf-8'))
            else:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.sendto(syslog_msg.encode('utf-8'), (host, port))
            
            logger.info(f"SIEM event {event_type} sent to {host}:{port}")
            return True
        except Exception as e:
            logger.error(f"Failed to send SIEM event: {e}")
            return False
