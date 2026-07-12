"""
verify_phase5.py
~~~~~~~~~~~~~~~~

Phase 5 verification for the Mergen Platform WhatsApp package.

Validates:
  1. Import sanity — all Phase 5 modules load correctly.
  2. WhatsAppClient — constructor validation, URL construction, mock send_message.
  3. verify_signature — valid and invalid HMAC-SHA256 cases.
  4. parse_webhook_payload — text message, interactive button, status-only,
     multi-entry, media-only (empty text), malformed payload.

Run from the repo root:
    uv run verify_phase5.py
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_TESTS_DIR)
sys.path.insert(0, os.path.join(_ROOT, "shared"))
sys.path.insert(0, os.path.join(_ROOT, "core"))
sys.path.insert(0, os.path.join(_ROOT, "packages"))

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)-8s  %(name)s -- %(message)s",
)

PASS = "[PASS]"
FAIL = "[FAIL]"

print()
print("=" * 60)
print(" Mergen Platform -- Phase 5 Verification")
print("=" * 60)
print()

# ===========================================================================
# STEP 1 -- Import verification
# ===========================================================================
try:
    from mergen_common.models import InboundMessage, OutboundMessage
    from mergen_pkg_whatsapp.client import WhatsAppClient, WhatsAppAPIError
    from mergen_pkg_whatsapp.webhook_parser import (
        verify_signature,
        parse_webhook_payload,
        CHANNEL_SLUG,
    )
    print(f"{PASS} All imports resolved successfully.")
    print(f"       InboundMessage, OutboundMessage     -- OK")
    print(f"       mergen_pkg_whatsapp.client          -- WhatsAppClient OK")
    print(f"       mergen_pkg_whatsapp.webhook_parser  -- verify_signature, parse_webhook_payload OK")
except ImportError as exc:
    print(f"{FAIL} Import error: {exc}")
    sys.exit(1)

# ===========================================================================
# STEP 2 -- WhatsAppClient
# ===========================================================================
print()
print("--- Step 2: WhatsAppClient (mocked HTTP) ---")

APP_SECRET = "test_app_secret_12345"
WABA_ID    = "987654321098765"
PHONE_ID   = "109876543210123"
TOKEN      = "mock_platform_token_abc"

# -- Constructor validation --
try:
    WhatsAppClient(platform_token="", waba_id=WABA_ID)
    print(f"{FAIL} Expected ValueError for empty platform_token.")
    sys.exit(1)
except ValueError:
    print(f"{PASS} ValueError correctly raised for empty platform_token.")

try:
    WhatsAppClient(platform_token=TOKEN, waba_id="")
    print(f"{FAIL} Expected ValueError for empty waba_id.")
    sys.exit(1)
except ValueError:
    print(f"{PASS} ValueError correctly raised for empty waba_id.")

# -- Mock httpx.Client to intercept actual HTTP calls --
import httpx

def _make_mock_response(body: dict, status: int = 200) -> MagicMock:
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = status
    mock_resp.json.return_value = body
    mock_resp.text = json.dumps(body)
    mock_resp.raise_for_status = MagicMock()
    return mock_resp

mock_http = MagicMock(spec=httpx.Client)
client = WhatsAppClient(platform_token=TOKEN, waba_id=WABA_ID, http_client=mock_http)
print(f"{PASS} WhatsAppClient instantiated (mock HTTP backend).")

# add_phone_number
mock_http.post.return_value = _make_mock_response({"id": PHONE_ID})
returned_id = client.add_phone_number("+905551234567", "Acme Support")
assert returned_id == PHONE_ID
call_url = mock_http.post.call_args[0][0]
assert f"/{WABA_ID}/phone_numbers" in call_url
print(f"{PASS} add_phone_number -- URL correct: ...{call_url.split('facebook.com')[1]}")
print(f"       Returned phone_number_id: {returned_id}")

# request_verification_code
mock_http.post.return_value = _make_mock_response({"success": True})
ok = client.request_verification_code(PHONE_ID, code_method="SMS", language="tr_TR")
assert ok is True
call_url = mock_http.post.call_args[0][0]
assert f"/{PHONE_ID}/request_code" in call_url
print(f"{PASS} request_verification_code -- URL correct: ...{call_url.split('facebook.com')[1]}")

# verify_code
mock_http.post.return_value = _make_mock_response({"success": True})
ok = client.verify_code(PHONE_ID, "123456")
assert ok is True
call_url = mock_http.post.call_args[0][0]
assert f"/{PHONE_ID}/verify_code" in call_url
print(f"{PASS} verify_code -- URL correct: ...{call_url.split('facebook.com')[1]}")

# register_number
mock_http.post.return_value = _make_mock_response({"success": True})
ok = client.register_number(PHONE_ID, pin="000000")
assert ok is True
call_url = mock_http.post.call_args[0][0]
assert f"/{PHONE_ID}/register" in call_url
print(f"{PASS} register_number -- URL correct: ...{call_url.split('facebook.com')[1]}")

# send_message (text)
outbound = OutboundMessage(
    tenant_id="tenant-abc",
    channel="whatsapp",
    recipient="+905551234567",
    text="Hello from Mergen Platform!",
)
mock_http.post.return_value = _make_mock_response(
    {"messages": [{"id": "wamid.testid123"}]}
)
result = client.send_message(outbound, PHONE_ID)
assert result["messages"][0]["id"] == "wamid.testid123"
call_url = mock_http.post.call_args[0][0]
call_payload = mock_http.post.call_args[1]["json"]
assert f"/{PHONE_ID}/messages" in call_url
assert call_payload["type"] == "text"
assert "Hello from Mergen Platform!" in call_payload["text"]["body"]
assert call_payload["to"] == "905551234567"   # + stripped
print(f"{PASS} send_message (text) -- URL correct: ...{call_url.split('facebook.com')[1]}")
print(f"       Payload type='{call_payload['type']}' to='{call_payload['to']}'")
print(f"       API response msg_id: {result['messages'][0]['id']}")

# send_message (template)
outbound_tmpl = OutboundMessage(
    tenant_id="tenant-abc",
    channel="whatsapp",
    recipient="905559876543",
    text="",
    template_name="order_confirmation_v1",
)
mock_http.post.return_value = _make_mock_response({"messages": [{"id": "wamid.tmpl999"}]})
result_tmpl = client.send_message(outbound_tmpl, PHONE_ID)
tmpl_payload = mock_http.post.call_args[1]["json"]
assert tmpl_payload["type"] == "template"
assert tmpl_payload["template"]["name"] == "order_confirmation_v1"
print(f"{PASS} send_message (template) -- template_name='{tmpl_payload['template']['name']}'")

# ===========================================================================
# STEP 3 -- verify_signature
# ===========================================================================
print()
print("--- Step 3: verify_signature (HMAC-SHA256) ---")

body_bytes = b'{"object":"whatsapp_business_account","entry":[]}'

# Compute a valid signature
valid_hex = hmac.new(
    key=APP_SECRET.encode("utf-8"),
    msg=body_bytes,
    digestmod=hashlib.sha256,
).hexdigest()
valid_header = f"sha256={valid_hex}"

result = verify_signature(body_bytes, valid_header, APP_SECRET)
assert result is True
print(f"{PASS} verify_signature -- valid HMAC signature accepted.")
print(f"       Header: sha256={valid_hex[:16]}...")

# Wrong signature
result = verify_signature(body_bytes, "sha256=deadbeef0000000000000000000000000000000000000000000000000000000", APP_SECRET)
assert result is False
print(f"{PASS} verify_signature -- tampered signature correctly rejected.")

# Missing header
result = verify_signature(body_bytes, "", APP_SECRET)
assert result is False
print(f"{PASS} verify_signature -- missing header correctly rejected.")

# Bad format (no sha256= prefix)
result = verify_signature(body_bytes, valid_hex, APP_SECRET)
assert result is False
print(f"{PASS} verify_signature -- malformed header (no prefix) correctly rejected.")

# Empty secret
result = verify_signature(body_bytes, valid_header, "")
assert result is False
print(f"{PASS} verify_signature -- empty app_secret correctly rejected (security guard).")

# ===========================================================================
# STEP 4 -- parse_webhook_payload
# ===========================================================================
print()
print("--- Step 4: parse_webhook_payload ---")

# ── 4a: Standard text message ─────────────────────────────────────────────
text_payload = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "123456789",
            "changes": [
                {
                    "field": "messages",
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15550001234",
                            "phone_number_id": PHONE_ID,
                        },
                        "contacts": [
                            {
                                "profile": {"name": "Alice Yilmaz"},
                                "wa_id": "905551234567",
                            }
                        ],
                        "messages": [
                            {
                                "from": "905551234567",
                                "id": "wamid.abc001",
                                "timestamp": "1712345678",
                                "type": "text",
                                "text": {"body": "Musteri temsilcisiyle gorusmek istiyorum."},
                            }
                        ],
                    },
                }
            ],
        }
    ],
}

msgs = parse_webhook_payload(text_payload)
assert len(msgs) == 1
m = msgs[0]
assert isinstance(m, InboundMessage)
assert m.tenant_id == PHONE_ID
assert m.channel == "whatsapp"
assert m.sender == "905551234567"
assert m.text == "Musteri temsilcisiyle gorusmek istiyorum."
assert m.raw_payload["contact_name"] == "Alice Yilmaz"
print(f"{PASS} Text message parsed correctly.")
print(f"       tenant_id (phone_number_id): {m.tenant_id}")
print(f"       sender:                      {m.sender}")
print(f"       channel:                     {m.channel}")
print(f"       text:                        '{m.text}'")
print(f"       contact_name:                {m.raw_payload['contact_name']}")
print(f"       received_at:                 {m.received_at.isoformat()}")

# ── 4b: Interactive button_reply ──────────────────────────────────────────
interactive_payload = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "123456789",
            "changes": [
                {
                    "field": "messages",
                    "value": {
                        "metadata": {"phone_number_id": PHONE_ID, "display_phone_number": "15550001234"},
                        "contacts": [],
                        "messages": [
                            {
                                "from": "905559876543",
                                "id": "wamid.abc002",
                                "timestamp": "1712345900",
                                "type": "interactive",
                                "interactive": {
                                    "type": "button_reply",
                                    "button_reply": {"id": "btn1", "title": "Confirm Appointment"},
                                },
                            }
                        ],
                    },
                }
            ],
        }
    ],
}
msgs = parse_webhook_payload(interactive_payload)
assert len(msgs) == 1
assert msgs[0].text == "Confirm Appointment"
assert msgs[0].sender == "905559876543"
print(f"{PASS} Interactive button_reply parsed correctly. text='{msgs[0].text}'")

# ── 4c: Status-only event (delivered/read) — must be silently ignored ─────
status_payload = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "123456789",
            "changes": [
                {
                    "field": "messages",
                    "value": {
                        "metadata": {"phone_number_id": PHONE_ID, "display_phone_number": "15550001234"},
                        "statuses": [
                            {
                                "id": "wamid.abc003",
                                "status": "delivered",
                                "timestamp": "1712346000",
                                "recipient_id": "905551234567",
                            }
                        ],
                    },
                }
            ],
        }
    ],
}
msgs = parse_webhook_payload(status_payload)
assert len(msgs) == 0
print(f"{PASS} Status-only event (delivered) correctly produced 0 InboundMessages.")

# ── 4d: Multi-entry payload ───────────────────────────────────────────────
multi_entry_payload = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "111",
            "changes": [{"field": "messages", "value": {
                "metadata": {"phone_number_id": "PHONE_A", "display_phone_number": "111"},
                "contacts": [],
                "messages": [{"from": "1111", "id": "wamid.A", "timestamp": "1712345000", "type": "text", "text": {"body": "Message A"}}],
            }}],
        },
        {
            "id": "222",
            "changes": [{"field": "messages", "value": {
                "metadata": {"phone_number_id": "PHONE_B", "display_phone_number": "222"},
                "contacts": [],
                "messages": [{"from": "2222", "id": "wamid.B", "timestamp": "1712345001", "type": "text", "text": {"body": "Message B"}}],
            }}],
        },
    ],
}
msgs = parse_webhook_payload(multi_entry_payload)
assert len(msgs) == 2
assert msgs[0].text == "Message A"
assert msgs[0].tenant_id == "PHONE_A"
assert msgs[1].text == "Message B"
assert msgs[1].tenant_id == "PHONE_B"
print(f"{PASS} Multi-entry payload produced {len(msgs)} InboundMessages correctly.")

# ── 4e: Media message (image) — text must be empty string ─────────────────
image_payload = {
    "object": "whatsapp_business_account",
    "entry": [{"id": "999", "changes": [{"field": "messages", "value": {
        "metadata": {"phone_number_id": PHONE_ID, "display_phone_number": "15550001234"},
        "contacts": [],
        "messages": [{"from": "905551234567", "id": "wamid.img01", "timestamp": "1712346000",
                       "type": "image", "image": {"id": "img_media_id_xyz", "mime_type": "image/jpeg"}}],
    }}]}],
}
msgs = parse_webhook_payload(image_payload)
assert len(msgs) == 1
assert msgs[0].text == ""
assert msgs[0].raw_payload["message"]["type"] == "image"
print(f"{PASS} Image media message parsed: text='' (empty), raw_payload has media info.")

# ── 4f: Malformed payload (empty dict) ────────────────────────────────────
msgs = parse_webhook_payload({})
assert msgs == []
print(f"{PASS} Malformed/empty payload returns empty list safely.")

# ===========================================================================
# Summary
# ===========================================================================
print()
print("=" * 60)
print(" All Phase 5 checks completed successfully.")
print("=" * 60)
print()
