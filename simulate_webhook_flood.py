"""
simulate_webhook_flood.py
~~~~~~~~~~~~~~~~~~~~~~~~~

Direct core concurrency simulation for the Mergen Platform.
Tests the thread-safety of the PlanGuard and TenantManager under high concurrent loads.

Bypasses the HTTP layer and FastAPI/Uvicorn entirely. Instantiates core classes directly
and executes 500 concurrent messages using Python's concurrent.futures.ThreadPoolExecutor.

Replaces the RAG embedding function with a dummy stub to prevent loading the heavy
SentenceTransformer ML model, ensuring the simulation runs and completes in seconds.

Usage:
    uv run simulate_webhook_flood.py
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
import concurrent.futures
from typing import List, Dict

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_ROOT = os.path.dirname(os.path.abspath(__file__))
for _p in (
    os.path.join(_ROOT, "shared"),
    os.path.join(_ROOT, "core"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Core imports
# ---------------------------------------------------------------------------
from mergen_common.models import Tenant, KnowledgeField
from mergen_core.tenant_manager import TenantManager
from mergen_core.plan_guard import PlanGuard, PLAN_LIMITS
from mergen_core.rag_engine import RagEngine

# Stub the embedding model to avoid loading the heavy sentence-transformers package
# This makes the test run instantaneously.
RagEngine.embed = lambda self, text: [0.0] * 384

TENANT_ID = "concurrency-test-tenant-123"
TOTAL_MESSAGES = 500
CONCURRENT_THREADS = 50


def process_message(
    msg_id: int,
    tenant_manager: TenantManager,
    plan_guard: PlanGuard,
    rag_engine: RagEngine,
) -> str:
    """Simulate routing a single webhook message through the core components."""
    # 1. Resolve tenant details
    try:
        tenant = tenant_manager.get_tenant_by_id(TENANT_ID)
    except Exception as exc:
        return f"tenant_error: {exc}"

    # 2. Check plan quota and increment usage (enforced by PlanGuard)
    allowed = plan_guard.check_and_increment(tenant.tenant_id, tenant.plan)
    if not allowed:
        return "quota_blocked"

    # 3. Simulate RAG retrieve query
    try:
        results = rag_engine.retrieve(
            tenant_id=tenant.tenant_id,
            query=f"Simulated query {msg_id}",
            top_k=3,
        )
        # Verify results is a list (even if empty)
        assert isinstance(results, list)
    except Exception as exc:
        return f"rag_error: {exc}"

    return "processed"


def main() -> None:
    print("=" * 60)
    print(" Starting Core Webhook Flood Concurrency Simulation...")
    print(f" Simulating: {TOTAL_MESSAGES} messages")
    print(f" Max Workers: {CONCURRENT_THREADS} threads")
    print("=" * 60)
    print()

    # 1. Instantiate Core components directly
    tenant_manager = TenantManager()
    plan_guard = PlanGuard()
    rag_engine = RagEngine()

    # 2. Setup a tenant on the 'free' plan (limit: 100 messages)
    plan_slug = "free"
    quota_limit = PLAN_LIMITS[plan_slug]
    
    tenant = Tenant(
        tenant_id=TENANT_ID,
        business_name="Concurrency Corp",
        sector="desk",
        plan=plan_slug,
        whatsapp_phone_number_id="META_PHONE_999",
        created_at=datetime.now(tz=timezone.utc),
    )
    tenant_manager.create_tenant(tenant)
    print(f"[Core] Registered tenant '{tenant.business_name}' with plan '{plan_slug}' (limit: {quota_limit}).")

    # 3. Ingest a dummy knowledge field to populate the RAG index
    kf = KnowledgeField(
        tenant_id=TENANT_ID,
        field_type="policy",
        value="Default cancellation policy for concurrency test."
    )
    rag_engine.ingest_fields(TENANT_ID, [kf])
    print("[Core] Ingested 1 mock knowledge field into RagEngine.")
    print()

    print(f" Pounding core with {TOTAL_MESSAGES} concurrent calls...")
    start_time = time.perf_counter()

    # 4. Flood the core using ThreadPoolExecutor
    results: List[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT_THREADS) as executor:
        futures = [
            executor.submit(process_message, i, tenant_manager, plan_guard, rag_engine)
            for i in range(TOTAL_MESSAGES)
        ]
        for fut in concurrent.futures.as_completed(futures):
            results.append(fut.result())

    end_time = time.perf_counter()
    total_time = end_time - start_time

    # 5. Analyze results
    processed_count = results.count("processed")
    blocked_count = results.count("quota_blocked")
    errors = [r for r in results if r not in ("processed", "quota_blocked")]
    
    final_usage = plan_guard.get_usage(TENANT_ID)

    print("-" * 60)
    print(" Concurrency Test Summary")
    print("-" * 60)
    print(f" Total Time:          {total_time:.4f} seconds")
    print(f" Total Requests:      {len(results)}")
    print(f" Successful/Allowed:  {processed_count}")
    print(f" Quota Blocked:       {blocked_count}")
    print(f" Errors/Failures:     {len(errors)}")
    if errors:
        print(f" First error details: {errors[0]}")
    
    print(f"\n Final PlanGuard Usage Tracker value: {final_usage}")
    
    # 6. Safety Assertions
    print("\n Running Safety Validations...")
    
    # Check 1: Final usage should equal the quota limit exactly
    assert final_usage == quota_limit, f"Usage tracker value {final_usage} != limit {quota_limit}!"
    print(f" [PASS] PlanGuard tracker value ({final_usage}) matches quota limit ({quota_limit}) exactly.")
    
    # Check 2: Successful processed calls must equal the quota limit exactly
    assert processed_count == quota_limit, f"Processed count {processed_count} != limit {quota_limit}!"
    print(f" [PASS] Allowed count ({processed_count}) matches quota limit ({quota_limit}) exactly.")

    # Check 3: Blocked count must equal the remainder exactly
    expected_blocked = TOTAL_MESSAGES - quota_limit
    assert blocked_count == expected_blocked, f"Blocked count {blocked_count} != expected {expected_blocked}!"
    print(f" [PASS] Blocked count ({blocked_count}) matches expected remainder ({expected_blocked}) exactly.")
    
    print("\n Concurrency test PASSED. No race conditions detected.")
    print("=" * 60)


if __name__ == "__main__":
    main()
