import logging
from slack_sdk.webhook import WebhookClient
from typing import Dict, Any

logger = logging.getLogger(__name__)

class SlackDispatcher:
    @staticmethod
    def send_alert(webhook_url: str, event_type: str, data: Dict[str, Any]) -> bool:
        if not webhook_url:
            return False
            
        try:
            client = WebhookClient(webhook_url)
            
            color = "#36a64f"
            if "failed" in event_type or "critical" in str(data).lower():
                color = "#ff0000"
            elif "high" in str(data).lower():
                color = "#ff9900"
                
            message = {
                "attachments": [
                    {
                        "color": color,
                        "title": f"KRAVIGIL Alert: {event_type}",
                        "text": f"Event Details:\n```{data}```",
                        "footer": "KRAVIGIL Security Platform"
                    }
                ]
            }
            
            response = client.send_dict(message)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Slack dispatch failed: {e}")
            return False
