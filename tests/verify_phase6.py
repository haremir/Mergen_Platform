"""
verify_phase6.py
~~~~~~~~~~~~~~~~

Phase 6 verification script for the Mergen Platform Desk product.

Validates:
  1. Import sanity — all Phase 6 modules load without errors.
  2. desk_persona.py — persona dict schema and handoff trigger list.
  3. DeskTemplateValidator — successful conversion with full form data.
  4. DeskTemplateValidator — DeskValidationError on missing required fields.
  5. DeskTemplateValidator — optional fields and faq_* fields included.
  6. DeskOnboardingService — full happy path with mocked WhatsApp and RAG.
  7. DeskOnboardingService — validation_error abort path.
  8. DeskOnboardingService — whatsapp_error abort path.

Run from the repo root:
    uv run verify_phase6.py
"""

from __future__ import annotations

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
for _p in (
    os.path.join(_ROOT, "shared"),
    os.path.join(_ROOT, "core"),
    os.path.join(_ROOT, "packages"),
    os.path.join(_ROOT, "products"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)-8s  %(name)s -- %(message)s",
)

PASS = "[PASS]"
FAIL = "[FAIL]"

print()
print("=" * 60)
print(" Mergen Platform -- Phase 6 Verification")
print("=" * 60)
print()

# ===========================================================================
# STEP 1 -- Import verification
# ===========================================================================
try:
    from mergen_common.models import Tenant, KnowledgeField
    from mergen_product_desk.desk_persona import DESK_PERSONA, DESK_HANDOFF_TRIGGERS
    from mergen_product_desk.knowledge_template import (
        DeskTemplateValidator,
        DeskValidationError,
        REQUIRED_FIELDS,
        OPTIONAL_FIELDS,
    )
    from mergen_product_desk.onboarding_orchestrator import DeskOnboardingService
    print(f"{PASS} All imports resolved successfully.")
    print(f"       DESK_PERSONA, DESK_HANDOFF_TRIGGERS  -- OK")
    print(f"       DeskTemplateValidator, DeskValidationError -- OK")
    print(f"       DeskOnboardingService                -- OK")
except ImportError as exc:
    print(f"{FAIL} Import error: {exc}")
    sys.exit(1)

# ===========================================================================
# STEP 2 -- desk_persona.py
# ===========================================================================
print()
print("--- Step 2: desk_persona.py ---")

required_persona_keys = {"name", "tone", "system_prompt", "boundaries", "language"}
missing_keys = required_persona_keys - set(DESK_PERSONA.keys())
if missing_keys:
    print(f"{FAIL} DESK_PERSONA missing keys: {missing_keys}")
    sys.exit(1)
print(f"{PASS} DESK_PERSONA schema valid.")
print(f"       name:     {DESK_PERSONA['name']}")
print(f"       tone:     {DESK_PERSONA['tone']}")
print(f"       language: {DESK_PERSONA['language']}")
print(f"       boundaries: {len(DESK_PERSONA['boundaries'])} rule(s)")
print(f"       system_prompt: {len(DESK_PERSONA['system_prompt'])} chars")

assert len(DESK_HANDOFF_TRIGGERS) >= 10, "Expected at least 10 Desk handoff triggers"
print(f"{PASS} DESK_HANDOFF_TRIGGERS: {len(DESK_HANDOFF_TRIGGERS)} trigger signal(s) defined.")

# Spot-check a few key triggers
trigger_labels = [label for _, label in DESK_HANDOFF_TRIGGERS]
assert "desk:randevu_iptali" in trigger_labels, "Missing desk:randevu_iptali"
assert "desk:yetkili" in trigger_labels,         "Missing desk:yetkili"
assert "desk:fiyat_itiraz" in trigger_labels,    "Missing desk:fiyat_itiraz"
assert "desk:cancel_appointment" in trigger_labels, "Missing desk:cancel_appointment"
print(f"{PASS} Key triggers present: randevu_iptali, yetkili, fiyat_itiraz, cancel_appointment.")

# ===========================================================================
# STEP 3 -- DeskTemplateValidator: successful conversion
# ===========================================================================
print()
print("--- Step 3: DeskTemplateValidator -- Successful Validation ---")

TENANT_ID = "desk-verify-tenant-001"

full_form = {
    "business_hours":      "Mon-Fri 09:00-19:00, Sat 10:00-17:00",
    "location":            "Bagcilar Mah. Ataturk Cad. No:12, Kadikoy/Istanbul",
    "contact_info":        "reception@acmebarber.com | +90 212 555 0000",
    "cancellation_policy": "Iptal icin en az 24 saat oncesinden haber verilmelidir.",
    "services":            "Sac kesimi, Sakal tiras, Renklendirme, Bakim paketleri",
    # Optional fields
    "pricing":             "Sac kesimi: 150 TL, Sakal tiras: 80 TL, Renklendirme: 300 TL+",
    "social_media":        "@acmebarber_istanbul",
    "languages_spoken":    "Turkce, Ingilizce",
    # FAQ entries
    "faq_parking":         "S: Park yeri var mi? C: Evet, binamizin onunde ucretsiz park yeri mevcuttur.",
    "faq_cards":           "S: Kredi karti kabul ediyor musunuz? C: Evet, tum kartlari kabul ederiz.",
}

try:
    validator = DeskTemplateValidator()
    fields = validator.validate_and_convert(TENANT_ID, full_form)

    assert isinstance(fields, list), "Expected list"
    assert all(isinstance(f, KnowledgeField) for f in fields), "Expected KnowledgeField instances"
    assert len(fields) >= len(REQUIRED_FIELDS), "Must have at least all required fields"

    print(f"{PASS} validate_and_convert returned {len(fields)} KnowledgeField(s).")
    print()
    print("       Generated KnowledgeFields:")
    print("       " + "-" * 52)
    for kf in fields:
        print(f"       field_type={kf.field_type:<14} | value={kf.value[:55]}...")
    print("       " + "-" * 52)

    # Verify field types
    field_types = {kf.field_type for kf in fields}
    assert "policy"  in field_types, "Missing policy type"
    assert "contact" in field_types, "Missing contact type"
    assert "product" in field_types, "Missing product type"
    assert "faq"     in field_types, "Missing faq type"
    print(f"{PASS} All expected field_types present: {sorted(field_types)}")

    # Verify FAQ entries made it in
    faq_fields = [kf for kf in fields if kf.field_type == "faq"]
    assert len(faq_fields) == 2, f"Expected 2 FAQ fields, got {len(faq_fields)}"
    print(f"{PASS} {len(faq_fields)} FAQ field(s) correctly included (faq_parking, faq_cards).")

    # Verify required field content
    hours_field = next(kf for kf in fields if "[business_hours]" in kf.value)
    assert "Mon-Fri" in hours_field.value
    print(f"{PASS} Required field 'business_hours' content preserved correctly.")

except DeskValidationError as exc:
    print(f"{FAIL} Unexpected validation error: {exc}")
    sys.exit(1)
except Exception as exc:
    print(f"{FAIL} Unexpected error: {exc}")
    sys.exit(1)

# ===========================================================================
# STEP 4 -- DeskTemplateValidator: missing required fields
# ===========================================================================
print()
print("--- Step 4: DeskTemplateValidator -- Validation Failure Cases ---")

# Completely empty form
try:
    validator.validate_and_convert(TENANT_ID, {})
    print(f"{FAIL} Expected DeskValidationError for empty form.")
    sys.exit(1)
except DeskValidationError as exc:
    assert set(exc.missing_fields) == set(REQUIRED_FIELDS)
    print(f"{PASS} Empty form raises DeskValidationError with all required fields listed.")
    print(f"       missing_fields: {exc.missing_fields}")

# Partial form — missing 'cancellation_policy' and 'services'
partial_form = {
    "business_hours": "Mon-Fri 09:00-18:00",
    "location":       "Istanbul",
    "contact_info":   "test@test.com",
    # cancellation_policy MISSING
    # services MISSING
}
try:
    validator.validate_and_convert(TENANT_ID, partial_form)
    print(f"{FAIL} Expected DeskValidationError for partial form.")
    sys.exit(1)
except DeskValidationError as exc:
    assert "cancellation_policy" in exc.missing_fields
    assert "services" in exc.missing_fields
    print(f"{PASS} Partial form raises DeskValidationError for: {exc.missing_fields}")

# validate_only (no conversion)
try:
    validator.validate_only({})
    print(f"{FAIL} Expected DeskValidationError from validate_only.")
    sys.exit(1)
except DeskValidationError:
    print(f"{PASS} validate_only() correctly raises DeskValidationError.")

# ===========================================================================
# STEP 5 -- DeskOnboardingService: happy path (mocked WhatsApp + RAG)
# ===========================================================================
print()
print("--- Step 5: DeskOnboardingService -- Happy Path ---")

# Mock WhatsAppClient
mock_wa = MagicMock()
mock_wa.add_phone_number.return_value = "META_PHONE_ID_999"

# Mock RagEngine
mock_rag = MagicMock()
mock_rag.ingest_fields.return_value = 10   # returns count of indexed fields

# Mock TenantManager (use real one for create/get)
from mergen_core.tenant_manager import TenantManager
mock_tm = TenantManager()

service = DeskOnboardingService(
    whatsapp_client=mock_wa,
    tenant_manager=mock_tm,
    rag_engine=mock_rag,
)
print(f"{PASS} DeskOnboardingService instantiated with mocked WA and RAG.")

result = service.setup_new_client(
    tenant_id=TENANT_ID,
    business_name="Acme Barber Istanbul",
    raw_form_data=full_form,
    phone_number="+905550001234",
)

print()
print("       setup_new_client result:")
print("       " + "-" * 52)
for k, v in result.items():
    if k not in ("error",):
        print(f"       {k:<30} = {v}")
print("       " + "-" * 52)

assert result["status"] == "pending_verification", f"Expected pending_verification, got {result['status']}"
assert result["phone_number_id"] == "META_PHONE_ID_999"
assert result["knowledge_fields_ingested"] == len(fields)   # Same as Step 3
assert result["tenant_id"] == TENANT_ID
assert result["persona"] == "desk_receptionist"

print(f"{PASS} status = 'pending_verification'")
print(f"{PASS} phone_number_id = '{result['phone_number_id']}'")
print(f"{PASS} knowledge_fields_ingested = {result['knowledge_fields_ingested']}")
print(f"{PASS} persona = '{result['persona']}'")

# Verify add_phone_number was called with correct args
mock_wa.add_phone_number.assert_called_once_with(
    phone_number="+905550001234",
    display_name="Acme Barber Istanbul",
)
print(f"{PASS} WhatsApp add_phone_number called with correct phone_number and display_name.")

# Verify RAG was called
mock_rag.ingest_fields.assert_called_once()
rag_call_fields = mock_rag.ingest_fields.call_args[0][1]   # positional arg 1 = fields
assert len(rag_call_fields) == len(fields)
print(f"{PASS} RAG index_knowledge_fields called with {len(rag_call_fields)} field(s).")

# Verify tenant was actually stored in TenantManager
stored_tenant = mock_tm.get_tenant_by_id(TENANT_ID)
assert stored_tenant.business_name == "Acme Barber Istanbul"
assert stored_tenant.sector == "desk"
print(f"{PASS} Tenant stored in TenantManager: name='{stored_tenant.business_name}' sector='{stored_tenant.sector}'")

# ===========================================================================
# STEP 6 -- DeskOnboardingService: validation_error path
# ===========================================================================
print()
print("--- Step 6: DeskOnboardingService -- Validation Error Path ---")

bad_form = {"business_hours": "Mon-Fri 09:00-18:00"}   # Missing 4 required fields

result_bad = service.setup_new_client(
    tenant_id="desk-bad-tenant-001",
    business_name="Bad Config Corp",
    raw_form_data=bad_form,
    phone_number="+905559999999",
)
assert result_bad["status"] == "validation_error"
assert "missing_fields" in result_bad
assert "location" in result_bad["missing_fields"]
print(f"{PASS} validation_error correctly returned for incomplete form.")
print(f"       missing_fields: {result_bad['missing_fields']}")
print(f"       WhatsApp add_phone_number call count (must be 1 from Step 5): "
      f"{mock_wa.add_phone_number.call_count}")
assert mock_wa.add_phone_number.call_count == 1, "add_phone_number should NOT be called on validation error"
print(f"{PASS} WhatsApp API correctly NOT called after validation failure.")

# ===========================================================================
# STEP 7 -- DeskOnboardingService: whatsapp_error path
# ===========================================================================
print()
print("--- Step 7: DeskOnboardingService -- WhatsApp Error Path ---")

from mergen_pkg_whatsapp.client import WhatsAppAPIError

mock_wa_fail = MagicMock()
mock_wa_fail.add_phone_number.side_effect = WhatsAppAPIError(
    "POST", "/phone_numbers", 400, '{"error": {"message": "Invalid phone number format"}}'
)
mock_rag2 = MagicMock()
mock_tm2   = TenantManager()

service_fail = DeskOnboardingService(
    whatsapp_client=mock_wa_fail,
    tenant_manager=mock_tm2,
    rag_engine=mock_rag2,
)

result_wa_err = service_fail.setup_new_client(
    tenant_id="desk-wa-error-tenant",
    business_name="WA Fail Corp",
    raw_form_data=full_form,
    phone_number="+1INVALID",
)
assert result_wa_err["status"] == "whatsapp_error"
assert result_wa_err["error"] is not None
print(f"{PASS} whatsapp_error correctly returned on Meta API failure.")
print(f"       error snippet: {str(result_wa_err['error'])[:80]}")

# ===========================================================================
# Summary
# ===========================================================================
print()
print("=" * 60)
print(" All Phase 6 checks completed successfully.")
print("=" * 60)
print()
