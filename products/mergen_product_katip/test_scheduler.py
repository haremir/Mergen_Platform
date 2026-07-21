"""
Mergen Kâtip — Scheduler & Autonomy Verification Test
======================================================
Zamanlayıcının (scheduler.py) FOR UPDATE SKIP LOCKED mantığını,
otonom konu tüketimini ve hata durumunda topic'i 'failed' yapıp
tıkanmayı önleme davranışını test eder.

Çalıştır:
    $env:PYTHONPATH="core;packages;products;shared"
    uv run python products/mergen_product_katip/test_scheduler.py
"""

from __future__ import annotations

import sys
import uuid
from sqlalchemy.orm import Session

from mergen_core.database import SessionLocal
from mergen_product_katip.models import KatipTopicQueue, KatipDraft, KatipDraftVersion
from mergen_product_katip.scheduler import (
    fetch_and_lock_next_topic,
    process_single_pending_topic,
    run_scheduler_batch,
)
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


def test_katip_scheduler():
    sep("1. Veritabanı Hazırlığı ve Seed")
    db: Session = SessionLocal()
    try:
        seed_katip_pilot_data(db)
        print("  [OK] Seed tamamlandı.")
    finally:
        db.close()

    sep("2. Test Konusu Ekleme (Priority: 9)")
    db = SessionLocal()
    try:
        topic_title = f"Zamanlayıcı Otonomi Test Konusu - {uuid.uuid4().hex[:6]}"
        test_topic = KatipTopicQueue(
            tenant_id=TENANT,
            topic_title=topic_title,
            target_keywords=["otonomi", "zamanlayici", "test"],
            priority=9,
            status="pending",
        )
        db.add(test_topic)
        db.commit()
        db.refresh(test_topic)
        topic_id = test_topic.id
        print(f"  [OK] Konu eklendi: ID={topic_id} Title='{topic_title}' Priority=9 Status=pending")
    finally:
        db.close()

    sep("3. fetch_and_lock_next_topic() (SKIP LOCKED Kontrolü)")
    db = SessionLocal()
    try:
        locked_topic = fetch_and_lock_next_topic(db)
        check("Konu başarıyla kilitlendi", locked_topic is not None)
        check("Kilitlenen konu pending durumunda", locked_topic.status == "pending")
        print(f"     Kilitlenen Konu ID: {locked_topic.id} - '{locked_topic.topic_title}'")
    finally:
        db.close()

    sep("4. run_scheduler_batch() — Otonom İşleme")
    count = run_scheduler_batch(max_topics=3)
    print(f"  [OK] Scheduler turunda işlenen konu sayısı: {count}")

    sep("5. İşlenen Konunun ve Üretilen Taslağın Doğrulanması")
    db = SessionLocal()
    try:
        updated_topic = db.query(KatipTopicQueue).filter(KatipTopicQueue.id == topic_id).first()
        check("Konu status='done' oldu", updated_topic.status == "done")
        check("processed_at seti yapıldı", updated_topic.processed_at is not None)

        draft = db.query(KatipDraft).filter(KatipDraft.topic_id == topic_id).first()
        check("KatipDraft üretildi", draft is not None)

        if draft:
            version = db.query(KatipDraftVersion).filter(KatipDraftVersion.draft_id == draft.id).first()
            check("KatipDraftVersion v1 üretildi", version is not None)
            check("Kelime sayısı > 0", version.word_count > 0)
            print(f"     Üretilen Taslak ID: {draft.id}  Versiyon: v{version.version_number}  Kelime: {version.word_count}")
    finally:
        db.close()

    sep("6. Hata Yönetimi & Tıkanma Önleme Testi (Failed Topic)")
    db = SessionLocal()
    try:
        # Hata üretecek bozuk konu (geçersiz veritabanı durumu taklidi)
        broken_topic = KatipTopicQueue(
            tenant_id=TENANT,
            topic_title="Hata Test Konusu (Tıkanma Önleme)",
            priority=99,
            status="pending",
        )
        db.add(broken_topic)
        db.commit()
        db.refresh(broken_topic)
        broken_id = broken_topic.id

        # generate_draft_for_topic fonksiyonunu geçici olarak hata verdirtmek için taklit et
        from unittest.mock import patch
        with patch("mergen_product_katip.scheduler.generate_draft_for_topic", side_effect=RuntimeError("LLM Gateway Zaman Aşımı (Timeout)")):
            process_single_pending_topic(db)

        b_topic = db.query(KatipTopicQueue).filter(KatipTopicQueue.id == broken_id).first()
        check("Bozuk konu status='failed' yapıldı (tıkanma önlendi)", b_topic.status == "failed")
        check("retry_count arttı", b_topic.retry_count >= 1)
        check("error_message kaydedildi", bool(b_topic.error_message))
        print(f"     Failed Konu Hata Mesajı: {b_topic.error_message[:120]}...")
    finally:
        db.close()

    print("\n" + "="*60)
    print("  TÜM SCHEDULER & OTONOMİ TESTLERİ BAŞARIYLA GEÇTİ!")
    print("="*60)


if __name__ == "__main__":
    test_katip_scheduler()
