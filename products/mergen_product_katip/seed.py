"""
mergen_product_katip.seed
~~~~~~~~~~~~~~~~~~~~~~~~~

Pilot veri yükleme skripti (Dental Clinic / Diş Kliniği Sektörü).

Masaüstündeki ham verileri okur ve PostgreSQL veritabanına yükler:
- Pilot tenant ("pilot-dental-clinic-01")
- BrandGuide (Yapılandırılmış ton, yapı, SEO ve sağlık sektörü kuralları)
- 15 adet Revizyon Kalıbı (before/after/rule_summary + vector embedding)
- Örnek referans makaleler
- Pilot Konu Kuyruğu (3 adet test konusu)

Kullanım:
    uv run python -m mergen_product_katip.seed
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from mergen_core.database import SessionLocal, engine
from mergen_core.db_models import DBTenant
from mergen_core.rag_engine import embed
from mergen_product_katip.models import (
    KatipBrandGuide,
    KatipExampleArticle,
    KatipRevisionPattern,
    KatipTopicQueue,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Pilot Tenant ID
PILOT_TENANT_ID = "pilot-dental-clinic-01"


# ---------------------------------------------------------------------------
# Ham Veri Tanımları (yeni klasör/'den çekildi)
# ---------------------------------------------------------------------------

BRAND_GUIDE_RULES = {
    "tone_rules": [
        "'Genellikle' kelimesini kullanma — belirsizlik yaratır. Somut aralık ver ('ortalama %3-4 oranında', '3 ile 4 arasında').",
        "'Bu, şu, bunlar, onlar' gibi belirsiz zamirler yerine anahtar kelimeyi açıkça tekrar et.",
        "Başlıklarda 'bazı, gibi, benzer' belirsiz kelimeler kullanma.",
        "'Destekler, sağlar' gibi içi boş cümle bitişlerinden kaçın; somut sonuçla bitir.",
        "Tanısal/kesin ifadelerle uzmanlık ve güven vurgusu yap (E-E-A-T).",
        "Liste cevaplarında marka adını öne çıkarma; doğal akışta ölçülü kullan.",
        "Cümleler gerçek bir uzman diş hekiminin konuşma tarzını yansıtmalı — robotik şablonlardan kaçın.",
        "Kanıtlanmamış üstünlük sıfatları ('uzman', 'en iyi') tek başına kullanılmamalı.",
        "Doğru terminoloji kullan: 'doktor' değil 'diş hekimi'."
    ],
    "structure_rules": [
        "Hedef uzunluk ortalama 600-650 kelime (minimum 400+ kelime).",
        "Yüksek hacimli konularda 7-8 alt başlık idealdir.",
        "SSS bölümleri 2-3 paragraf, çok net ve kısa olmalı (PAA kutuları için).",
        "İlk sorguya paragraf formatında doğrudan cevap ver; sonraki sorgulara madde/liste formatında geç.",
        "Her alt başlığın ilk cümlesi mikro-cevap olmalı (12-15 kelimelik net cevap), ardından detay verilmeli.",
        "SSS bölümünden dışarıya link verme.",
        "Tablo formatı uygun alt sorgularda (özellikle fiyat aralıklarında) kullanılmalı.",
        "Terim tanımlarını tekrar etme; parantez içi kısa tanım yeterlidir ('pembe estetik (diş eti estetiği)').",
        "Açıklanmamış 'Not:' gibi belirsiz bölümler ekleme."
    ],
    "seo_rules": [
        "Ana kelimeyi %3-4 oranında doğal kullan; LSI/varyasyon kelimeleri ekle ('protez diş' -> 'diş protezi', 'takma diş').",
        "İç linkleme: birden fazla sayfaya link verilecekse ayrı alt başlıklarda ver.",
        "Hacmi olmayan (0 hacimli) kelimeleri link hedefi yapma.",
        "Featured snippet için soru-cevap formatı kullan (kısa alt başlık + net kısa cevap)."
    ],
    "sector_exceptions": {
        "sector": "dental_clinic",
        "health_sector": True,
        "cta_allowed": False,  # Sağlık sektöründe CTA yasaktır!
        "mandatory_review": True,  # YMYL sektörü — insan incelemesi zorunlu
        "correct_title": "diş hekimi"
    }
}

REVISION_PATTERNS_DATA = [
    {
        "title": "Yamuk Dişler Nasıl Düzeltilir?",
        "original_excerpt": "Uzun ve dolaylı süreç anlatımı.",
        "revised_excerpt": "Yamuk dişler şeffaf plak (telsiz ortodonti), metal/porselen braketler veya estetik lamine kaplamalar ile düzeltilebilir. Tedavi yöntemi çapraşıklık derecesine göre diş hekimi tarafından belirlenir.",
        "pattern_tags": ["uzunluk", "mikro-cevap", "diş_hekimliği"],
        "general_rule": "Sorguya kısa ve vurucu cevap ver; gereksiz uzatma."
    },
    {
        "title": "Çarpık Diş Neden Olur?",
        "original_excerpt": "Genel çene yapısı ve uzun tarihçe anlatımı.",
        "revised_excerpt": "Çarpık diş genetik faktörler, erken süt dişi kaybı, parmak emme alışkanlığı veya çene darlığı nedeniyle oluşur.",
        "pattern_tags": ["giriş", "hızlı-cevap"],
        "general_rule": "Cevabı hızlı ver; detaya gireceksen kısa gir, çok uzatma."
    },
    {
        "title": "Sık Sorulan Sorular (SSS Formatı)",
        "original_excerpt": "SSS kısmında uzun akademik paragraflar.",
        "revised_excerpt": "SSS cevapları detaya girmeden 2-3 cümlelik temel bilgi vermeli; PAA kutuları için net kalınmalı.",
        "pattern_tags": ["sss", "paa", "format"],
        "general_rule": "SSS cevapları detaya girmeden ziyaretçiye hızlı temel bilgi vermeli."
    },
    {
        "title": "Diş Çektirmek Acıtır mı?",
        "original_excerpt": "Diş çektirmek acıtmaz. Lokal anestezi işlemi ile çekilecek diş uyuşturulur. Bu işlem birkaç saniye içinde tamamlanır ve 1-2 dakika arasında etkisini göstermeye başlar...",
        "revised_excerpt": "Diş çekimi lokal anestezi altında yapıldığı için işlem sırasında herhangi bir acı veya ağrı hissedilmez. Sadece hafif bir baskı hissi oluşabilir.",
        "pattern_tags": ["giriş", "ikna", "eeat"],
        "general_rule": "Giriş cümlesi okuyucuyu ilk anda tatmin edecek kadar güçlü ve ikna edici olmalı."
    },
    {
        "title": "Diş Çektirmek Acılı Bir İşlem Midir?",
        "original_excerpt": "Diş çektirmek acılı bir işlem değildir. Hastalar korkmamalıdır çünkü...",
        "revised_excerpt": "Lokal anestezi uygulandığı için diş çekimi acısız bir işlemdir.",
        "pattern_tags": ["alt-başlık", "format"],
        "general_rule": "Alt başlıklar SSS formatında değil, doğrudan sorguya net cevapla giriş yapmalı."
    },
    {
        "title": "Diş Çekiminden Sonra Ne Olur?",
        "original_excerpt": "Diş çekiminin ardından hastalar evde geçirecekleri iyileşme sürecini dikkatli yönetirlerse acı yaşamadan atlatabilirler. İlk 24 ila 48 saat en hassas dönemdir...",
        "revised_excerpt": "Diş çekiminden sonra bölgede hafif sızı ve pıhtı oluşumu gözlenir. İlk 24 saat boyunca tükürmemek, sıcak gıda tüketmemek ve çekim bölgesini zorlamamak gerekir.",
        "pattern_tags": ["sorgu-uyumu", "doktor-notu"],
        "general_rule": "Cevap başlıktaki sorgunun birebir karşılığı olmalı; dolaylı anlatımla sorguyu es geçme."
    },
    {
        "title": "Pembe Estetik Nedir?",
        "original_excerpt": "Pembe estetik, diş eti estetiği anlamına gelir ve estetik bir gülüşe sahip olmak isteyen kişilerin başvurduğu bir tedavi yöntemidir. Başta pembe estetik, diş eti estetiği anlamına gelir.",
        "revised_excerpt": "Pembe estetik (diş eti estetiği), diş etlerinin seviye, simetri ve renk açısından estetik olarak düzenlenmesi işlemidir.",
        "pattern_tags": ["tanım", "tekrar-engelleme"],
        "general_rule": "Terim tanımlarını tekrar etme; anlam bütünlüğünü bozmadan parantez içi kısa tanım kullan."
    },
    {
        "title": "Pembe Estetiği Kimler Yaptırabilir?",
        "original_excerpt": "Gülüşünden memnun olmayan ve diş eti sorunları yaşayan herkes pembe estetik yaptırabilir çünkü estetik bir gülüş çok önemlidir...",
        "revised_excerpt": "Pembe estetiği şu kişiler yaptırabilir:\n- Diş eti gülürken fazla görünenler (Gummy Smile)\n- Diş eti seviyeleri düzensiz olanlar\n- Diş eti çekilmesi veya renk değişimi yaşayan yetişkinler.",
        "pattern_tags": ["liste-formatı", "uygunluk"],
        "general_rule": "'Kimler yaptırabilir' sorularına doğrudan liste formatında net cevap ver."
    },
    {
        "title": "Pembe Estetik Yöntemleri Nelerdir?",
        "original_excerpt": "Birçok farklı yöntem mevcuttur. Diş hekimi seçer...",
        "revised_excerpt": "Pembe estetik yöntemleri şunlardır: Gingivektomi (diş eti kesimi), Gingivoplasti (diş eti şekillendirme) ve küretaj (diş eti temizliği).",
        "pattern_tags": ["featured-snippet", "yöntemler"],
        "general_rule": "Google featured snippet format ve uzunluğunu referans al."
    },
    {
        "title": "Pembe Estetik Nasıl Yapılır?",
        "original_excerpt": "Pembe estetik tedavisi bir dizi işlem ile yapılmaktadır. Diş kliniğinde uzman bir diş hekimi...",
        "revised_excerpt": "Pembe estetik, lokal anestezi altında diyot lazer veya koter cihazı ile diş etlerinin milimetrik olarak şekillendirilmesiyle uygulanır. İşlem ortalama 30-45 dakika sürer.",
        "pattern_tags": ["uzman-dili", "eeat"],
        "general_rule": "Cümle gerçek bir uzman diş hekiminin konuşma tarzını yansıtmalı (E-E-A-T)."
    },
    {
        "title": "Pembe Estetik Tedavisinde İyileşme Süreci Ne Kadardır?",
        "original_excerpt": "İyileşme süreci kısadır.\nNot: İyileşme süresince sigara içilmemelidir.",
        "revised_excerpt": "Pembe estetik sonrası doku iyileşmesi ortalama 7-10 günde tamamlanır. Lazerli uygulamalarda hasta aynı gün günlük hayatına dönebilir.",
        "pattern_tags": ["temizlik", "not-engelleme"],
        "general_rule": "Belirsiz/açıklanmamış 'Not:' gibi ek bölümler ekleme; her bölüm sorguya hizmet etmeli."
    },
    {
        "title": "Diş Eti Kesimi Nedir?",
        "original_excerpt": "Başlık: Diş Hekimi Kesimi Hangi Durumlarda Yapılır? (Yanlış başlık)",
        "revised_excerpt": "Başlık: Diş Eti Kesimi (Gingivektomi) Nedir?",
        "pattern_tags": ["başlık-uyumu", "düzeltme"],
        "general_rule": "Başlıklar sorguyla birebir örtüşmeli; başlık-içerik tutarlılığı kontrol edilmeli."
    },
    {
        "title": "Diş Eti Kesimi Sonrasında Neler Yapılmaktadır?",
        "original_excerpt": "...doktorun reçete ettiği ilaçlar ve özellikle ağrı kesiciler saati saatine kullanılmalıdır.",
        "revised_excerpt": "...diş hekiminizin reçete ettiği antiseptik gargara ve ağrı kesiciler düzenli kullanılmalıdır.",
        "pattern_tags": ["terminoloji", "sağlık"],
        "general_rule": "Sektöre özgü doğru terminoloji kullanılmalı ('doktor' değil 'diş hekimi')."
    },
    {
        "title": "Diş Eti Kesimi Kaliteli Midir?",
        "original_excerpt": "Diş eti kesimi, uzman bir diş hekiminin uygulamasıyla son derece kaliteli ve en iyi tedavi yöntemidir.",
        "revised_excerpt": "Diş eti kesimi (gingivektomi), uygun vakalarda doku sağlığını ve estetiğini başarıyla sağlayan güvenilir bir prosedürdür.",
        "pattern_tags": ["iddia-engelleme", "eeat"],
        "general_rule": "Kanıtlanmamış iddialı üstünlük sıfatları ('uzman', 'en iyi') tek başına kullanılmamalı."
    },
    {
        "title": "İltihaplı Diş Çekildikten Sonra İltihap Yayılır mı?",
        "original_excerpt": "İltihaplı diş çekimi genellikle güvenli bir işlemdir; ancak işlem öncesinde iltihabın mutlaka antibiyotik tedavisi ile kontrol altına alınması gerekir.",
        "revised_excerpt": "Akut iltihaplı diş, enfeksiyon kontrol altına alınmadan çekilmez. Diş hekimi önce antibiyotik tedavisi uygular, iltihap baskılandıktan sonra diş güvenle çekilir.",
        "pattern_tags": ["kesinlik", "güven"],
        "general_rule": "'Genellikle' gibi belirsizlik yaratan kelimeleri kullanma; cümleyi kesin ve net ifadeyle kur."
    }
]

EXAMPLE_ARTICLES_DATA = [
    {
        "title": "Zirkonyum Kaplama Nedir? Avantajları ve Fiyatları 2026",
        "body": """Zirkonyum kaplama, estetik diş hekimliğinde hem ön hem arka dişlerde sıklıkla tercih edilen, doku dostu ve yüksek dayanıklılığa sahip bir kaplama türüdür. Metal desteksiz yapısı sayesinde doğal diş şeffaflığını en yakın şekilde taklit eder.

Zirkonyum Diş Kaplamanın Avantajları Nelerdir?
- Diş eti kenarında gri çizgi oluşturmaz (metal alerjisi riski yoktur).
- Isı iletkenliği düşük olduğu için sıcak-soğuk hassasiyeti minimum düzeydedir.
- Çiğneme kuvvetlerine karşı yüksek direnç gösterir.

Zirkonyum Kaplama Tedavisi Kaç Gün Sürer?
Zirkonyum kaplama tedavisi ortalama 3 ile 5 gün arasında tamamlanır. İlk seansta dişler lokal anestezi altında hazırlanır ve dijital ölçü alınır. İkinci seansta altyapı provası, üçüncü seansta ise daimi yapıştırma işlemi gerçekleştirilir.

Zirkonyum Kaplama Fiyatları Neyi Değiştirir?
Zirkonyum kaplama fiyatları; kaplanacak diş sayısına, kullanılan zirkonyum bloğunun kalitesine ve klinik imkanlarına göre değişiklik gösterir. Detaylı muayene ve kişiye özel tedavi planı için diş hekiminize başvurabilirsiniz."""
    },
    {
        "title": "İmplant Tedavisi Nasıl Yapılır? Aşama Aşama İyileşme Süreci",
        "body": """İmplant tedavisi, eksik dişlerin yerine çene kemiğine yerleştirilen titanyum vidalar ve üzerine yapılan porselen/zirkonyum protezlerle doğal diş fonksiyonunu geri kazandırma işlemidir.

İmplant Tedavisi Acıtır mı?
İmplant operasyonu lokal anestezi veya sedasyon altında yapıldığı için işlem sırasında acı hissedilmez. Operasyon sonrasında diş hekiminin reçete ettiği ağrı kesiciler ile süreç konforlu şekilde atlatılır.

İmplantın Kemikle Kaynama Süresi Ne Kadardır?
Çene kemiğine yerleştirilen implantın kemikle bütünleşme süresi (osteointegrasyon) alt çenede ortalama 2-3 ay, üst çenede ise 3-4 ay sürer. Kemik grefti (kemik tozu) uygulanan vakalarda bu süre 6 aya kadar uzayabilir."""
    }
]

PILOT_TOPICS = [
    {
        "topic_title": "Yamuk Dişler Nasıl Düzeltilir?",
        "target_keywords": ["yamuk diş tedavisi", "şeffaf plak", "ortodonti", "diş teli"],
        "priority": 10
    },
    {
        "topic_title": "Diş Çektirmek Acıtır mı?",
        "target_keywords": ["diş çekimi acısı", "lokal anestezi", "diş çekiminden sonra ağrı"],
        "priority": 8
    },
    {
        "topic_title": "Pembe Estetik Nedir ve Nasıl Yapılır?",
        "target_keywords": ["pembe estetik", "diş eti estetiği", "gingivektomi", "gummy smile"],
        "priority": 9
    }
]


# ---------------------------------------------------------------------------
# Seed Fonksiyonu
# ---------------------------------------------------------------------------

def seed_katip_pilot_data(db: Session) -> None:
    logger.info("Katip pilot veri yükleme başlatılıyor...")

    # 1. Tenant var mı kontrol et, yoksa oluştur
    tenant = db.query(DBTenant).filter(DBTenant.id == PILOT_TENANT_ID).first()
    if not tenant:
        tenant = DBTenant(
            id=PILOT_TENANT_ID,
            business_name="Mergen Diş Kliniği Pilot",
            sector="dental_clinic",
            plan="enterprise",
            bot_active=True,
            persona="professional_expert",
        )
        db.add(tenant)
        db.flush()
        logger.info("Pilot tenant oluşturuldu: %s", PILOT_TENANT_ID)
    else:
        logger.info("Pilot tenant zaten mevcut: %s", PILOT_TENANT_ID)

    # 2. BrandGuide ekle / güncelle
    bg = db.query(KatipBrandGuide).filter(KatipBrandGuide.tenant_id == PILOT_TENANT_ID).first()
    if not bg:
        # Rules JSON string uzunluğu tahmini token hesabı (4 karaktere 1 token)
        rules_text = str(BRAND_GUIDE_RULES)
        token_est = len(rules_text) // 4

        bg = KatipBrandGuide(
            tenant_id=PILOT_TENANT_ID,
            sector="dental_clinic",
            rules_json=BRAND_GUIDE_RULES,
            token_count=token_est,
        )
        db.add(bg)
        logger.info("BrandGuide yüklendi (tahmini %d token).", token_est)
    else:
        bg.rules_json = BRAND_GUIDE_RULES
        logger.info("BrandGuide güncellendi.")

    # 3. RevisionPatterns (15 adet) + Vektör Embedding
    existing_rev_count = db.query(KatipRevisionPattern).filter(KatipRevisionPattern.tenant_id == PILOT_TENANT_ID).count()
    if existing_rev_count == 0:
        logger.info("15 adet Revizyon Kalıbı ve vektör embedding'leri yükleniyor...")
        for pattern in REVISION_PATTERNS_DATA:
            # Vector embedding üret (RAG için)
            embed_text = f"{pattern['title']} {pattern['general_rule']} {pattern['revised_excerpt']}"
            vec = embed(embed_text)

            rev = KatipRevisionPattern(
                tenant_id=PILOT_TENANT_ID,
                original_excerpt=pattern["original_excerpt"],
                revised_excerpt=pattern["revised_excerpt"],
                pattern_tags=pattern["pattern_tags"],
                embedding=vec,
            )
            db.add(rev)
        logger.info("15 adet Revizyon Kalıbı başarıyla eklendi.")
    else:
        logger.info("Revizyon kalıpları zaten yüklü (%d adet).", existing_rev_count)

    # 4. ExampleArticles + Vektör Embedding
    existing_art_count = db.query(KatipExampleArticle).filter(KatipExampleArticle.tenant_id == PILOT_TENANT_ID).count()
    if existing_art_count == 0:
        logger.info("Örnek makaleler yükleniyor...")
        for art in EXAMPLE_ARTICLES_DATA:
            vec = embed(f"{art['title']} {art['body'][:500]}")
            words = len(art["body"].split())
            item = KatipExampleArticle(
                tenant_id=PILOT_TENANT_ID,
                title=art["title"],
                body=art["body"],
                embedding=vec,
                word_count=words,
            )
            db.add(item)
        logger.info("Örnek makaleler eklendi.")

    # 5. Pilot Konu Kuyruğu (TopicsQueue)
    existing_topic_count = db.query(KatipTopicQueue).filter(KatipTopicQueue.tenant_id == PILOT_TENANT_ID).count()
    if existing_topic_count == 0:
        logger.info("Pilot konular kuyruğa ekleniyor...")
        for top in PILOT_TOPICS:
            t_item = KatipTopicQueue(
                tenant_id=PILOT_TENANT_ID,
                topic_title=top["topic_title"],
                target_keywords=top["target_keywords"],
                priority=top["priority"],
                status="pending",
            )
            db.add(t_item)
        logger.info("3 adet pilot konu kuyruğa eklendi.")

    db.commit()
    logger.info("Katip pilot verileri başarıyla veritabanına işlendi! ✅")


if __name__ == "__main__":
    with SessionLocal() as session:
        seed_katip_pilot_data(session)
