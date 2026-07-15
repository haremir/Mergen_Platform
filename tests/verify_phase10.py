"""
verify_phase10.py
~~~~~~~~~~~~~~~~~

Phase 10 verification script for dynamic OpenRouter LLM integration.
"""

from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

# Path setup
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

from fastapi.testclient import TestClient
from panel.api_server import app, _REAL_MESSAGE_LOGS

from mergen_common.models import Tenant, KnowledgeField
from mergen_core.database import engine, Base, SessionLocal
from mergen_core.db_models import DBPlatformSetting, DBTenant
from mergen_core.tenant_manager import get_tenant_manager
from mergen_core.llm_orchestrator import process_inbound_message
from mergen_core.rag_engine import RagEngine, get_rag_engine

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"

# Initialize DB tables
Base.metadata.create_all(bind=engine)


async def async_test_flow():
    print("\n" + "=" * 60)
    print(" Mergen Platform -- Phase 10 Verification")
    print("=" * 60 + "\n")

    tenant_id = "test-tenant-uuid-10"
    phone_number_id = "test_phone_id_10"

    # Setup database with test tenant and setting overrides
    with SessionLocal() as session:
        # Clear existing test entries if any
        session.query(DBTenant).filter(DBTenant.id == tenant_id).delete()
        session.query(DBPlatformSetting).filter(DBPlatformSetting.key == "openrouter_api_key").delete()
        session.query(DBPlatformSetting).filter(DBPlatformSetting.key == "default_llm_model").delete()

        # Insert DBPlatformSetting with empty API key to test dynamic setting guard
        db_key = DBPlatformSetting(key="openrouter_api_key", value="")
        db_model = DBPlatformSetting(key="default_llm_model", value="qwen/qwen-2.5-14b-instruct")
        session.add(db_key)
        session.add(db_model)

        # Insert DBTenant
        db_tenant = DBTenant(
            id=tenant_id,
            business_name="Acme Reception test",
            sector="hairdresser",
            plan="starter",
            whatsapp_phone_number_id=phone_number_id,
            bot_active=True,
            system_prompt_override="Test override rule.",
            persona="corporate_formal",
        )
        session.add(db_tenant)
        session.commit()

    # Stub embed globally to make it instantaneous and ensure perfect matching
    RagEngine.embed = lambda self, text: [0.0] * 384
    rag = get_rag_engine()
    rag.upsert(
        tenant_id=tenant_id,
        knowledge_field=KnowledgeField(
            tenant_id=tenant_id,
            field_type="faq",
            value="[faq] Question: Adresiniz nedir? | Answer: Kadikoy, Istanbul",
        )
    )

    # --- Test 1: Empty API key fallback ---
    print("--- Test 1: Missing / Empty OpenRouter API key ---")
    if "OPENROUTER_API_KEY" in os.environ:
        del os.environ["OPENROUTER_API_KEY"]
    reply = await process_inbound_message(tenant_id, "Merhaba, adresinizi öğrenebilir miyim?")
    assert reply == "Sistem yöneticisi henüz LLM API anahtarını tanımlamadı.", f"Expected API key warning, got: {reply}"
    print(f"{PASS} Dynamic setting lookup block and fallback message matches successfully.")

    # --- Test 2: Valid API key & LLM payload construction ---
    print("\n--- Test 2: Mocked OpenRouter call with dynamic prompt assembly ---")
    os.environ["OPENROUTER_API_KEY"] = "sk-or-v1-test-key-12345"
    os.environ["DEFAULT_LLM_MODEL"] = "qwen/qwen-2.5-14b-instruct"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Acme Reception test asistanı olarak: Adresimiz Kadıköy, İstanbul'dur."
                }
            }
        ]
    }

    # Patch httpx.AsyncClient.post to verify correct payload submission
    with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        reply = await process_inbound_message(tenant_id, "Merhaba, adresinizi alabilir miyim?")
        assert "İstanbul" in reply, f"Expected RAG-backed mock response, got: {reply}"
        print(f"{PASS} LLM response returned successfully.")

        # Verify call arguments
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        url = args[0]
        assert url == "https://openrouter.ai/api/v1/chat/completions"
        headers = kwargs["headers"]
        assert headers["Authorization"] == "Bearer sk-or-v1-test-key-12345"

        payload = kwargs["json"]
        assert payload["model"] == "qwen/qwen-2.5-14b-instruct"
        
        # Verify prompt construction contains persona and override
        sys_prompt = payload["messages"][0]["content"]
        assert "ciddi ve saygın bir asistanın" in sys_prompt  # corporate_formal persona
        assert "Test override rule." in sys_prompt            # system_prompt_override
        assert "Kadikoy, Istanbul" in sys_prompt             # RAG Context
        print(f"{PASS} System prompt correctly injected with RAG context, dynamic persona, and custom override rules.")

    # --- Test 3: FastAPI Webhook endpoint integration ---
    print("\n--- Test 3: Webhook Verification and Dispatch Endpoints ---")
    client = TestClient(app)

    # Verification GET
    resp = client.get("/webhook/whatsapp?hub.mode=subscribe&hub.challenge=challenge123&hub.verify_token=mergen_token")
    assert resp.status_code == 200
    assert resp.text == "challenge123"
    print(f"{PASS} GET /webhook/whatsapp verification matches successfully.")

    # Message POST
    webhook_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba_123",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15550001234",
                                "phone_number_id": phone_number_id
                            },
                            "contacts": [{"profile": {"name": "Alice"}, "wa_id": "905551234567"}],
                            "messages": [
                                {
                                    "from": "905551234567",
                                    "id": "wamid.msg101",
                                    "timestamp": "1712345678",
                                    "type": "text",
                                    "text": {"body": "Adresinizi söyler misiniz?"}
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }

    # Clear logs
    _REAL_MESSAGE_LOGS.clear()

    # Mock send_message of WhatsAppClient to avoid actual Meta request
    with patch("mergen_pkg_whatsapp.client.WhatsAppClient.send_message") as mock_send, \
         patch("httpx.AsyncClient.post", return_value=mock_response):
        
        resp = client.post("/webhook/whatsapp", json=webhook_payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        print(f"{PASS} POST /webhook/whatsapp returned 200 OK.")

        # Give background tasks a brief moment to run
        await asyncio.sleep(0.5)

        mock_send.assert_called_once()
        sent_outbound = mock_send.call_args[0][0]
        assert "Kadıköy" in sent_outbound.text
        assert sent_outbound.recipient == "905551234567"
        print(f"{PASS} Background worker processed webhook message, ran LLM, and executed send_message successfully.")

        # Verify real log entry generated
        logs_resp = client.get(f"/api/logs/{tenant_id}")
        assert logs_resp.status_code == 200
        logs_data = logs_resp.json()
        assert logs_data["total"] > len(logs_data["messages"]) or any("SYSTEM" in m["sender"] for m in logs_data["messages"])
        print(f"{PASS} Conversation log updated with real message logs.")

    print("\n" + "=" * 60)
    print(" Phase 10 Verification End-To-End: PASSED")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(async_test_flow())
