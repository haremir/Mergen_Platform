"""
mergen_pkg_telegram.client
~~~~~~~~~~~~~~~~~~~~~~~~~~

Telegram Bot API Client operations.
"""

from __future__ import annotations

import logging
from typing import Any, Dict
import httpx

logger = logging.getLogger(__name__)


class TelegramClient:
    """Asynchronous client for sending messages via the Telegram Bot API."""

    def __init__(self) -> None:
        logger.info("TelegramClient initialized.")

    async def send_message(self, chat_id: str, text: str, bot_token: str) -> Dict[str, Any]:
        """Send a text message to a specific Telegram chat using the Telegram Bot API.

        POST https://api.telegram.org/bot<token>/sendMessage
        """
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        logger.info("TelegramClient.send_message: sending to chat_id=%s via bot_token=***%s", chat_id, bot_token[-5:] if len(bot_token) > 5 else "")
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            logger.info("TelegramClient.send_message: successfully sent message.")
            return data
