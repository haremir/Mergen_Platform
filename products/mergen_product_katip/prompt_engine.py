"""
mergen_product_katip.prompt_engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

KatipPromptEngine — BrandGuide, RAG Revizyon Kalıpları, Referans Makaleler ve
Sektör Kurallarını birleştirerek Qwen LLM için zengin prompt inşa eder.

Özellikler:
- RAG tabanlı revizyon kalıpları eşleştirmesi (konuyla semantik alakalı top-k kalıp)
- Token bütçe kontrolü (BrandGuide max 800 token)
- Sağlık / YMYL sektörü kısıtlamaları (CTA yasağı, doktor yerine diş hekimi terminolojisi)
- Paragraf başı 12-15 kelimelik mikro-cevap kuralı

Author: Mergen Platform -- Kâtip Team
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from mergen_core.rag_engine import embed
from mergen_product_katip.models import (
    KatipBrandGuide,
    KatipExampleArticle,
    KatipRevisionPattern,
)

logger = logging.getLogger(__name__)

# Maksimum kural token bütçesi
MAX_BRAND_GUIDE_TOKENS = 800


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """İki float vektör arasındaki Kosinüs Benzerliğini hesaplar."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = sum(a * a for a in v1) ** 0.5
    norm_b = sum(b * b for b in v2) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class KatipPromptEngine:
    """Mergen Kâtip için özel prompt üretici servis."""

    def __init__(self, max_revision_patterns: int = 5, max_example_articles: int = 2):
        self.max_revision_patterns = max_revision_patterns
        self.max_example_articles = max_example_articles

    def _fetch_brand_guide(self, db: Session, tenant_id: str) -> Optional[KatipBrandGuide]:
        return db.query(KatipBrandGuide).filter(KatipBrandGuide.tenant_id == tenant_id).first()

    def _find_relevant_patterns(
        self, db: Session, tenant_id: str, topic_title: str, top_k: int = 5
    ) -> List[KatipRevisionPattern]:
        """Konu başlığına en yakın semantik revizyon kalıplarını RAG ile getirir."""
        patterns = db.query(KatipRevisionPattern).filter(KatipRevisionPattern.tenant_id == tenant_id).all()
        if not patterns:
            return []

        topic_vec = embed(topic_title)
        scored: List[Tuple[float, KatipRevisionPattern]] = []

        for p in patterns:
            if p.embedding and isinstance(p.embedding, list):
                score = cosine_similarity(topic_vec, p.embedding)
                scored.append((score, p))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_k]]

    def _find_relevant_articles(
        self, db: Session, tenant_id: str, topic_title: str, top_k: int = 2
    ) -> List[KatipExampleArticle]:
        """Konu başlığına en yakın örnek referans makaleleri RAG ile getirir."""
        articles = db.query(KatipExampleArticle).filter(KatipExampleArticle.tenant_id == tenant_id).all()
        if not articles:
            return []

        topic_vec = embed(topic_title)
        scored: List[Tuple[float, KatipExampleArticle]] = []

        for a in articles:
            if a.embedding and isinstance(a.embedding, list):
                score = cosine_similarity(topic_vec, a.embedding)
                scored.append((score, a))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_k]]

    def build_prompt(
        self,
        db: Session,
        tenant_id: str,
        topic_title: str,
        target_keywords: Optional[List[str]] = None,
        additional_feedback: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Qwen LLM için eksiksiz sistem ve kullanıcı prompt'unu üretir.

        Returns:
            {
                "system_prompt": str,
                "user_prompt": str,
                "full_prompt_text": str,
                "token_budget_passed": bool,
                "patterns_used": int,
                "articles_used": int
            }
        """
        # 1. BrandGuide Çek
        brand_guide = self._fetch_brand_guide(db, tenant_id)
        rules = brand_guide.rules_json if brand_guide else {}
        token_count = brand_guide.token_count if brand_guide else 0

        # Token Budget Kontrolü
        budget_passed = token_count <= MAX_BRAND_GUIDE_TOKENS
        if not budget_passed:
            logger.warning(
                "Tenant %s BrandGuide token bütçesini aştı (%d > %d)! Kısıtlama uygulanacak.",
                tenant_id, token_count, MAX_BRAND_GUIDE_TOKENS
            )

        # 2. RAG ile İlgili Revizyon Kalıpları ve Örnekleri Çek
        rel_patterns = self._find_relevant_patterns(db, tenant_id, topic_title, self.max_revision_patterns)
        rel_articles = self._find_relevant_articles(db, tenant_id, topic_title, self.max_example_articles)

        # 3. Sistem Promptu İnşası
        sector_info = rules.get("sector_exceptions", {})
        is_health = sector_info.get("health_sector", False)
        cta_allowed = sector_info.get("cta_allowed", True)
        correct_title = sector_info.get("correct_title", "uzman")

        system_prompt_parts = [
            "Sen Mergen Kâtip platformunda görev yapan, SEO ve Google E-E-A-T (Deneyim, Uzmanlık, Otorite, Güvenilirlik) standartlarına %100 hakim kıdemli bir profesyonel içerik yazarısın.",
            f"Yazıların doğrudan uzman {correct_title} ağzından, kesin ve güven veren bir tonla yazılmalıdır.",
            "ZORUNLU KURAL VE YASAKLI KELİMELER: Sadece somut verilerle uzman ağzıyla konuş. Belirsizlik ve muğlaklık içeren kelimeleri ('bazı', 'genellikle', 'gibi', 'benzer', 'destekler', 'sağlar') KESİNLİKLE KULLANMA! 'Genellikle' kelimesi yerine somut oran veya aralık ver ('ortalama %3-4', '3 ile 4 arasında'). 'Bu, şu, bunlar' belirsiz zamirleri yerine atıfta bulunulan anahtar kelimeyi açıkça tekrar yaz.",
        ]

        if is_health:
            system_prompt_parts.append(
                "ÖNEMLİ (SAĞLIK SEKTÖRÜ İSTİSNASI): Sağlık mevzuatı gereği yazıda 'doktor' kelimesi yerine kesinlikle 'diş hekimi' kullanılmalıdır. Asla kanıtlanmamış üstünlük iddiaları ('en iyi', 'garantili', 'kesin çözüm') ve eyleme çağrı (CTA) CÜMLELERİ KULLANILMAMALIDIR!"
            )
        elif not cta_allowed:
            system_prompt_parts.append("ÖNEMLİ: Bu sektörde CTA (eyleme çağrı) cümleleri kullanmak yasaktır.")

        system_prompt = "\n\n".join(system_prompt_parts)

        # 4. Kullanıcı Promptu (User Prompt) İnşası
        user_prompt_parts = [
            f"# HEDEF KONU: {topic_title}",
        ]

        if target_keywords:
            user_prompt_parts.append(f"## Hedef Anahtar Kelimeler: {', '.join(target_keywords)}")

        # Kurallar Bölümü
        user_prompt_parts.append("## MARKA VE İÇERİK KURAL SETİ:")

        tone_rules = rules.get("tone_rules", [])
        if tone_rules:
            user_prompt_parts.append("### Ton ve Dil Kuralları:\n" + "\n".join(f"- {r}" for r in tone_rules))

        struct_rules = rules.get("structure_rules", [])
        if struct_rules:
            user_prompt_parts.append("### Yapı ve Format Kuralları:\n" + "\n".join(f"- {r}" for r in struct_rules))

        seo_rules = rules.get("seo_rules", [])
        if seo_rules:
            user_prompt_parts.append("### SEO Kuralları:\n" + "\n".join(f"- {r}" for r in seo_rules))

        # Revizyon Kalıpları Bölümü (RAG Çıktısı)
        if rel_patterns:
            user_prompt_parts.append("## GEÇMİŞ EDİTÖR DÜZELTME KALIPLARI (BU HATALARI KESİNLİKLE TEKRAR ETME):")
            for idx, pat in enumerate(rel_patterns, 1):
                rule_label = getattr(pat, "general_rule", None) or (
                    pat.pattern_tags[0] if getattr(pat, "pattern_tags", None) else "Editör Kuralı"
                )
                pattern_block = (
                    f"Kalıp #{idx} [{rule_label}]\n"
                    f"  - Yanlış Kullanım: {pat.original_excerpt[:150]}\n"
                    f"  - Onaylanan Doğru Kullanım: {pat.revised_excerpt[:200]}"
                )
                user_prompt_parts.append(pattern_block)

        # Editör Revizyon Notu (Var İse)
        if additional_feedback:
            user_prompt_parts.append(
                f"## EDİTÖRÜN YENİ REVİZYON NOTU (ÖNCELİKLİ UYGULA):\n\"{additional_feedback}\""
            )

        # Çıktı Formatı Talimatı
        user_prompt_parts.append(
            "## ÇIKTI FORMATI:\n"
            "Yazıyı Markdown formatında yaz. H1 başlığı ile başla. "
            "Her alt başlığın ilk cümlesini 12-15 kelimelik net ve vurucu bir mikro-cevap olarak kur, ardından detaylandır. "
            "Yazı sonunda 3 soruluk SSS (Sık Sorulan Sorular) bölümü ekle. "
            "Toplam kelime sayısı ortalama 600-650 kelime arasında olmalıdır."
        )

        user_prompt = "\n\n".join(user_prompt_parts)
        full_text = f"=== SYSTEM ===\n{system_prompt}\n\n=== USER ===\n{user_prompt}"

        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "full_prompt_text": full_text,
            "token_budget_passed": budget_passed,
            "patterns_used": len(rel_patterns),
            "articles_used": len(rel_articles),
        }
