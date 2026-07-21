"""
Mergen Kâtip — CMS & WordPress Publishing Verification Test
===========================================================
WordPress REST API / Webhook entegrasyonu ve dispatch_cms_publication
fonksiyonunun davranışını test eder.

Çalıştır:
    $env:PYTHONPATH="core;packages;products;shared"
    uv run python products/mergen_product_katip/test_cms.py
"""

from __future__ import annotations

import sys
import uuid
from unittest.mock import patch, MagicMock

from sqlalchemy.orm import Session
from mergen_core.database import SessionLocal
from mergen_product_katip.models import KatipTopicQueue, KatipDraft, KatipDraftVersion
from mergen_product_katip.cms_service import dispatch_cms_publication, publish_to_wordpress, publish_to_webhook
from mergen_product_katip.seed import seed_katip_pilot_data

TENANT = "pilot-dental-clinic-01"
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


def test_cms_publishing():
    sep("1. Veritabanı Hazırlığı & Seed")
    db: Session = SessionLocal()
    try:
        seed_katip_pilot_data(db)
        print("  [OK] Seed tamamlandı.")
    finally:
        db.close()

    sep("2. Test Taslağı ve Versiyon Oluşturma")
    db = SessionLocal()
    try:
        topic = KatipTopicQueue(
            tenant_id=TENANT,
            topic_title=f"CMS Yayınlama Test Konusu - {uuid.uuid4().hex[:6]}",
            status="done",
        )
        db.add(topic)
        db.commit()
        db.refresh(topic)

        draft = KatipDraft(
            topic_id=topic.id,
            tenant_id=TENANT,
            status="approved",
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)

        version = KatipDraftVersion(
            draft_id=draft.id,
            version_number=1,
            content="# CMS Yayınlama Testi\n\nBu içerik WordPress REST API üzerinden otomatik yayınlanacaktır.",
            word_count=120,
        )
        db.add(version)
        db.commit()
        draft_id = draft.id
        print(f"  [OK] Test Taslağı Hazır: DraftID={draft_id} Status=approved")
    finally:
        db.close()

    sep("3. Simulated CMS Dispatch (Varsayılan Akış)")
    db = SessionLocal()
    try:
        res = dispatch_cms_publication(db, TENANT, draft_id)
        check("status=success", res["status"] == "success")
        check("publication kaydı var", "publication" in res)
        check("cms_type=simulated", res["publication"]["cms_type"] == "simulated")
        print(f"     Yayın Kaydı: PostID={res['publication']['post_id']} URL={res['publication']['post_url']}")

        # DB status kontrolü
        updated_draft = db.query(KatipDraft).filter(KatipDraft.id == draft_id).first()
        check("KatipDraft status='published' oldu", updated_draft.status == "published")
    finally:
        db.close()

    sep("4. WordPress REST API Mock Testi (POST /wp-json/wp/v2/posts)")
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {
        "id": 1042,
        "link": "https://dental-clinic.example.com/blog/cms-test-konusu",
        "status": "publish",
        "date": "2026-07-21T17:00:00",
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        wp_res = publish_to_wordpress(
            wp_url="https://dental-clinic.example.com",
            username="admin",
            app_password="secret-app-password",
            title="WordPress Test Başlığı",
            content="WordPress Test İçeriği",
        )
        check("WordPress post_id=1042", wp_res["post_id"] == 1042)
        check("WordPress post_url doğru", "dental-clinic.example.com" in wp_res["post_url"])
        print(f"     WordPress Yayınlama Başarılı: PostID={wp_res['post_id']} URL={wp_res['post_url']}")

    sep("5. Webhook CMS Mock Testi")
    mock_wh_resp = MagicMock()
    mock_wh_resp.status_code = 200
    mock_wh_resp.text = '{"success": true}'

    with patch("httpx.Client.post", return_value=mock_wh_resp):
        wh_res = publish_to_webhook(
            webhook_url="https://api.custom-cms.com/webhooks/publish",
            payload={"event": "katip.draft.published", "draft_id": draft_id},
        )
        check("Webhook status_code=200", wh_res["status_code"] == 200)
        print(f"     Webhook Yayınlama Başarılı: Status={wh_res['status_code']}")

    print("\n" + "="*60)
    print("  TÜM CMS & WORDPRESS ENTEGRASYON TESTLERİ BAŞARIYLA GEÇTİ!")
    print("="*60)


if __name__ == "__main__":
    test_cms_publishing()
