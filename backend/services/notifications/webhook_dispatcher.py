import hmac
import hashlib
import json
import logging
import httpx
from typing import Dict, Any, List
from backend.database.models.webhook import Webhook

logger = logging.getLogger(__name__)

class WebhookDispatcher:
    @staticmethod
    def _generate_signature(secret: str, payload: str) -> str:
        return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def dispatch(webhooks: List[Webhook], event_type: str, data: Dict[str, Any]) -> None:
        payload = {"event": event_type, "data": data}
        payload_str = json.dumps(payload)
        with httpx.Client(timeout=10.0) as client:
            for webhook in webhooks:
                if not webhook.is_active or event_type not in webhook.events:
                    continue
                signature = WebhookDispatcher._generate_signature(webhook.secret, payload_str)
                headers = {
                    "Content-Type": "application/json",
                    "X-Kravigil-Signature": signature,
                    "X-Kravigil-Event": event_type
                }
                try:
                    response = client.post(webhook.url, content=payload_str, headers=headers)
                    response.raise_for_status()
                    logger.info("Webhook %s dispatched successfully", webhook.id)
                except httpx.HTTPError as exc:
                    logger.error("Webhook %s failed: %s", webhook.id, exc)
