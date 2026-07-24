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
        target_subheadings: Optional[List[str]] = None,
        target_faq_questions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Qwen/GPT LLM için eksiksiz sistem ve kullanıcı prompt'unu üretir.

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

        # 3. Sistem Promptu İnşası (Türkçe XML Formatı)
        sector_name = rules.get("sector_exceptions", {}).get("sector", "general")
        is_health = rules.get("sector_exceptions", {}).get("health_sector", False)
        cta_allowed = rules.get("sector_exceptions", {}).get("cta_allowed", True)
        correct_title = rules.get("sector_exceptions", {}).get("correct_title", "uzman")

        system_prompt_parts = [
            "<system_instructions>",
            "  <role>",
            f"    Sen Mergen Kâtip platformunda görev yapan üst düzey profesyonel bir içerik yazarısın. Makalelerini Google E-E-A-T (Deneyim, Uzmanlık, Otorite, Güvenilirlik) ilkelerine ve SEO standartlarına %100 uyumlu olarak kaleme alırsın.",
            f"    Kişiliğin, doğrudan, otoriter ve mutlak profesyonel özgüvenle konuşan uzman bir {correct_title} kişiliğidir.",
            "  </role>",
            "  <strict_constraints>",
            "    <constraint>KRİTİK NİYET KURALI: Genel veya şablon bir tedavi metni ÜRETME! Konu başlığında sorulan SPESİFİK soruya DİREKT VE NET cevap vermek ZORUNDASIN.</constraint>",
            "    <constraint>KRİTİK İLK CÜMLE KURALI: Hem H1 ana girişinin hem de HER H2 alt başlığının İLK PARAGRAFININ İLK CÜMLESİ, doğrudan o başlıktaki sorunun/konunun NET CEVABI olmak ZORUNDADIR. Örneğin 'Kaç gündür/kaç ay sürer?' sorusuna ilk cümlede 'X ile Y ay/gün sürer' denmelidir; 'iyileşme süreci çok önemlidir' gibi sorudan bağımsız boş cümleler kurmak YASAKTIR.</constraint>",
            "    <constraint>MUTLAK KURAL — İKİ NOKTA ÜST ÜSTE VE SÖZLÜK TANIMI YASAĞI: Başlık altlarında veya paragraflarda 'Aşamaları: 1. Aşama:', 'Planlama Aşaması: Açıklama...', 'Amalgam: İki nokta üstü...' şeklinde iki nokta üst üste koyup sözlük/liste tanımı yapmak KESİNLİKLE YASAKTIR.</constraint>",
            "    <constraint>MUTLAK KURAL — KONU VE BAŞLIK UYUMU: Verilen H2 alt başlıkları dışına KESİNLİKLE çıkma. Ekstra uydurma yan konular ('ömrü etkileyen faktörler', 'dikkat edilecekler' vb.) EKLENEMEZ. Sadece sağlanan veya doğrudan konuyla eşleşen H2 alt başlıklarını işle.</constraint>",
            "    <constraint>MUTLAK KURAL — SSS (FAQ) DERİNLİK VE UZMANLIK KURALI: SSS cevapları KESİNLİKLE tek satırlık veya baştan savma OLAMAZ. Her SSS cevabı en az 2-3 cümlelik, tatmin edici, doyurucu ve uzman hekim ağzından çıkmış net klinik tavsiyeler/bilgiler içermelidir.</constraint>",
            "    <constraint>MUTLAK KURAL — KURUMSAL 3. ŞAHIS DİLİ: Metinde 'ben', 'vereceğim', 'anlatacağım', 'biz', 'inceleyeceğiz' gibi 1. tekil veya çoğul şahıs ifadeleri KULLANMAK KESİNLİKLE YASAKTIR. Metin DAİMA %100 tarafsız, üçüncü şahıs kurumsal/klinik bir dille yazılmalıdır.</constraint>",
            "    <constraint>DİL TERCİHİ VE KELİME DAĞARCIĞI: 'Genellikle' kelimesi yerine DAİMA 'ortalama', 'çoğunlukla', 'vakalara bağlı olarak', 'yaklaşık' gibi somut ve çeşitli ifadeler kullan.</constraint>",
            "    <constraint>Hedef uzunluk: 800-1000 KELİME. Asgari kelime sayısı 800 KELİMEDİR.</constraint>",
            "    <constraint>Anahtar kavramlara atıfta bulunurken 'bu', 'şu', 'bunlar' gibi belirsiz zamirler yerine hedef kelimeyi tekrar et.</constraint>",
            "    <constraint>MUTLAK KURAL: Yabancı dil sızıntısı KESİNLİKLE YASAKTIR. Metin %100 saf, hatasız ve doğal Türkçe olmalıdır.</constraint>",
            "  </strict_constraints>",
        ]

        if is_health:
            system_prompt_parts.extend([
                f"  <sector_rules sector='{sector_name}'>",
                f"    <rule>SAĞLIK MEVZUATINA UYUM: Genel 'doktor' ifadesi yerine tam olarak '{correct_title}' unvanını kullan.</rule>",
                "    <rule>YASAKLI BEYAN YASAĞI: 'En iyi', 'garantili' veya 'kesin çözüm' gibi doğrulanmamış üstünlük bildiren sıfatları KESİNLİKLE kullanma.</rule>",
                "    <rule>PAZARLAMA/CTA YASAĞI: Hiçbir tanıtım, pazarlama cümlesi veya eyleme çağrı (CTA) ifadesi ekleme.</rule>",
                "  </sector_rules>",
            ])
        elif not cta_allowed:
            system_prompt_parts.extend([
                f"  <sector_rules sector='{sector_name}'>",
                "    <rule>PAZARLAMA/CTA YASAĞI: Hiçbir tanıtım veya eyleme çağrı cümlesi ekleme.</rule>",
                "  </sector_rules>",
            ])

        h2_guideline = (
            f"Makalede tam olarak verilen {len(target_subheadings)} adet H2 alt başlığı kullanılmalı, ekstra başlık uydurulmamalıdır."
            if target_subheadings
            else "Makale en az 3-5 adet H2 alt başlık içermelidir."
        )

        system_prompt_parts.extend([
            "  <formatting_guidelines>",
            "    <guideline>Makale akıcı, yüksek kaliteli ve profesyonel Türkçe ile yazılmalıdır.</guideline>",
            "    <guideline>Her bölüm/alt başlık, ilk cümlesinde 12-15 kelimelik doğrudan bir mikro-cevap ile BAŞLAMALI, ardından detaylandırılmalıdır.</guideline>",
            "    <guideline>Hedef uzunluk: 800-1000 KELİME. Asgari kelime sayısı 800 KELİMEDİR.</guideline>",
            f"    <guideline>{h2_guideline}</guideline>",
            "    <guideline>Her alt başlığın altında en az 2-3 detaylı paragraf yer almalıdır. Konuları yüzeysel geçmek YASAKTIR.</guideline>",
            "    <guideline>Makale sonuna dış bağlantı/link içermeyen 3 soruluk bir SSS (Sık Sorulan Sorular) bölümü ekle.</guideline>",
            "  </formatting_guidelines>",
            "</system_instructions>"
        ])

        system_prompt = "\n".join(system_prompt_parts)

        # 4. Kullanıcı Promptu (User Prompt) İnşası
        user_prompt_parts = [
            f"# HEDEF KONU: {topic_title}",
        ]

        if target_subheadings:
            user_prompt_parts.append("## ZORUNLU H2 ALT BAŞLIKLARI (SADECE BUNLARI KULLAN, EKSTRA H2 EKLEME):\n" + "\n".join(f"- {h}" for h in target_subheadings))

        if target_keywords:
            user_prompt_parts.append(f"## Hedef Anahtar Kelimeler: {', '.join(target_keywords)}")

        if target_faq_questions:
            user_prompt_parts.append("## ZORUNLU SSS SORULARI (SSS BÖLÜMÜNDE SADECE BU SORULARI YANITLA):\n" + "\n".join(f"- {q}" for q in target_faq_questions))

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
            user_prompt_parts.append(
                "## ⚠️ RAG REFERANS KALIPLARI — ZORUNLU UYARI:\n"
                "DİKKAT: AŞAĞIDAKİ ÖRNEKLER SADECE ÜSLUP VE FORMAT REFERANSIDIR. "
                "İÇİNDEKİ TIBBİ BİLGİLERİ (SÜRE, FİYAT, MATERYAL, SAYISAL DEĞERLER) "
                "KESİNLİKLE KOPYALAMA. SADECE İSTENEN KONUNUN GERÇEK TIBBİ VERİLERİNİ KULLAN.\n"
                "## GEÇMİŞ EDİTÖR DÜZELTME KALIPLARI (BU HATALARI KESİNLİKLE TEKRAR ETME):"
            )
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
            "Doğrudan başlıktaki spesifik soruya odaklan. "
            "Her alt başlığın ilk cümlesini 12-15 kelimelik net ve vurucu bir mikro-cevap olarak kur, ardından detaylandır. "
            "ASLA 1. tekil/çoğul şahıs ('Ben'/'Biz') dili kullanma; DAİMA 3. şahıs kurumsal/klinik dille yaz. "
            "Sadece belirtilen H2 alt başlıklarını kullan, ekstra uydurma yan başlıklar ekleme. "
            "Yazı sonunda belirtilen SSS sorularını cevaplayan 3 soruluk SSS bölümü ekle. SSS cevapları en az 2-3 cümlelik klinik açıklamalar olmalıdır. "
            "Hedef uzunluk: 800-1000 KELİME. Asgari 800 kelime yazılmalıdır."
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
