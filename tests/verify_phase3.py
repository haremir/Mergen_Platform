"""
verify_phase3.py
~~~~~~~~~~~~~~~~

Phase 3 verification script for the Mergen Platform core governance layer.

Validates:
  1. Import sanity — all Phase 3 modules load without errors.
  2. TenantManager — create, get by id, get by whatsapp_phone_number_id.
  3. PlanGuard — quota enforcement (starter plan, 500 msg limit).
  4. PlanGuard — LLM circuit breaker (open after 3 consecutive failures).

Run from the repo root:
    uv run verify_phase3.py

Expected output:
    [PASS] All imports OK
    [PASS] TenantManager instantiated
    [PASS] create_tenant OK
    [PASS] get_tenant_by_id OK
    [PASS] get_tenant_by_whatsapp_id OK (webhook routing)
    [PASS] PlanGuard instantiated
    [PASS] First 500 calls allowed (starter plan)
    [PASS] 501st call BLOCKED (quota exceeded)
    [PASS] 3 LLM failures tracked
    [PASS] Circuit is OPEN after threshold
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Path setup — make shared/ and core/ importable from repo root
# ---------------------------------------------------------------------------
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_TESTS_DIR)
sys.path.insert(0, os.path.join(_ROOT, "shared"))
sys.path.insert(0, os.path.join(_ROOT, "core"))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.WARNING,   # Suppress DEBUG/INFO noise during verify
    format="%(levelname)-8s  %(name)s — %(message)s",
)
log = logging.getLogger("verify_phase3")

PASS  = "\033[92m[PASS]\033[0m"
FAIL  = "\033[91m[FAIL]\033[0m"

print("\n" + "=" * 60)
print(" Mergen Platform — Phase 3 Verification")
print("=" * 60 + "\n")

# ===========================================================================
# STEP 1 — Import verification
# ===========================================================================
try:
    from mergen_common.models import Tenant, InboundMessage
    from mergen_core.tenant_manager import TenantManager, TenantNotFoundError, TenantAlreadyExistsError
    from mergen_core.plan_guard import PlanGuard, PLAN_LIMITS
    print(f"{PASS} All imports resolved successfully.")
except ImportError as exc:
    print(f"{FAIL} Import error: {exc}")
    sys.exit(1)

# ===========================================================================
# STEP 2 — TenantManager
# ===========================================================================
print("\n--- Step 2: TenantManager ---")

try:
    manager = TenantManager()
    print(f"{PASS} TenantManager instantiated (in-memory mock backend).")
except Exception as exc:
    print(f"{FAIL} TenantManager init: {exc}")
    sys.exit(1)

# Create a fake starter tenant
TENANT_ID       = "demo-tenant-phase3-001"
PHONE_NUMBER_ID = "10987654321"

fake_tenant = Tenant(
    tenant_id=TENANT_ID,
    business_name="Acme Messaging Co.",
    sector="retail",
    plan="starter",
    whatsapp_phone_number_id=PHONE_NUMBER_ID,
    created_at=datetime.now(timezone.utc),
)

try:
    manager.create_tenant(fake_tenant)
    print(f"{PASS} create_tenant OK — tenant '{TENANT_ID}' saved.")
    print(f"       total tenants in store: {manager.count()}")
except Exception as exc:
    print(f"{FAIL} create_tenant: {exc}")
    sys.exit(1)

# get_tenant_by_id
try:
    retrieved = manager.get_tenant_by_id(TENANT_ID)
    assert retrieved.tenant_id == TENANT_ID
    assert retrieved.plan == "starter"
    print(f"{PASS} get_tenant_by_id OK — name='{retrieved.business_name}' plan='{retrieved.plan}'")
except Exception as exc:
    print(f"{FAIL} get_tenant_by_id: {exc}")
    sys.exit(1)

# get_tenant_by_whatsapp_id (webhook routing hot path)
try:
    routed = manager.get_tenant_by_whatsapp_id(PHONE_NUMBER_ID)
    assert routed.tenant_id == TENANT_ID
    print(f"{PASS} get_tenant_by_whatsapp_id OK — phone_number_id='{PHONE_NUMBER_ID}' -> tenant='{routed.tenant_id}'")
    print(f"       (This is the webhook firewall routing key resolution.)")
except Exception as exc:
    print(f"{FAIL} get_tenant_by_whatsapp_id: {exc}")
    sys.exit(1)

# Negative path — unknown phone_number_id should raise TenantNotFoundError
try:
    manager.get_tenant_by_whatsapp_id("000000000")
    print(f"{FAIL} Expected TenantNotFoundError but got no exception.")
    sys.exit(1)
except TenantNotFoundError:
    print(f"{PASS} TenantNotFoundError correctly raised for unknown phone_number_id.")

# Duplicate create should raise TenantAlreadyExistsError
try:
    manager.create_tenant(fake_tenant)
    print(f"{FAIL} Expected TenantAlreadyExistsError but got no exception.")
    sys.exit(1)
except TenantAlreadyExistsError:
    print(f"{PASS} TenantAlreadyExistsError correctly raised for duplicate tenant_id.")

# ===========================================================================
# STEP 3 — PlanGuard quota enforcement
# ===========================================================================
print("\n--- Step 3: PlanGuard — Quota Enforcement ---")

try:
    guard = PlanGuard()
    print(f"{PASS} PlanGuard instantiated (in-memory mock backend).")
    print(f"       Plan limits: {PLAN_LIMITS}")
except Exception as exc:
    print(f"{FAIL} PlanGuard init: {exc}")
    sys.exit(1)

STARTER_LIMIT = PLAN_LIMITS["starter"]   # 500
allowed_count = 0
blocked_count = 0

for i in range(STARTER_LIMIT + 1):
    result = guard.check_and_increment(TENANT_ID, "starter")
    if result:
        allowed_count += 1
    else:
        blocked_count += 1

print(f"       Simulated {STARTER_LIMIT + 1} API calls:")
print(f"         Allowed: {allowed_count}")
print(f"         Blocked: {blocked_count}")

if allowed_count == STARTER_LIMIT:
    print(f"{PASS} First {STARTER_LIMIT} calls ALLOWED (starter plan quota intact).")
else:
    print(f"{FAIL} Expected {STARTER_LIMIT} allowed calls, got {allowed_count}.")
    sys.exit(1)

if blocked_count == 1:
    print(f"{PASS} Call #{STARTER_LIMIT + 1} BLOCKED — quota correctly exhausted.")
else:
    print(f"{FAIL} Expected 1 blocked call, got {blocked_count}.")
    sys.exit(1)

current_usage = guard.get_usage(TENANT_ID)
print(f"       Current usage counter value: {current_usage}")

# ===========================================================================
# STEP 4 — PlanGuard LLM Circuit Breaker
# ===========================================================================
print("\n--- Step 4: PlanGuard — LLM Circuit Breaker ---")

CB_TENANT = "circuit-breaker-test-tenant"
assert not guard.is_circuit_open(CB_TENANT), "Circuit should start CLOSED."
print(f"{PASS} Circuit starts CLOSED for fresh tenant.")

# Simulate 3 consecutive LLM failures
failure_counts = []
for i in range(1, 4):
    count = guard.track_llm_failure(CB_TENANT)
    failure_counts.append(count)
    print(f"       LLM failure #{i} tracked — consecutive count: {count}")

assert failure_counts == [1, 2, 3], f"Expected [1,2,3], got {failure_counts}"
print(f"{PASS} 3 consecutive LLM failures correctly tracked.")

# Circuit must be open now
circuit_open = guard.is_circuit_open(CB_TENANT)
if circuit_open:
    print(f"{PASS} Circuit is OPEN after {3} failures — LLM calls correctly BLOCKED.")
else:
    print(f"{FAIL} Circuit should be OPEN but is_circuit_open() returned False.")
    sys.exit(1)

# Manual reset should close it
guard.reset_circuit(CB_TENANT)
assert not guard.is_circuit_open(CB_TENANT), "Circuit should be CLOSED after manual reset."
print(f"{PASS} Circuit correctly CLOSED after manual reset_circuit() call.")

# Verify isolated — original TENANT_ID circuit is not affected
assert not guard.is_circuit_open(TENANT_ID), "Tenant isolation broken — other tenant circuit open."
print(f"{PASS} Tenant isolation confirmed — other tenant's circuit is CLOSED.")

# ===========================================================================
# Summary
# ===========================================================================
print("\n" + "=" * 60)
print(" All Phase 3 checks completed successfully.")
print("=" * 60 + "\n")
