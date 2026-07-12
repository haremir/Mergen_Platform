"""
verify_phase2.py
~~~~~~~~~~~~~~~~

Phase 2 verification script for the Mergen Platform core intelligence layer.

Validates:
  1. Import sanity — all modules load without errors.
  2. RagEngine (FAISS backend) — ingest 3 KnowledgeFields, retrieve relevant ones.
  3. LLMGateway — mock route() is tested (real call skipped if no API keys set).
  4. build_context_block — formats retrieved fields correctly.

Run from the repo root:
    python verify_phase2.py

Expected output:
    [PASS] All imports OK
    [PASS] FAISS RagEngine initialised
    [PASS] 3/3 fields ingested
    [PASS] retrieve() returned N results
    [PASS] Context block built
    [PASS] LLMGateway instantiated
    [PASS/SKIP] LLM route() ...
"""

from __future__ import annotations

import logging
import os
import sys

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
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("verify_phase2")

PASS  = "\033[92m[PASS]\033[0m"
SKIP  = "\033[93m[SKIP]\033[0m"
FAIL  = "\033[91m[FAIL]\033[0m"

# ===========================================================================
# STEP 1 — Import verification
# ===========================================================================
print("\n" + "="*60)
print(" Mergen Platform — Phase 2 Verification")
print("="*60 + "\n")

try:
    from mergen_common.models import InboundMessage, KnowledgeField, OutboundMessage, Tenant
    from mergen_core.rag_engine import RagEngine, build_context_block
    from mergen_core.llm_gateway import LLMGateway, UsageRecord, get_gateway
    print(f"{PASS} All imports resolved successfully.")
except ImportError as exc:
    print(f"{FAIL} Import error: {exc}")
    sys.exit(1)

# ===========================================================================
# STEP 2 — RagEngine with FAISS backend
# ===========================================================================

print("\n--- Step 2: RagEngine (FAISS) ---")

try:
    engine = RagEngine(backend="faiss")
    print(f"{PASS} RagEngine (FAISS backend) initialised.")
except Exception as exc:
    print(f"{FAIL} RagEngine init: {exc}")
    sys.exit(1)

# Dummy tenant and knowledge fields
TENANT_ID = "demo-tenant-abc-123"

dummy_fields = [
    KnowledgeField(
        tenant_id=TENANT_ID,
        field_type="faq",
        value=(
            "Q: What are your business hours?\n"
            "A: We are open Monday through Friday, 09:00–18:00. "
            "Saturday by appointment only."
        ),
    ),
    KnowledgeField(
        tenant_id=TENANT_ID,
        field_type="policy",
        value=(
            "Cancellation policy: Customers must cancel at least 24 hours "
            "in advance to receive a full refund. Late cancellations are "
            "subject to a 50% fee."
        ),
    ),
    KnowledgeField(
        tenant_id=TENANT_ID,
        field_type="product",
        value=(
            "Premium Support Package: Includes 24/7 priority email support, "
            "dedicated account manager, and monthly performance reviews. "
            "Starting at $299/month."
        ),
    ),
]

try:
    count = engine.ingest_fields(TENANT_ID, dummy_fields)
    assert count == 3, f"Expected 3 indexed, got {count}"
    print(f"{PASS} {count}/3 fields ingested into FAISS index.")
    print(f"       Total vectors in index: {engine.count()}")
    print(f"       Tenant-scoped count:    {engine.count(TENANT_ID)}")
except Exception as exc:
    print(f"{FAIL} ingest_fields: {exc}")
    sys.exit(1)

# ===========================================================================
# STEP 3 — Retrieve
# ===========================================================================

print("\n--- Step 3: retrieve() ---")

QUERY = "Do you have any cancellation fee policy?"
try:
    results = engine.retrieve(TENANT_ID, QUERY, top_k=2)
    print(f"{PASS} retrieve() returned {len(results)} result(s) for query:")
    print(f"       Query: \"{QUERY}\"")
    for i, field in enumerate(results, 1):
        print(f"       [{i}] type={field.field_type!r} | value='{field.value[:80]}...'")
except Exception as exc:
    print(f"{FAIL} retrieve(): {exc}")
    sys.exit(1)

# ===========================================================================
# STEP 4 — Context block formatting
# ===========================================================================

print("\n--- Step 4: build_context_block() ---")

try:
    context = build_context_block(results)
    assert context and len(context) > 20, "Context block too short"
    print(f"{PASS} Context block built ({len(context)} chars):")
    print("       " + context.replace("\n", "\n       ")[:300])
except Exception as exc:
    print(f"{FAIL} build_context_block(): {exc}")
    sys.exit(1)

# ===========================================================================
# STEP 5 — LLMGateway instantiation + route()
# ===========================================================================

print("\n--- Step 5: LLMGateway ---")

try:
    gw = LLMGateway()  # reads from env vars, all optional
    print(f"{PASS} LLMGateway instantiated.")
    print(f"       local_url present:    {bool(gw._local_url)}")
    print(f"       openrouter key set:   {bool(gw._or_key)}")
    print(f"       groq key set:         {bool(gw._groq_key)}")
except Exception as exc:
    print(f"{FAIL} LLMGateway init: {exc}")
    sys.exit(1)

# Attempt a real route() only if at least one API key is present
_has_any_key = gw._or_key or gw._groq_key or gw._local_url

if _has_any_key:
    system_prompt = (
        "You are a helpful AI assistant. Use the context below to answer.\n\n"
        f"<context>\n{context}\n</context>"
    )
    user_query = QUERY
    print(f"\n       Attempting real LLM call for tenant={TENANT_ID!r}...")
    try:
        reply = gw.route(user_query, system_prompt, tenant_id=TENANT_ID)
        usage = gw.last_usage()
        print(f"{PASS} LLM route() succeeded.")
        print(f"       Provider:  {usage.provider if usage else 'n/a'}")
        print(f"       Model:     {usage.model if usage else 'n/a'}")
        print(f"       Tokens:    {usage.total_tokens if usage else 'n/a'}")
        print(f"       Latency:   {usage.latency_ms:.1f} ms" if usage else "")
        print(f"       Response:  '{reply[:200]}'")
    except RuntimeError as exc:
        print(f"{FAIL} LLM route() — all tiers exhausted: {exc}")
else:
    print(
        f"{SKIP} No API keys detected (LOCAL_LLM_URL / OPENROUTER_API_KEY / "
        f"GROQ_API_KEY not set).\n"
        f"       Verifying gateway fallback raises RuntimeError correctly..."
    )
    try:
        gw.route("test", "test", tenant_id=TENANT_ID)
        print(f"{FAIL} Expected RuntimeError but got a response.")
    except RuntimeError as exc:
        print(f"{PASS} LLMGateway correctly raises RuntimeError when all tiers unavailable:")
        print(f"       {str(exc)[:120]}")

# ===========================================================================
# Summary
# ===========================================================================

print("\n" + "="*60)
print(" All Phase 2 checks completed.")
print("="*60 + "\n")
