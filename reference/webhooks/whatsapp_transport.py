"""WhatsApp channel implementation using Meta Business Cloud API."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional
import httpx

from dentbot.channels.base_channel import BaseChannel
from dentbot.config import get_config

logger = logging.getLogger(__name__)


def convert_html_to_whatsapp_markdown(text: str) -> str:
    """Converts simple HTML tags (b, i, code) to WhatsApp-compatible markdown (*, _, `)."""
    if not text:
        return text
    # Replace HTML tags
    text = re.sub(r'</?(b|strong)>', '*', text)
    text = re.sub(r'</?(i|em)>', '_', text)
    text = re.sub(r'</?(code|tt)>', '`', text)
    text = re.sub(r'<br\s*/?>', '\n', text)
    # Remove any other HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    return text


class WhatsAppTransport(BaseChannel):
    """WhatsApp-specific transport adapter utilizing Meta Cloud API."""

    def __init__(self, token: Optional[str] = None, phone_number_id: Optional[str] = None) -> None:
        config = get_config()
        # Fallback to config methods if not provided directly
        self.token = token or os.getenv("WHATSAPP_TOKEN") or config._env.get("WHATSAPP_TOKEN")
        self.phone_number_id = phone_number_id or os.getenv("WHATSAPP_PHONE_NUMBER_ID") or config._env.get("WHATSAPP_PHONE_NUMBER_ID")
        self.base_url = "https://graph.facebook.com/v18.0"
        self._client = httpx.Client(timeout=10.0)

    def _require_credentials(self) -> None:
        if not self.token or not self.phone_number_id:
            raise ValueError(
                "WhatsApp credentials missing. Please set WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID."
            )

    def send_message(
        self,
        chat_id: Any,
        text: str,
        *,
        parse_mode: Optional[str] = None,
        reply_to_message_id: Optional[int] = None,
        disable_web_page_preview: Optional[bool] = None,
    ) -> Any:
        """Send a WhatsApp message. Converts HTML to WhatsApp markdown by default."""
        self._require_credentials()
        clean_text = convert_html_to_whatsapp_markdown(text)
        
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": str(chat_id).replace("+", "").strip(),
            "type": "text",
            "text": {"body": clean_text},
        }

        try:
            response = self._client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info("WhatsApp message sent to %s successfully: %s", chat_id, response.json())
            return response.json()
        except Exception as e:
            logger.error("Failed to send WhatsApp message to %s: %s", chat_id, e)
            raise

    def send_template_message(
        self,
        chat_id: Any,
        template_name: str,
        language_code: str = "tr",
        components: Optional[list] = None,
    ) -> Any:
        """Send a pre-approved Meta WhatsApp Template message."""
        self._require_credentials()
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": str(chat_id).replace("+", "").strip(),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            }
        }
        if components:
            payload["template"]["components"] = components

        try:
            response = self._client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info("WhatsApp template %s sent to %s successfully: %s", template_name, chat_id, response.json())
            return response.json()
        except Exception as e:
            logger.error("Failed to send WhatsApp template %s to %s: %s", template_name, chat_id, e)
            raise

    def send_photo(
        self,
        chat_id: Any,
        photo: Any,
        *,
        caption: Optional[str] = None,
        reply_to_message_id: Optional[int] = None,
    ) -> Any:
        """Send a photo through WhatsApp using a media link or media ID."""
        self._require_credentials()
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": str(chat_id).replace("+", "").strip(),
            "type": "image",
            "image": {},
        }

        if str(photo).startswith("http"):
            payload["image"]["link"] = photo
        else:
            payload["image"]["id"] = str(photo)

        if caption:
            payload["image"]["caption"] = convert_html_to_whatsapp_markdown(caption)

        try:
            response = self._client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to send WhatsApp photo to %s: %s", chat_id, e)
            raise

    def reply(
        self,
        update: Any,
        text: str,
        *,
        parse_mode: Optional[str] = None,
        disable_web_page_preview: Optional[bool] = None,
    ) -> Any:
        """Reply to the active WhatsApp message using the sender's identifier."""
        chat_id = self.get_chat_id(update)
        if not chat_id:
            return None
        return self.send_message(chat_id, text)

    def get_chat_id(self, update: Any) -> Optional[Any]:
        """Extract the WhatsApp sender phone number from the update dict."""
        return self.parse_update(update).get("chat_id")

    def get_user_id(self, update: Any) -> Optional[Any]:
        """Extract the WhatsApp sender phone number as user id from the update."""
        return self.parse_update(update).get("user_id")

    def get_text(self, update: Any) -> Optional[str]:
        """Extract message text body from a WhatsApp update."""
        return self.parse_update(update).get("text")

    def get_message_type(self, update: Any) -> Optional[str]:
        """Return the coarse message type (e.g. text, image)."""
        return self.parse_update(update).get("message_type")

    def show_typing(self, chat_id: Any) -> Any:
        """Display a typing indicator. Meta API doesn't support generic typing for Cloud API directly."""
        pass

    def parse_update(self, update: Any) -> Dict[str, Any]:
        """Normalize a Meta Webhook payload into a transport-agnostic dict.
        
        Expects Meta Graph API webhook format.
        """
        if not isinstance(update, dict):
            return {}

        # Meta cloud API Webhook JSON structure
        entry_list = update.get("entry", [])
        if not entry_list:
            return update  # fallback if already normalized

        entry = entry_list[0]
        changes = entry.get("changes", [])
        if not changes:
            return {}

        value = changes[0].get("value", {})
        messages = value.get("messages", [])
        contacts = value.get("contacts", [])

        if not messages:
            return {}

        message = messages[0]
        sender_phone = message.get("from")
        msg_id = message.get("id")
        msg_type = message.get("type", "text")
        
        contact_name = "WhatsApp User"
        if contacts:
            contact_name = contacts[0].get("profile", {}).get("name", contact_name)

        text_body = ""
        if msg_type == "text":
            text_body = message.get("text", {}).get("body", "")
        elif msg_type == "interactive":
            interactive = message.get("interactive", {})
            int_type = interactive.get("type")
            if int_type == "button_reply":
                text_body = interactive.get("button_reply", {}).get("title", "")
            elif int_type == "list_reply":
                text_body = interactive.get("list_reply", {}).get("title", "")

        return {
            "chat_id": sender_phone,
            "user_id": sender_phone,
            "text": text_body,
            "message_type": msg_type,
            "message_id": msg_id,
            "username": sender_phone,
            "first_name": contact_name,
            "last_name": "",
            "raw_update": update,
        }


import os
