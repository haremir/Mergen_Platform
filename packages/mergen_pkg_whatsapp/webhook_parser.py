"""
mergen_pkg_whatsapp.webhook_parser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Meta WhatsApp Cloud API webhook security and payload normaliser.

Security Model
--------------
Every HTTP POST from Meta carries the header ``X-Hub-Signature-256: sha256=<hex>``.
The HMAC-SHA256 is computed over the **raw request body bytes** using the
``META_APP_SECRET`` as the HMAC key.

Layer 1  — ``verify_signature()`` validates this header with a constant-time
           comparison to prevent timing-oracle attacks.
Layer 2  — ``parse_webhook_payload()`` navigates Meta's nested JSON structure
           and extracts only the relevant message fields, discarding status
           events (delivered, read) silently.

Meta Webhook JSON Structure
---------------------------
::

    {
      "object": "whatsapp_business_account",
      "entry": [
        {
          "id": "<waba_id>",
          "changes": [
            {
              "value": {
                "messaging_product": "whatsapp",
                "metadata": {
                  "display_phone_number": "15550001234",
                  "phone_number_id": "109876543210123"        ← routing key
                },
                "contacts": [
                  { "profile": { "name": "Alice" }, "wa_id": "905551234567" }
                ],
                "messages": [
                  {
                    "from": "905551234567",                   ← sender E.164
                    "id": "wamid.xxxxx",
                    "timestamp": "1712345678",
                    "type": "text",
                    "text": { "body": "Hello!" }
                  }
                ]
              },
              "field": "messages"
            }
          ]
        }
      ]
    }

Author: Mergen Platform -- Core Team
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Import shared domain models
# ---------------------------------------------------------------------------
try:
    from mergen_common.models import InboundMessage
except ModuleNotFoundError:
    _shared = os.path.join(os.path.dirname(__file__), "..", "..", "shared")
    sys.path.insert(0, os.path.abspath(_shared))
    from mergen_common.models import InboundMessage  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

# Channel slug used in InboundMessage.channel
CHANNEL_SLUG = "whatsapp"


# ---------------------------------------------------------------------------
# Layer 1 — Signature Verification
# ---------------------------------------------------------------------------

def verify_signature(
    payload: bytes,
    signature_header: str,
    app_secret: str,
) -> bool:
    """Verify the ``X-Hub-Signature-256`` header sent by Meta.

    Meta computes::

        HMAC-SHA256(key=APP_SECRET_bytes, message=raw_body_bytes)

    and sends the result as ``sha256=<hex_digest>`` in the header.

    This function replicates the computation and uses ``hmac.compare_digest``
    for **constant-time comparison** to prevent timing-oracle attacks.

    Args:
        payload:          Raw, unmodified HTTP request body bytes.
                          Must be the bytes BEFORE any JSON parsing.
        signature_header: Value of the ``X-Hub-Signature-256`` header.
                          Expected format: ``"sha256=<64-char-hex-string>"``.
        app_secret:       Meta App Secret (``META_APP_SECRET`` env var).

    Returns:
        ``True``  — signature is valid; payload is authentic.
        ``False`` — signature is missing, malformed, or does not match.

    Security Notes:
        - Never return True when app_secret is empty (would pass any signature).
        - ``hmac.compare_digest`` prevents timing side-channels.
    """
    if not app_secret:
        logger.error(
            "verify_signature: app_secret is empty — rejecting all payloads "
            "until META_APP_SECRET is configured."
        )
        return False

    if not signature_header:
        logger.warning("verify_signature: X-Hub-Signature-256 header is missing.")
        return False

    if not signature_header.startswith("sha256="):
        logger.warning(
            "verify_signature: unexpected signature format '%s'.",
            signature_header[:20],
        )
        return False

    received_hex = signature_header[len("sha256="):]

    expected_hex = hmac.new(
        key=app_secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    valid = hmac.compare_digest(expected_hex, received_hex)

    if not valid:
        logger.warning(
            "verify_signature: SIGNATURE MISMATCH — possible replay or tampering. "
            "received='%.10s...' expected='%.10s...'",
            received_hex,
            expected_hex,
        )

    return valid


# ---------------------------------------------------------------------------
# Layer 2 — Payload Parsing
# ---------------------------------------------------------------------------

def parse_webhook_payload(payload: Dict[str, Any]) -> List[InboundMessage]:
    """Normalise a Meta WhatsApp webhook payload into a list of InboundMessages.

    Traversal path::

        payload["entry"][n]["changes"][m]["value"] -> {
            "metadata":  { "phone_number_id": ..., "display_phone_number": ... }
            "contacts":  [ { "profile": { "name": ... }, "wa_id": ... } ]
            "messages":  [ { "from": ..., "type": ..., "text": { "body": ... } } ]
            "statuses":  [ ... ]   ← silently ignored
        }

    Multi-entry / multi-change payloads are fully supported (uncommon but valid
    per Meta's spec).  Each ``messages[]`` item produces one ``InboundMessage``.

    Supported message types:
        - ``text``        → ``InboundMessage.text`` = body
        - ``interactive`` → extracts button_reply or list_reply title as text
        - ``image``, ``audio``, ``video``, ``document``, ``sticker`` →
          ``InboundMessage.text`` = empty string (caller must check type via
          raw_payload)
        - ``statuses``    → silently skipped (no InboundMessage emitted)

    The ``phone_number_id`` from ``metadata`` is stored as ``InboundMessage.tenant_id``
    so the TenantManager can resolve the owning Tenant in a subsequent step.

    Args:
        payload: Parsed Meta webhook JSON dict (already verified via
                 ``verify_signature``).

    Returns:
        List of ``InboundMessage`` objects.  Empty list when:
        - Payload contains only status events (delivered / read).
        - Payload does not match the expected Meta structure.
    """
    messages: List[InboundMessage] = []
    received_at = datetime.now(tz=timezone.utc)

    entries: List[Dict] = payload.get("entry", [])
    if not entries:
        logger.debug("parse_webhook_payload: no 'entry' key in payload — skipping.")
        return messages

    for entry in entries:
        changes: List[Dict] = entry.get("changes", [])
        for change in changes:
            if change.get("field") != "messages":
                logger.debug(
                    "parse_webhook_payload: skipping change with field='%s'.",
                    change.get("field"),
                )
                continue

            value: Dict = change.get("value", {})
            parsed = _parse_value_block(value, received_at)
            messages.extend(parsed)

    logger.info(
        "parse_webhook_payload: extracted %d message(s) from payload.",
        len(messages),
    )
    return messages


def _parse_value_block(
    value: Dict[str, Any],
    received_at: datetime,
) -> List[InboundMessage]:
    """Parse a single ``changes[n].value`` block into InboundMessages."""
    results: List[InboundMessage] = []

    # ── Extract routing key from metadata ────────────────────────────────
    metadata: Dict = value.get("metadata", {})
    phone_number_id: str = (
        metadata.get("phone_number_id")
        or metadata.get("display_phone_number")
        or ""
    )

    if not phone_number_id:
        logger.warning(
            "_parse_value_block: could not extract phone_number_id from metadata=%s — skipping.",
            metadata,
        )
        return results

    # ── Build a display-name lookup from contacts[] ───────────────────────
    contacts: List[Dict] = value.get("contacts", [])
    contact_map: Dict[str, str] = {}
    for contact in contacts:
        wa_id = contact.get("wa_id", "")
        name = contact.get("profile", {}).get("name", "")
        if wa_id:
            contact_map[wa_id] = name

    # ── Skip if no messages[] key (status-only event) ────────────────────
    raw_messages: List[Dict] = value.get("messages", [])
    if not raw_messages:
        # Check if this is a statuses-only event — log and move on
        if value.get("statuses"):
            logger.debug(
                "_parse_value_block: statuses-only event for phone_number_id=%s — ignored.",
                phone_number_id,
            )
        return results

    # ── Parse each message entry ──────────────────────────────────────────
    for msg in raw_messages:
        inbound = _normalise_message(
            msg=msg,
            phone_number_id=phone_number_id,
            contact_map=contact_map,
            raw_value=value,
            received_at=received_at,
        )
        if inbound is not None:
            results.append(inbound)

    return results


def _normalise_message(
    msg: Dict[str, Any],
    phone_number_id: str,
    contact_map: Dict[str, str],
    raw_value: Dict[str, Any],
    received_at: datetime,
) -> Optional[InboundMessage]:
    """Convert one raw Meta message dict into an InboundMessage.

    Returns ``None`` for unsupported / system message types.
    """
    sender: str = msg.get("from", "")
    if not sender:
        logger.debug("_normalise_message: 'from' field missing — skipping.")
        return None

    msg_type: str = msg.get("type", "text")

    # ── Extract text body by message type ────────────────────────────────
    text_body = _extract_text(msg, msg_type)

    # ── Timestamp (prefer Meta's server-side timestamp) ───────────────────
    ts_unix = msg.get("timestamp")
    if ts_unix:
        try:
            received_at = datetime.fromtimestamp(int(ts_unix), tz=timezone.utc)
        except (ValueError, OSError):
            pass  # Fall back to the time we received it

    inbound = InboundMessage(
        tenant_id=phone_number_id,   # Resolved to Tenant UUID by TenantManager
        channel=CHANNEL_SLUG,
        sender=sender,
        text=text_body,
        raw_payload={
            "message": msg,
            "metadata": raw_value.get("metadata", {}),
            "contact_name": contact_map.get(sender, ""),
        },
        received_at=received_at,
    )

    logger.debug(
        "_normalise_message: phone_id=%s from=%s type=%s text='%.60s'",
        phone_number_id,
        sender,
        msg_type,
        text_body,
    )
    return inbound


def _extract_text(msg: Dict[str, Any], msg_type: str) -> str:
    """Extract the human-readable text content from a message dict."""
    if msg_type == "text":
        return msg.get("text", {}).get("body", "")

    if msg_type == "interactive":
        interactive = msg.get("interactive", {})
        int_type = interactive.get("type", "")
        if int_type == "button_reply":
            return interactive.get("button_reply", {}).get("title", "")
        if int_type == "list_reply":
            return interactive.get("list_reply", {}).get("title", "")
        return ""

    if msg_type == "button":
        # Quick-reply button response
        return msg.get("button", {}).get("text", "")

    # Media types — return empty string; caller inspects raw_payload for media ID
    if msg_type in {"image", "audio", "video", "document", "sticker", "location"}:
        logger.debug("_extract_text: non-text message type='%s' — empty text.", msg_type)
        return ""

    logger.debug("_extract_text: unrecognised message type='%s'.", msg_type)
    return ""
