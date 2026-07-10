# mergen_pkg_whatsapp — WhatsApp Cloud API channel adapter for the Mergen Platform.
# Handles webhook verification, signature validation, message parsing,
# and outbound message/template delivery via Meta Graph API.

from mergen_pkg_whatsapp.client import WhatsAppClient, WhatsAppAPIError
from mergen_pkg_whatsapp.webhook_parser import (
    verify_signature,
    parse_webhook_payload,
    CHANNEL_SLUG,
)

__all__ = [
    # Client
    "WhatsAppClient",
    "WhatsAppAPIError",
    # Webhook Parser
    "verify_signature",
    "parse_webhook_payload",
    "CHANNEL_SLUG",
]
