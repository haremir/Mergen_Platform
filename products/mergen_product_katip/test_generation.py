"""
mergen_product_katip.test_generation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Doğrulama ve End-to-End Test Skripti.

Adımlar:
1. Seed skriptini çalıştırır ve pilot verilerini PostgreSQL'e yazar.
2. KatipPromptEngine'i çağırıp RAG ile kaç revizyon kalıbının seçildiğini doğrular.
3. Konu kuyruğundan pending konuyu çekip generate_draft_for_topic() ile v1 taslağını üretir.
4. KatipDraft, KatipDraftVersion ve KatipGenerationLog tablolarını sorgulayıp sonuçları raporlar.

Kullanım:
    uv run python -m mergen_product_katip.test_generation
"""

from __future__ import annotations

import logging
import sys

from sqlalchemy.orm import Session

from mergen_core.database import SessionLocal
from mergen_product_katip.draft_service import generate_draft_for_topic
from mergen_product_katip.models import (
    KatipBrandGuide,
    KatipDraft,
    KatipDraftVersion,
    KatipGenerationLog,
    KatipRevisionPattern,
    KatipTopicQueue,
)
from mergen_product_katip.prompt_engine import KatipPromptEngine
from mergen_product_katip.seed import PILOT_TENANT_ID, seed_katip_pilot_data

logger = logging.getLogger("test_generation")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def run_e2e_test():
    print("\n" + "=" * 80)
    print("  MERGEN KÂTİP — FAZ 2 PROMPT ENGINE & DRAFT GENERATION END-TO-END TEST  ")
    print("=" * 80 + "\n")

    with SessionLocal() as db:
        # 1. Seed Verilerini Yükle
        print("1. Seed verileri yükleniyor...")
        seed_katip_pilot_data(db)

        # 2. BrandGuide ve Revizyon Kalıplarını Doğrula
        bg = db.query(KatipBrandGuide).filter(KatipBrandGuide.tenant_id == PILOT_TENANT_ID).first()
        pattern_count = db.query(KatipRevisionPattern).filter(KatipRevisionPattern.tenant_id == PILOT_TENANT_ID).count()

        print(f"  [OK] BrandGuide: Bulundu (Tahmini Token: {bg.token_count})")
        print(f"  [OK] Revizyon Kalıpları: {pattern_count} adet veritabanında mevcut.")

        # 3. Prompt Engine Test Et (RAG Semantik Arama)
        engine = KatipPromptEngine(max_revision_patterns=5)
        test_topic = "Yamuk Dişler Nasıl Düzeltilir?"
        prompt_info = engine.build_prompt(db, PILOT_TENANT_ID, test_topic, ["şeffaf plak", "ortodonti"])

        print("\n2. Prompt Engine & RAG Testi:")
        print(f"  [OK] Konu: '{test_topic}'")
        print(f"  [OK] Token Bütçe Geçti mi?: {prompt_info['token_budget_passed']}")
        print(f"  [OK] RAG İle Eşleşen Revizyon Kalıbı Sayısı: {prompt_info['patterns_used']}")
        print(f"  [OK] Sistem Promptu Uzunluğu: {len(prompt_info['system_prompt'])} karakter")
        print(f"  [OK] Kullanıcı Promptu Uzunluğu: {len(prompt_info['user_prompt'])} karakter")

        # 4. Kuyruktan İş Bekleyen Konuyu Çek ve Taslak Üret
        print("\n3. Taslak Üretim Servisi (generate_draft_for_topic) Çalıştırılıyor...")
        topic = db.query(KatipTopicQueue).filter(
            KatipTopicQueue.tenant_id == PILOT_TENANT_ID,
            KatipTopicQueue.status == "pending"
        ).first()

        if not topic:
            # Sıfırla test için
            topic = db.query(KatipTopicQueue).filter(KatipTopicQueue.tenant_id == PILOT_TENANT_ID).first()
            topic.status = "pending"
            db.commit()

        print(f"  İşlenen Konu ID: {topic.id} - '{topic.topic_title}'")

        result = generate_draft_for_topic(db, PILOT_TENANT_ID, topic.id, prompt_engine=engine)

        print("\n4. Üretim Sonuçları:")
        print(f"  [OK] Durum: {result['status']}")
        print(f"  [OK] Draft ID: {result['draft_id']}")
        print(f"  [OK] Version ID: {result['version_id']} (v{result['version_number']})")
        print(f"  [OK] Kelime Sayısı: {result['word_count']}")
        print(f"  [OK] Model: {result['model_used']}")
        print(f"  [OK] Latency: {result['latency_ms']} ms")
        print(f"  [OK] Toplam Token Tahmini: {result['token_count']}")

        # 5. Veritabanı Kayıtlarını Doğrula
        draft = db.query(KatipDraft).filter(KatipDraft.id == result["draft_id"]).first()
        version = db.query(KatipDraftVersion).filter(KatipDraftVersion.id == result["version_id"]).first()
        gen_log = db.query(KatipGenerationLog).filter(KatipGenerationLog.draft_version_id == version.id).first()

        assert draft is not None, "Draft DB'de bulunamadı!"
        assert version is not None, "DraftVersion DB'de bulunamadı!"
        assert gen_log is not None, "GenerationLog DB'de bulunamadı!"
        assert topic.status == "done", "Topic status 'done' olmadı!"

        print("\n5. Veritabanı Bütünlüğü:")
        print("  [OK] KatipDraft kaydı doğrulandı.")
        print("  [OK] KatipDraftVersion v1 kaydı doğrulandı.")
        print("  [OK] KatipGenerationLog kaydı doğrulandı.")
        print("  [OK] KatipTopicQueue status='done' doğrulandı.")

        print("\n" + "=" * 80)
        print("  YAZILAN TASLAK İÇERİK ÖRNEĞİ (İLK 300 KARAKTER):")
        print("=" * 80)
        print(version.content[:300] + "...\n")
        print("SUCCESS! E2E Test başarıyla tamamlandı.\n")


if __name__ == "__main__":
    run_e2e_test()
