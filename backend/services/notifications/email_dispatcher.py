import smtplib
import logging
from email.message import EmailMessage
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class EmailDispatcher:
    @staticmethod
    def send_alert(smtp_config: Dict[str, Any], to_addresses: List[str], event_type: str, data: Dict[str, Any]) -> bool:
        if not smtp_config or not to_addresses:
            return False

        msg = EmailMessage()
        msg['Subject'] = f"KRAVIGIL: {event_type}"
        msg['From'] = smtp_config.get("from_address", "noreply@kravigil.local")
        msg['To'] = ", ".join(to_addresses)
        
        if event_type == "PASSWORD_RESET":
            body = f"Please click the link below to reset your password:\n\n{data.get('link')}\n\nIf you did not request this, ignore this email."
        else:
            body = f"Event: {event_type}\n\nDetails:\n"
            for key, value in data.items():
                body += f"- {key}: {value}\n"
                
        msg.set_content(body)

        try:
            with smtplib.SMTP(smtp_config.get("host", "localhost"), smtp_config.get("port", 587)) as server:
                if smtp_config.get("use_tls", True):
                    server.starttls()
                if smtp_config.get("username") and smtp_config.get("password"):
                    server.login(smtp_config["username"], smtp_config["password"])
                server.send_message(msg)
            logger.info(f"Email alert sent to {to_addresses} for event {event_type}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False
