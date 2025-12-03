"""
Minimal Upstash QStash publish helper.

Usage:
    from shop.tasks.qstash_client import publish
    publish("https://your-domain/api/jobs/shipment-status", {"shipment_id": "...", "carrier_status": "shipped", "event_id": "evt_123"})
"""

import os
from typing import Any, Dict

from dotenv import load_dotenv
import httpx

# Ensure env is loaded when running outside Flask
load_dotenv()


class QStashClient:
    def __init__(self, token: str) -> None:
        if not token:
            raise RuntimeError("QSTASH_TOKEN is required to publish messages.")
        self.token = token
        self.base_url = os.environ.get("QSTASH_URL", "https://qstash.upstash.io")
        if self.base_url.endswith("/"):
            self.base_url = self.base_url.rstrip("/")

    def publish(self, target_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Publish a message to QStash that will POST to target_url.
        target_url should be the full https URL of your handler.
        """
        api_url = f"{self.base_url}/v2/publish/{target_url}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        response = httpx.post(api_url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()


def publish(target_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    client = QStashClient(os.environ.get("QSTASH_TOKEN", ""))
    return client.publish(target_url, payload)

