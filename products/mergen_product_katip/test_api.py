"""
Mergen Kâtip — API Router End-to-End Test
==========================================
FastAPI TestClient ile tüm endpoint'leri gerçek DB üzerinde test eder.
Çalıştır:
    $env:PYTHONPATH="core;packages;products;shared"
    uv run python products/mergen_product_katip/test_api.py
"""
from __future__ import annotations

import sys
import uuid

# FastAPI TestClient
from fastapi import FastAPI
from fastapi.testclient import TestClient

# App'i minimal olarak kur — sadece katip router
app = FastAPI(title="Katip API Test")

from mergen_product_katip.router import router as katip_router  # noqa
app.include_router(katip_router, prefix="/api/katip")

client = TestClient(app, raise_server_exceptions=True)
TENANT = "pilot-dental-clinic-01"
HEADERS = {"X-Tenant-ID": TENANT}

PASS = "[OK]"
FAIL = "[FAIL]"

def check(label: str, condition: bool, detail: str = ""):
    if condition:
        print(f"  {PASS} {label}")
    else:
        print(f"  {FAIL} {label}  {detail}", file=sys.stderr)
        sys.exit(1)


def sep(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


sep("1. GET /api/katip/topics — Konu kuyruğu listeleme")
r = client.get("/api/katip/topics", headers=HEADERS)
check("HTTP 200", r.status_code == 200, str(r.text))
data = r.json()
check("Yanıt tenant_id doğru", data["tenant_id"] == TENANT)
check("items listesi mevcut", isinstance(data["items"], list))
print(f"     Toplam konu sayısı: {data['total']}")

# Pending konuları filtrele
pending_topics = [t for t in data["items"] if t["status"] == "pending"]
print(f"     Pending konular: {len(pending_topics)}")

sep("2. POST /api/katip/topics — Yeni konu oluştur")
new_title = f"Test Konusu - {uuid.uuid4().hex[:6]}"
r = client.post(
    "/api/katip/topics",
    json={"topic_title": new_title, "target_keywords": ["test", "diş"], "priority": 3},
    headers=HEADERS,
)
check("HTTP 201", r.status_code == 201, str(r.text))
created = r.json()
check("status=created", created["status"] == "created")
check("topic_id var", bool(created["topic_id"]))
new_topic_id = created["topic_id"]
print(f"     Oluşturulan topic_id: {new_topic_id}")

sep("3. POST /api/katip/drafts/generate — Taslak üretimi (v1)")
r = client.post(
    "/api/katip/drafts/generate",
    json={"topic_id": new_topic_id},
    headers=HEADERS,
)
check("HTTP 201", r.status_code == 201, str(r.text))
gen = r.json()
check("status=success", gen["status"] == "success", str(gen))
check("draft_id var", bool(gen["draft_id"]))
check("version_number=1", gen["version_number"] == 1)
check("word_count > 0", gen["word_count"] > 0)
check("latency_ms > 0", gen["latency_ms"] > 0)
draft_id = gen["draft_id"]
print(f"     Draft ID: {draft_id}  Kelime: {gen['word_count']}  Latency: {gen['latency_ms']}ms")

sep("4. GET /api/katip/drafts/{draft_id} — Taslak detay ve versiyon geçmişi")
r = client.get(f"/api/katip/drafts/{draft_id}", headers=HEADERS)
check("HTTP 200", r.status_code == 200, str(r.text))
detail = r.json()
check("draft_id eşleşiyor", detail["draft_id"] == draft_id)
check("latest_version mevcut", detail["latest_version"] is not None)
check("versions listesi >= 1", len(detail["versions"]) >= 1)
print(f"     Versiyon sayısı: {len(detail['versions'])}")
print(f"     İçerik önizleme: {detail['latest_version']['content'][:120]}...")

sep("5. POST /api/katip/drafts/generate — İdempotency testi (2. kez üret)")
r = client.post(
    "/api/katip/drafts/generate",
    json={"topic_id": new_topic_id},
    headers=HEADERS,
)
check("HTTP 201", r.status_code == 201, str(r.text))
idem = r.json()
check("status=already_processed (idempotent)", idem["status"] == "already_processed", str(idem))
print(f"     Idempotent yanıt: {idem['status']}")

sep("6. POST /api/katip/drafts/{draft_id}/regenerate — Feedback ile v2 üret")
r = client.post(
    f"/api/katip/drafts/{draft_id}/regenerate",
    json={
        "feedback_note": "Giriş paragrafında kullanılan 'genellikle' kelimesini somut rakamlarla değiştir. İlk cümle 12 kelime olmalı.",
        "author_label": "test-editor",
    },
    headers=HEADERS,
)
check("HTTP 201", r.status_code == 201, str(r.text))
regen = r.json()
check("status=regenerated", regen["status"] == "regenerated")
check("new_version_number=2", regen["new_version_number"] == 2)
check("feedback_id var", bool(regen["feedback_id"]))
check("word_count > 0", regen["word_count"] > 0)
print(f"     v2 Version ID: {regen['new_version_id']}  Kelime: {regen['word_count']}")

sep("7. GET /api/katip/drafts/{draft_id} — v2 sonrası versiyon geçmişi")
r = client.get(f"/api/katip/drafts/{draft_id}", headers=HEADERS)
check("HTTP 200", r.status_code == 200)
detail2 = r.json()
check("versions listesi = 2", len(detail2["versions"]) == 2)
check("latest_version.version_number=2", detail2["latest_version"]["version_number"] == 2)
print(f"     v2 içerik önizleme: {detail2['latest_version']['content'][:120]}...")

sep("8. PUT /api/katip/drafts/{draft_id}/status — Durum güncelleme (approved)")
r = client.put(
    f"/api/katip/drafts/{draft_id}/status",
    json={"status": "approved"},
    headers=HEADERS,
)
check("HTTP 200", r.status_code == 200, str(r.text))
upd = r.json()
check("new_status=approved", upd["new_status"] == "approved")
print(f"     Önceki durum: {upd['previous_status']} -> Yeni durum: {upd['new_status']}")

sep("9. GET /api/katip/drafts — Genel taslak listesi")
r = client.get("/api/katip/drafts", headers=HEADERS)
check("HTTP 200", r.status_code == 200)
drafts_list = r.json()
check("items listesi mevcut", isinstance(drafts_list["items"], list))
check("Toplam > 0", drafts_list["total"] > 0)
print(f"     Toplam taslak: {drafts_list['total']}")

sep("10. Hata durumu: geçersiz tenant")
r = client.get("/api/katip/topics", headers={"X-Tenant-ID": "olmayan-tenant-xyz"})
check("HTTP 404 bekleniyor", r.status_code == 404)
print(f"     Detail: {r.json()['detail']}")

print("\n" + "="*60)
print("  TUMU GECTI! Katip API Router E2E Test basariyla tamamlandi.")
print("="*60)
