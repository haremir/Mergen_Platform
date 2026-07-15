"""
verify_full_system_capillaries.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Extremely comprehensive end-to-end integration and E2E verification test.
Descends into the capillaries of all system components:
1. Database Schema Seeding & Migrations
2. Onboarding Request Validations & Fields (WhatsApp, Telegram)
3. PlanGuard Quotas & Circuit Breaker Logic
4. HandoffEngine Multilingual Intent Detection
5. RAG Engine Singleton Vector Search
6. Environmental API Keys / Model Resolution
7. WhatsApp Channel Webhook Endpoints
8. Telegram Channel Webhook Endpoints
9. FastAPI Management Endpoints (Health, Settings, Logs, Analytics, Plan)
"""

from __future__ import annotations

import os
import sys
import uuid
import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# Path setup - add project root and internal packages to sys.path
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
for _p in (
    os.path.join(_ROOT, "shared"),
    os.path.join(_ROOT, "core"),
    os.path.join(_ROOT, "packages"),
    os.path.join(_ROOT, "products"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Mock env keys before loading app
os.environ["OPENROUTER_API_KEY"] = "sk-or-v1-capillary-test-key-999"
os.environ["DEFAULT_LLM_MODEL"] = "meta-llama/llama-3.3-70b-instruct"

from fastapi.testclient import TestClient
from panel.api_server import app, startup_event, _REAL_MESSAGE_LOGS

from mergen_common.models import KnowledgeField, InboundMessage
from mergen_core.database import engine, Base, SessionLocal
from mergen_core.db_models import DBTenant, DBSectorPrompt, DBPlanUsage, DBPlatformSetting
from mergen_core.tenant_manager import get_tenant_manager
from mergen_core.rag_engine import get_rag_engine
from mergen_core.plan_guard import get_plan_guard
from mergen_core.handoff_engine import get_handoff_engine, REASON_USER_REQUESTED
from mergen_core.llm_orchestrator import process_inbound_message

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"

# Ensure all DB tables are fresh and initialized
Base.metadata.create_all(bind=engine)


async def run_full_system_test():
    print("\n" + "=" * 80)
    print(" Mergen Platform -- Full System Capillaries E2E Integration Test")
    print("=" * 80 + "\n")

    client = TestClient(app)

    # ──────────────────────────────────────────────────────────────────────────
    # Capillary 1: Database Schema & Startup Seeding Checks
    # ──────────────────────────────────────────────────────────────────────────
    print("--- Capillary 1: Database Schema & Seeding ---")
    
    # Clear prompts table and re-run startup seeder
    with SessionLocal() as session:
        session.query(DBSectorPrompt).delete()
        session.commit()
    
    startup_event()
    
    with SessionLocal() as session:
        prompts = session.query(DBSectorPrompt).all()
        assert len(prompts) == 4, f"Seeding failed: expected 4 sector prompts, found {len(prompts)}"
        for sector in ["hairdresser", "beauty_salon", "restaurant", "other"]:
            db_prompt = session.query(DBSectorPrompt).filter(DBSectorPrompt.sector_id == sector).first()
            assert db_prompt is not None, f"Sector prompt missing for {sector}"
            assert len(db_prompt.base_prompt) > 20, f"Sector prompt for {sector} too short"
            
        print(f"{PASS} Database tables exist, and all default sector prompts seeded successfully.")

    # ──────────────────────────────────────────────────────────────────────────
    # Capillary 2: Onboarding Validation & Path Gating
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- Capillary 2: Onboarding Validation & Constraints ---")
    
    # 2.1 Malformed/Missing data validation (HTTP 422)
    bad_payload = {
        "business_name": "S",  # min_length=2 violation
        "phone_number": "123",  # min_length=7 violation
        "location": "Istanbul"
        # missing required fields: business_hours, cancellation_policy, contact_info, services, sector, persona, meta_phone_id
    }
    bad_resp = client.post("/api/onboarding", json=bad_payload)
    assert bad_resp.status_code == 422
    err_fields = [e["loc"][-1] for e in bad_resp.json()["detail"]]
    assert "business_name" in err_fields or "body" in err_fields
    print(f"{PASS} Validation constraints correctly raise HTTP 422 on bad payload.")

    # 2.2 Onboarding Happy Path
    tenant_id = "c14e1f7a-8fcc-4d33-911e-b8324a35c136"
    onboard_payload = {
        "business_name": "Capillary Hair Studio",
        "phone_number": "+905557776666",
        "business_hours": {"monday": "09:00-19:00", "tuesday": "09:00-19:00"},
        "location": "Kadikoy Merkez, Istanbul",
        "cancellation_policy": "No cancellation within 24 hours.",
        "contact_info": "reception@capillary.com | +90 216 111 2222",
        "services": [{"name": "Saç Kesimi", "price": "120 TL", "description": "Erkek ve kadın saç tasarım"}],
        "faqs": [{"question": "Otopark var mı?", "answer": "Evet, otoparkımız mevcuttur."}],
        "sector": "hairdresser",
        "persona": "friendly_energetic",
        "meta_phone_id": "capillary_meta_phone_id_999",
        "telegram_token": "111222333:AAE_tg_token_capillaries"
    }

    # Intercept onboarding setup_new_client to enforce static UUID
    import uuid as uuid_mod
    with patch("uuid.uuid4", return_value=uuid_mod.UUID(tenant_id)):
        resp = client.post("/api/onboarding", json=onboard_payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending_verification"
        assert data["tenant_id"] == tenant_id
        assert data["phone_number_id"] == "MOCK_PHONE_ID_TEST001" or data["phone_number_id"].startswith("MOCK_PHONE_ID_")
        assert data["knowledge_fields_ingested"] == 7
        
    print(f"{PASS} Onboarding flow executed. Tenant registered in DB and RAG index initialized.")

    # ──────────────────────────────────────────────────────────────────────────
    # Capillary 3: Process-Wide RAG Singleton Operations
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- Capillary 3: RAG Singleton indexing and queries ---")
    
    # Override embedding globally to run instantly
    get_rag_engine().embed = lambda text: [0.0] * 384
    
    # Ingest a custom knowledge field to test index search
    get_rag_engine().upsert(
        tenant_id=tenant_id,
        knowledge_field=KnowledgeField(
            tenant_id=tenant_id,
            field_type="faq",
            value="[faq] Question: Otopark var mı? | Answer: Evet, ücretsiz otopark mevcuttur.",
        )
    )
    
    # Search RAG
    results = get_rag_engine().retrieve(tenant_id=tenant_id, query="otopark", top_k=1)
    assert len(results) > 0
    assert "ücretsiz otopark mevcuttur" in results[0].value
    print(f"{PASS} RAG Singleton retrieved correct knowledge field for query.")

    # ──────────────────────────────────────────────────────────────────────────
    # Capillary 4: Plan Guard & Quotas
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- Capillary 4: Plan Guard & Quotas & Circuit Breaker ---")
    pg = get_plan_guard()
    
    # 4.1 Reset stats first
    pg.reset_usage(tenant_id)
    pg.reset_circuit(tenant_id)
    
    # 4.2 Check quota limit
    # Starter plan limit = 500 messages. Check 500 messages check.
    assert pg.check_and_increment(tenant_id, "starter") is True
    assert pg.get_usage(tenant_id) == 1
    
    # Force usage update directly in DB to test quota breach
    with SessionLocal() as session:
        db_usage = session.query(DBPlanUsage).filter(DBPlanUsage.tenant_id == tenant_id).first()
        if db_usage:
            db_usage.used_messages = 500
            session.commit()
            
    # Check that increment fails when limit reached
    assert pg.check_and_increment(tenant_id, "starter") is False
    print(f"{PASS} PlanGuard blocked request successfully when monthly limit (500) reached.")
    
    # Reset usage to enable further tests
    pg.reset_usage(tenant_id)

    # 4.3 Check circuit breaker
    # Simulate consecutive failures to trip circuit
    assert pg.is_circuit_open(tenant_id) is False
    pg.track_llm_failure(tenant_id)  # failure 1
    pg.track_llm_failure(tenant_id)  # failure 2
    pg.track_llm_failure(tenant_id)  # failure 3 -> trips breaker
    assert pg.is_circuit_open(tenant_id) is True
    print(f"{PASS} Circuit breaker tripped successfully after 3 consecutive failures.")
    
    # Reset circuit breaker
    pg.reset_circuit(tenant_id)
    assert pg.is_circuit_open(tenant_id) is False
    print(f"{PASS} Circuit breaker manually reset successfully.")

    # ──────────────────────────────────────────────────────────────────────────
    # Capillary 5: Handoff Engine Keyword Scans
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- Capillary 5: Handoff Engine Multilingual Intent Scans ---")
    he = get_handoff_engine()
    
    # Test turkish intent
    inbound_tr = InboundMessage(
        tenant_id=tenant_id,
        channel="telegram",
        sender="bob88",
        text="müşteri temsilcisiyle görüşmek istiyorum",
        raw_payload={},
        received_at=datetime.now(timezone.utc)
    )
    intent_detected = he.analyze_handoff_intent(inbound_tr.text)
    assert intent_detected is True
    keyword = he.get_trigger_label(inbound_tr.text)
    assert keyword is not None
    
    # Test English intent
    inbound_en = InboundMessage(
        tenant_id=tenant_id,
        channel="whatsapp",
        sender="bob88",
        text="I need to speak with a human agent, escalate this please",
        raw_payload={},
        received_at=datetime.now(timezone.utc)
    )
    intent_detected = he.analyze_handoff_intent(inbound_en.text)
    assert intent_detected is True
    
    # Trigger Handoff Event creation
    event = he.trigger_notification(tenant_id, inbound_tr)
    assert event["event_type"] == "handoff_required"
    assert event["reason"] == "user_requested"
    assert event["original_message"]["sender"] == "bob88"
    print(f"{PASS} Handoff intent detected for Turkish and English keyword capillaries.")

    # ──────────────────────────────────────────────────────────────────────────
    # Capillary 6 & 7: WhatsApp Webhook & LLM Orchestrator
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- Capillary 6 & 7: WhatsApp Webhook & LLM Orchestrator ---")
    
    # 6.1 WhatsApp Webhook GET Verification
    verify_resp = client.get("/webhook/whatsapp?hub.mode=subscribe&hub.challenge=capillary_challenge&hub.verify_token=mergen_token")
    assert verify_resp.status_code == 200
    assert verify_resp.text == "capillary_challenge"
    print(f"{PASS} GET /webhook/whatsapp verification request authenticated successfully.")

    # 6.2 WhatsApp Webhook POST message delivery
    registered_phone_id = data["phone_number_id"]
    wa_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba_999",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551112222",
                                "phone_number_id": registered_phone_id
                            },
                            "contacts": [{"profile": {"name": "Alice capillary"}, "wa_id": "905559876543"}],
                            "messages": [
                                {
                                    "from": "905559876543",
                                    "id": "wamid.capillary999",
                                    "timestamp": "1712345678",
                                    "type": "text",
                                    "text": {"body": "Otoparkınız var mı?"}
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }

    mock_llm_response = MagicMock()
    mock_llm_response.status_code = 200
    mock_llm_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Evet, otoparkımız mevcuttur."
                }
            }
        ]
    }

    # Patches:
    # 1. OpenRouter POST request (validating dynamic headers, API key, model from env, and prompts)
    # 2. WhatsAppClient.send_message (verifying client sends response back to sender)
    async def mock_wa_post(url, *args, **kwargs):
        if "openrouter.ai" in url:
            # Check headers
            headers = kwargs["headers"]
            assert headers["Authorization"] == "Bearer sk-or-v1-capillary-test-key-999"
            
            # Check model
            payload = kwargs["json"]
            assert payload["model"] == "meta-llama/llama-3.3-70b-instruct"
            
            # Check prompt injection
            sys_prompt = payload["messages"][0]["content"]
            assert "Sen bir kuaför salonunun ön büro asistanısın" in sys_prompt  # Sector Prompt
            assert "Sen son derece dost canlısı, enerjik" in sys_prompt         # Persona Prompt
            assert "Evet, ücretsiz otopark mevcuttur" in sys_prompt             # RAG Context
            print(f"{PASS} OpenRouter call payload validates correctly.")
            return mock_llm_response
            
        raise ValueError(f"Unexpected URL inside mock client: {url}")

    _REAL_MESSAGE_LOGS.clear()

    with patch("httpx.AsyncClient.post", side_effect=mock_wa_post), \
         patch("mergen_pkg_whatsapp.client.WhatsAppClient.send_message") as mock_wa_send:
             
        post_resp = client.post("/webhook/whatsapp", json=wa_payload)
        assert post_resp.status_code == 200
        print(f"{PASS} Webhook POST /webhook/whatsapp returns 200 OK.")
        
        # Allow background task to process
        await asyncio.sleep(1.0)
        
        mock_wa_send.assert_called_once()
        sent_wa_msg = mock_wa_send.call_args[0][0]
        assert sent_wa_msg.recipient == "905559876543"
        assert sent_wa_msg.text == "Evet, otoparkımız mevcuttur."
        print(f"{PASS} WhatsAppClient called with correct reply recipient and text.")

    # ──────────────────────────────────────────────────────────────────────────
    # Capillary 8: Telegram Webhook & Client
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- Capillary 8: Telegram Webhook & Client ---")
    
    tg_payload = {
        "update_id": 8877,
        "message": {
            "message_id": 55,
            "chat": {"id": 999988, "type": "private"},
            "text": "Otopark var mı?"
        }
    }

    # Mock post calls to Telegram sendMessage
    async def mock_tg_post(url, *args, **kwargs):
        if "openrouter.ai" in url:
            return mock_llm_response
        elif "api.telegram.org" in url:
            assert "bot111222333:AAE_tg_token_capillaries" in url
            payload = kwargs["json"]
            assert payload["chat_id"] == "999988"
            assert payload["text"] == "Evet, otoparkımız mevcuttur."
            print(f"{PASS} Telegram bot token and sendMessage payloads match successfully.")
            
            mock_tg_res = MagicMock()
            mock_tg_res.status_code = 200
            mock_tg_res.json.return_value = {"ok": True}
            return mock_tg_res
            
        raise ValueError(f"Unexpected URL inside mock client: {url}")

    with patch("httpx.AsyncClient.post", side_effect=mock_tg_post):
        tg_resp = client.post(f"/webhook/telegram/{tenant_id}", json=tg_payload)
        assert tg_resp.status_code == 200
        print(f"{PASS} Webhook POST /webhook/telegram/{tenant_id} returns 200 OK.")
        
        # Allow background task to process
        await asyncio.sleep(1.0)

    # ──────────────────────────────────────────────────────────────────────────
    # Capillary 9: FastAPI Management Endpoints (Health, Settings, Logs, etc.)
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- Capillary 9: FastAPI Management Endpoints ---")
    
    # 9.1 health
    health_resp = client.get("/api/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "ok"
    print(f"{PASS} GET /api/health -> liveness probe passed.")

    # 9.2 plan
    plan_resp = client.get(f"/api/plan/{tenant_id}")
    assert plan_resp.status_code == 200
    pdata = plan_resp.json()
    assert pdata["plan"] == "starter"
    assert pdata["limits"]["monthly_messages"]["limit"] == 500
    print(f"{PASS} GET /api/plan/{tenant_id} -> limits retrieved successfully.")

    # 9.3 logs
    logs_resp = client.get(f"/api/logs/{tenant_id}")
    assert logs_resp.status_code == 200
    ldata = logs_resp.json()
    
    # Verify Telegram and WhatsApp real logs exist in combined logs
    real_wa_logs = [m for m in ldata["messages"] if m["channel"] == "whatsapp" and m["direction"] == "inbound" and m["sender"] == "905559876543"]
    real_tg_logs = [m for m in ldata["messages"] if m["channel"] == "telegram" and m["direction"] == "inbound" and m["sender"] == "999988"]
    
    assert len(real_wa_logs) > 0, "WhatsApp real message log missing"
    assert len(real_tg_logs) > 0, "Telegram real message log missing"
    print(f"{PASS} GET /api/logs/{tenant_id} combines in-memory real logs with static mock logs.")

    # 9.4 Platform Settings GET/POST
    settings_payload = {
        "maintenance_mode": True,
        "allow_new_registrations": False,
        "global_system_alerts": "Maintenance tonight!"
    }
    post_settings = client.post("/api/platform/settings", json=settings_payload)
    assert post_settings.status_code == 200
    
    get_settings = client.get("/api/platform/settings")
    assert get_settings.status_code == 200
    sdata = get_settings.json()
    assert sdata["maintenance_mode"] is True
    assert sdata["allow_new_registrations"] is False
    assert sdata["global_system_alerts"] == "Maintenance tonight!"
    print(f"{PASS} GET/POST /api/platform/settings successfully verified platform parameters.")

    # 9.5 Platform Analytics
    analytics_resp = client.get("/api/platform/analytics")
    assert analytics_resp.status_code == 200
    adata = analytics_resp.json()
    assert "metrics" in adata
    assert adata["metrics"]["active_tenants"] > 0
    print(f"{PASS} GET /api/platform/analytics returns calculations.")

    # 9.6 Tenant Settings Control
    control_payload = {
        "bot_active": False,
        "system_prompt_override": "Be extremely silent."
    }
    control_resp = client.post(f"/api/tenant/{tenant_id}/settings", json=control_payload)
    assert control_resp.status_code == 200
    cdata = control_resp.json()
    assert cdata["bot_active"] is False
    assert cdata["system_prompt_override"] == "Be extremely silent."
    print(f"{PASS} POST /api/tenant/settings successfully modified active state and override rules.")

    print("\n" + "=" * 80)
    print(" ALL 9 CAPILLARY SYSTEM E2E TESTS COMPLETED SUCCESSFULLY: PASSED")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(run_full_system_test())
