"""
verify_phase7_api.py
~~~~~~~~~~~~~~~~~~~~

Phase 7.1 verification script for the Mergen Panel FastAPI backend.

Uses FastAPI's built-in TestClient (backed by httpx) — no running server needed.
Injects mock RAG and WA dependencies to avoid loading sentence-transformers
(which takes 2-3 minutes on first run) during the API verification step.

Validates:
  1. Import sanity — FastAPI app and schemas load correctly.
  2. GET  /api/health   — liveness probe returns OK.
  3. POST /api/onboarding — happy path with valid payload (mocked deps).
  4. POST /api/onboarding — 422 validation error on missing required fields.
  5. POST /api/onboarding — 422 validation error on short field value.
  6. GET  /api/logs/{tenant_id} — returns mocked message log entries.
  7. GET  /api/plan/{tenant_id} — returns mocked plan + quota data.
  8. CORS origin config — http://localhost:3000 is in allowed origins.

Run from the repo root:
    uv run verify_phase7_api.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_ROOT = os.path.dirname(os.path.abspath(__file__))
for _p in (
    _ROOT,
    os.path.join(_ROOT, "shared"),
    os.path.join(_ROOT, "core"),
    os.path.join(_ROOT, "packages"),
    os.path.join(_ROOT, "products"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

logging.basicConfig(level=logging.WARNING, format="%(levelname)-8s  %(name)s -- %(message)s")

PASS = "[PASS]"
FAIL = "[FAIL]"

print()
print("=" * 60)
print(" Mergen Platform -- Phase 7.1 API Verification")
print("=" * 60)
print()

# ===========================================================================
# STEP 1 -- Import verification
# ===========================================================================
try:
    import panel.api_server as api_module
    from panel.api_server import app, set_test_overrides, clear_test_overrides, _all_origins
    from panel.schemas import (
        OnboardingRequest, OnboardingResponse,
        LogsResponse, PlanResponse, HealthResponse,
    )
    from fastapi.testclient import TestClient
    print(f"{PASS} All imports resolved successfully.")
    print(f"       panel.api_server  -- FastAPI app, override helpers OK")
    print(f"       panel.schemas     -- All Pydantic models OK")
except ImportError as exc:
    print(f"{FAIL} Import error: {exc}")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Inject mocks BEFORE creating TestClient to avoid sentence-transformer load
# ---------------------------------------------------------------------------
from mergen_core.tenant_manager import TenantManager as _TM
from mergen_pkg_whatsapp.client import WhatsAppAPIError

_mock_wa = MagicMock()
_mock_wa.add_phone_number.return_value = "MOCK_PHONE_ID_TEST001"

_mock_rag = MagicMock()
_mock_rag.ingest_fields.return_value = 7   # simulate 7 fields indexed

_mock_tm = _TM()  # lightweight in-memory tenant manager

set_test_overrides(
    wa_client=_mock_wa,
    rag_engine=_mock_rag,
    tenant_manager=_mock_tm,
)

client = TestClient(app, raise_server_exceptions=True)

# ===========================================================================
# STEP 2 -- GET /api/health
# ===========================================================================
print()
print("--- Step 2: GET /api/health ---")

resp = client.get("/api/health")
assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
data = resp.json()
assert data["status"] == "ok"
assert data["service"] == "Mergen Panel API"
print(f"{PASS} GET /api/health -> 200 OK")
print(f"       status='{data['status']}' version='{data['version']}' service='{data['service']}'")

# ===========================================================================
# STEP 3 -- POST /api/onboarding: happy path
# ===========================================================================
print()
print("--- Step 3: POST /api/onboarding -- Happy Path (mocked deps) ---")

VALID_PAYLOAD = {
    "business_name":      "Acme Barber Istanbul",
    "phone_number":       "+905550001234",
    "business_hours":     {"monday": "09:00-19:00", "tuesday": "09:00-19:00"},
    "location":           "Kadikoy Mah. Ataturk Cad. No:12, Kadikoy/Istanbul",
    "cancellation_policy":"24 hours advance notice required for cancellations.",
    "contact_info":       "reception@acme.com | +90 212 555 0000",
    "services":           [{"name": "Haircut", "price": "150 TL", "description": "Classic hair cut"}],
    "faqs":               [{"question": "Randevu iptal edilebilir mi?", "answer": "Evet, 24 saat kalana kadar."}],
    "pricing":            "Haircut: 150 TL, Beard trim: 80 TL",
    "plan":               "starter",
}

resp = client.post("/api/onboarding", json=VALID_PAYLOAD)
print(f"       HTTP Status: {resp.status_code}")
assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
data = resp.json()

print()
print("       Response JSON:")
print("       " + "-" * 52)
for k, v in data.items():
    print(f"       {k:<30} = {v}")
print("       " + "-" * 52)

assert data["status"] == "pending_verification", f"Expected pending_verification, got {data['status']}"
assert len(data["tenant_id"]) == 36, "tenant_id should be a UUID-4 string"
assert data["phone_number_id"] == "MOCK_PHONE_ID_TEST001"
assert data["knowledge_fields_ingested"] == 7  # mock returns 7
assert data["persona"] == "desk_receptionist"
assert data["error"] is None

print(f"{PASS} POST /api/onboarding -> 201 Created")
print(f"{PASS} status = 'pending_verification'")
print(f"{PASS} tenant_id (UUID) = {data['tenant_id']}")
print(f"{PASS} phone_number_id  = {data['phone_number_id']}")
print(f"{PASS} knowledge_fields_ingested = {data['knowledge_fields_ingested']} (mock)")
print(f"{PASS} persona = '{data['persona']}'")

# Verify mocks were called
_mock_wa.add_phone_number.assert_called_once_with(
    phone_number="+905550001234",
    display_name="Acme Barber Istanbul",
)
print(f"{PASS} WhatsApp add_phone_number called with correct args.")
_mock_rag.ingest_fields.assert_called_once()
print(f"{PASS} RAG ingest_fields called once.")

# ===========================================================================
# STEP 4 -- POST /api/onboarding: missing required fields (422)
# ===========================================================================
print()
print("--- Step 4: POST /api/onboarding -- Missing Fields (422) ---")

MISSING_PAYLOAD = {
    "business_name":  "Incomplete Corp",
    "phone_number":   "+905559999999",
    # business_hours, location, cancellation_policy, contact_info, services MISSING
}

resp = client.post("/api/onboarding", json=MISSING_PAYLOAD)
assert resp.status_code == 422, f"Expected 422 Unprocessable Entity, got {resp.status_code}"
err = resp.json()
missing_fields_reported = [e["loc"][-1] for e in err.get("detail", [])]
print(f"{PASS} POST /api/onboarding with missing fields -> 422 Unprocessable Entity")
print(f"       Missing fields caught by Pydantic: {missing_fields_reported}")
assert "business_hours" in missing_fields_reported
assert "location" in missing_fields_reported
assert "cancellation_policy" in missing_fields_reported
assert "contact_info" in missing_fields_reported
assert "services" in missing_fields_reported
print(f"{PASS} All 5 missing required fields correctly reported in 422 response.")

# ===========================================================================
# STEP 5 -- POST /api/onboarding: short field value (422)
# ===========================================================================
print()
print("--- Step 5: POST /api/onboarding -- Short Field Value (422) ---")

SHORT_PAYLOAD = dict(VALID_PAYLOAD)
SHORT_PAYLOAD["business_name"] = "X"   # min_length=2
resp = client.post("/api/onboarding", json=SHORT_PAYLOAD)
assert resp.status_code == 422, f"Expected 422 for short business_name, got {resp.status_code}"
print(f"{PASS} POST /api/onboarding with business_name='X' -> 422 (min_length=2 violated)")

# ===========================================================================
# STEP 6 -- GET /api/logs/{tenant_id}
# ===========================================================================
print()
print("--- Step 6: GET /api/logs/{tenant_id} ---")

FAKE_TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
resp = client.get(f"/api/logs/{FAKE_TENANT}")
assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
data = resp.json()
assert data["tenant_id"] == FAKE_TENANT
assert isinstance(data["messages"], list)
assert data["total"] > 0

print(f"{PASS} GET /api/logs/{FAKE_TENANT[:8]}... -> 200 OK")
print(f"       total={data['total']} message(s) returned")
print()
print("       Sample log entries:")
for msg in data["messages"][:3]:
    direction_icon = "<<" if msg["direction"] == "inbound" else ">>"
    print(f"       {direction_icon} [{msg['channel']}] {msg['sender']}: '{msg['text'][:55]}'")

first = data["messages"][0]
assert all(k in first for k in ["message_id", "tenant_id", "sender", "channel", "direction", "text", "timestamp"])
print(f"{PASS} Log entry schema validated (all required keys present).")

# ===========================================================================
# STEP 7 -- GET /api/plan/{tenant_id}
# ===========================================================================
print()
print("--- Step 7: GET /api/plan/{tenant_id} ---")

resp = client.get(f"/api/plan/{FAKE_TENANT}")
assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
data = resp.json()
assert data["tenant_id"] == FAKE_TENANT
assert data["plan"] == "starter"
assert "monthly_messages" in data["limits"]
assert "rag_documents" in data["limits"]
assert "whatsapp_numbers" in data["limits"]

mm = data["limits"]["monthly_messages"]
assert mm["limit"] == 500
assert mm["unit"] == "messages/month"
assert mm["remaining"] == mm["limit"] - mm["used"]

print(f"{PASS} GET /api/plan/{FAKE_TENANT[:8]}... -> 200 OK")
print(f"       plan='{data['plan']}'")
print(f"       monthly_messages: limit={mm['limit']} used={mm['used']} remaining={mm['remaining']}")
print(f"       rag_documents:    limit={data['limits']['rag_documents']['limit']}")
print(f"       whatsapp_numbers: limit={data['limits']['whatsapp_numbers']['limit']}")
print(f"{PASS} Plan limits schema validated.")

# ===========================================================================
# STEP 8 -- CORS configuration check
# ===========================================================================
print()
print("--- Step 8: CORS configuration ---")

print(f"       Configured CORS origins: {_all_origins}")
assert "http://localhost:3000" in _all_origins, "localhost:3000 must be in CORS origins"
assert "http://127.0.0.1:3000" in _all_origins, "127.0.0.1:3000 must be in CORS origins"
print(f"{PASS} CORS: http://localhost:3000 (Next.js dev server) is allowed.")
print(f"{PASS} CORS: http://127.0.0.1:3000 is allowed.")

# ===========================================================================
# STEP 9 -- Settings configuration check
# ===========================================================================
print()
print("--- Step 9: POST /api/tenant/{tenant_id}/settings ---")

settings_payload = {
    "bot_active": False,
    "system_prompt_override": "Yeni deneme sistem promptu"
}
resp = client.post(f"/api/tenant/{FAKE_TENANT}/settings", json=settings_payload)
assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
settings_data = resp.json()
assert settings_data["status"] == "success"
assert settings_data["bot_active"] is False
assert settings_data["system_prompt_override"] == "Yeni deneme sistem promptu"
print(f"{PASS} POST /api/tenant/.../settings -> 200 OK")
print(f"       message='{settings_data['message']}'")

# ===========================================================================
# Cleanup
# ===========================================================================
clear_test_overrides()

# ===========================================================================
# Summary
# ===========================================================================
print()
print("=" * 60)
print(" All Phase 7.3 backend checks completed successfully.")
print("=" * 60)
print()
print(" Start the API server with:")
print("   uv run uvicorn panel.api_server:app --reload --port 8000")
print(" Then open http://localhost:8000/docs for interactive Swagger UI.")
print()
