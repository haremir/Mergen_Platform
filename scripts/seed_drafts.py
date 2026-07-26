"""
scripts/seed_drafts.py
~~~~~~~~~~~~~~~~~~~~~~

Pilot tenant'a gerçekçi taslak verisi ekler.

Eklenecekler:
- 12 adet ek konu (çeşitli sektörel başlıklar)
- 8 adet hazır taslak (draft, in_review, approved, published durumlarında)
- Her taslak için 1-2 versiyon

Kullanım:
    set PYTHONPATH=core;packages;products;shared;.
    uv run python scripts/seed_drafts.py
"""

from __future__ import annotations

import logging
import os
import sys

# Proje kökünü path'e ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone, timedelta

from mergen_core.database import SessionLocal
from mergen_core.db_models import DBTenant
from mergen_product_katip.models import (
    KatipBrandGuide,
    KatipTopicQueue,
    KatipDraft,
    KatipDraftVersion,
    KatipFeedbackNote,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

PILOT_TENANT_ID = "pilot-dental-clinic-01"

# ---------------------------------------------------------------------------
# Ek Konu Başlıkları
# ---------------------------------------------------------------------------

EXTRA_TOPICS = [
    {
        "topic_title": "Zirkonyum Diş Kaplama Nedir, Nasıl Yapılır?",
        "target_keywords": ["zirkonyum kaplama", "estetik diş hekimliği", "porselen diş"],
        "priority": 10,
    },
    {
        "topic_title": "İmplant Tedavisi Süreci ve Sonrası",
        "target_keywords": ["implant tedavisi", "diş implantı", "titanyum vida"],
        "priority": 9,
    },
    {
        "topic_title": "Diş Beyazlatma (Bleaching) Yöntemleri",
        "target_keywords": ["diş beyazlatma", "bleaching", "ofis tipi beyazlatma"],
        "priority": 8,
    },
    {
        "topic_title": "Çocuklarda Ortodonti Tedavisi Ne Zaman Başlamalı?",
        "target_keywords": ["çocuk ortodonti", "diş teli yaşı", "erken ortodonti"],
        "priority": 7,
    },
    {
        "topic_title": "Diş Eti Hastalıkları (Periodontitis) Belirtileri ve Tedavisi",
        "target_keywords": ["diş eti hastalığı", "periodontitis", "diş eti iltihabı"],
        "priority": 8,
    },
    {
        "topic_title": "Lamine Diş Kaplama: Avantajları ve Dezavantajları",
        "target_keywords": ["lamine diş", "laminat veneer", "estetik kaplama"],
        "priority": 7,
    },
    {
        "topic_title": "Gece Plağı (Bruksizm) Nedir ve Nasıl Tedavi Edilir?",
        "target_keywords": ["gece plağı", "bruksizm", "diş gıcırdatma"],
        "priority": 6,
    },
    {
        "topic_title": "Kanal Tedavisi (Endodonti) Hakkında Merak Edilenler",
        "target_keywords": ["kanal tedavisi", "endodonti", "diş kanalı"],
        "priority": 6,
    },
    {
        "topic_title": "Ağız İçi Protez Çeşitleri: Sabit ve Hareketli Protezler",
        "target_keywords": ["diş protezi", "sabit protez", "hareketli protez", "takma diş"],
        "priority": 7,
    },
    {
        "topic_title": "Diş Hassasiyeti Neden Olur? Evde Tedavi Yolları",
        "target_keywords": ["diş hassasiyeti", "hassas dişler", "soğuk sıcak ağrı"],
        "priority": 5,
    },
    {
        "topic_title": "Florür Uygulaması Çocuklara Güvenli midir?",
        "target_keywords": ["florür uygulaması", "çocuk diş sağlığı", "florür tedavisi"],
        "priority": 5,
    },
    {
        "topic_title": "Gülüş Tasarımı (Smile Design) Nedir?",
        "target_keywords": ["gülüş tasarımı", "smile design", "estetik gülüş"],
        "priority": 9,
    },
]

# ---------------------------------------------------------------------------
# Hazır Taslak İçerikleri
# ---------------------------------------------------------------------------

DRAFT_CONTENTS = [
    # 1 — Yayınlandı (published)
    {
        "topic_title": "Zirkonyum Diş Kaplama Nedir, Nasıl Yapılır?",
        "status": "published",
        "versions": [
            {
                "v": 1,
                "content": """# Zirkonyum Diş Kaplama Nedir, Nasıl Yapılır?

Zirkonyum kaplama, estetik diş hekimliğinde metal desteksiz yapısı ve doğal görünümüyle ön plana çıkan ileri teknoloji bir kaplama türüdür. Yüksek biyouyumluluğu sayesinde diş eti sağlığını tehdit etmeden uzun yıllar sorunsuz kullanılabilmektedir.

## Zirkonyum Diş Kaplamanın Avantajları Nelerdir?

Zirkonyum kaplamaların tercih edilmesinin başlıca nedenleri şunlardır:
- Metal alerjisi riski sıfıra yakındır; diş eti kenarında gri çizgi oluşturmaz.
- Isı iletkenliği düşük olduğu için sıcak-soğuk hassasiyeti en aza indirgenir.
- Çiğneme kuvvetlerine karşı yüksek direnç gösterir; 10-15 yıl kullanım ömrü beklenir.
- CAD/CAM teknolojisiyle hazırlandığı için doğal diş şeffaflığını en yakın şekilde taklit eder.

## Zirkonyum Kaplama Süreci Nasıl İşler?

Zirkonyum kaplama tedavisi ortalama 3 ile 5 gün arasında tamamlanır:
1. **Birinci Seans:** Diş lokal anestezi altında hazırlanır; dijital ölçü alınır.
2. **İkinci Seans:** Altyapı (zirkonyum iskelet) provası yapılır.
3. **Üçüncü Seans:** Porselen tabaka eklenerek daimi yapıştırma gerçekleştirilir.

## Zirkonyum Bakımı Nasıl Yapılır?

Zirkonyum kaplamaların uzun ömürlü olması için günde iki kez düzenli fırçalama ve arayüz fırçası kullanımı şarttır. Kaplama kenarlarında bakteri plağı birikimini önlemek amacıyla antiseptik gargara tercih edilmeli; altı ayda bir diş hekimi kontrolü aksatılmamalıdır.

## Sık Sorulan Sorular

**Zirkonyum kaplama acıtır mı?**
Zirkonyum kaplama işlemi lokal anestezi altında yapıldığı için işlem sırasında ağrı hissedilmez. İşlem sonrasında hafif hassasiyet birkaç gün içinde kendiliğinden geçer.

**Zirkonyum ile porselen arasındaki fark nedir?**
Zirkonyum, porselen kaplamaya göre çok daha dayanıklıdır; arka dişlerde yüksek çiğneme kuvvetlerine karşı porselen yerine tercih edilir. Porselen ön dişlerde estetik açıdan daha doğal görünüm sağlar ancak kırılganlık riski taşır.
""",
            }
        ],
    },
    # 2 — Yayınlandı (published)
    {
        "topic_title": "Gülüş Tasarımı (Smile Design) Nedir?",
        "status": "published",
        "versions": [
            {
                "v": 1,
                "content": """# Gülüş Tasarımı (Smile Design) Nedir?

Gülüş tasarımı (Smile Design), kişinin yüz yapısı, dudak çizgisi, diş boyutu ve rengi gözetilerek estetik açıdan mükemmel bir gülüşün planlandığı kapsamlı diş hekimliği uygulamasıdır. Dijital görüntüleme teknolojileriyle tedavi öncesi sonucu simüle etmek mümkündür.

## Kimler Gülüş Tasarımı Yaptırabilir?

Gülüş tasarımı şu durumlarda uygulanabilir:
- Dişlerin rengi, boyutu veya şeklinden memnun olmayanlar
- Diastema (dişler arası boşluk) sorunu yaşayanlar
- Diş eti seviyesi dengesiz olan bireyler
- Estetik açıdan bütüncül bir gülüş arzu edenler

## Gülüş Tasarımında Kullanılan Yöntemler

Birden fazla prosedür bir arada uygulanabilir:
- Zirkonyum veya lamine kaplama
- Diş beyazlatma (bleaching)
- Pembe estetik (diş eti düzenlemesi)
- Ortodonti (diş hizalama)

## Süreç ve İyileşme

Gülüş tasarımı süreci kişiye göre 1 ila 4 hafta arasında değişir. Dijital gülüş analizi ile tedavi başlamadan önce beklenen sonuç simüle edilir; hastanın onayı alındıktan sonra uygulamaya geçilir.
""",
            }
        ],
    },
    # 3 — Onaylandı (approved)
    {
        "topic_title": "Diş Beyazlatma (Bleaching) Yöntemleri",
        "status": "approved",
        "versions": [
            {
                "v": 1,
                "content": """# Diş Beyazlatma (Bleaching) Yöntemleri

Diş beyazlatma (bleaching), dişlerin rengini açmak amacıyla uygulanan profesyonel diş hekimliği prosedürüdür. Ofis tipi ve ev tipi olmak üzere iki temel uygulama yöntemi mevcuttur.

## Ofis Tipi Diş Beyazlatma

Ofis tipi beyazlatma, diş kliniğinde uzman diş hekimi gözetiminde uygulanan hızlı ve etkili bir yöntemdir. Yüksek konsantrasyonlu hidrojen peroksit jeli dişlere uygulanır; işlem ortalama 45-60 dakika sürer. Tek seansta 2-8 ton açılım sağlanabilir.

## Ev Tipi Diş Beyazlatma

Ev tipi beyazlatmada diş hekimi tarafından hazırlanan kişisel plaklar ve düşük konsantrasyonlu jel kiti kullanılır. 10-14 gün boyunca günde 4-8 saat uygulanır. Sonuçlar ofis tipine göre daha yavaş görünür ancak daha uzun süre kalıcı olabilir.

## Beyazlatma Sonrası Dikkat Edilmesi Gerekenler

Beyazlatma tedavisinin ardından 48 saat boyunca renklendiricisi yüksek besinlerden (kahve, çay, kırmızı şarap) ve sigaradan kaçınılmalıdır. Bu süreçte dişler dış etkilere karşı daha hassastır.
""",
            },
            {
                "v": 2,
                "content": """# Diş Beyazlatma (Bleaching) Yöntemleri

Diş beyazlatma (bleaching), dişlerin rengini açmak amacıyla uygulanan profesyonel diş hekimliği prosedürüdür. Ofis tipi ve ev tipi olmak üzere iki temel uygulama yöntemi mevcuttur. Tedavi öncesinde mutlaka diş hekimi muayenesi yapılmalıdır.

## Ofis Tipi Diş Beyazlatma

Ofis tipi beyazlatma, diş kliniğinde uzman diş hekimi gözetiminde uygulanan hızlı ve etkili bir yöntemdir. Yüksek konsantrasyonlu hidrojen peroksit jeli dişlere uygulanır; işlem ortalama 45-60 dakika sürer. Tek seansta 2-8 ton açılım sağlanabilir.

## Ev Tipi Diş Beyazlatma

Ev tipi beyazlatmada diş hekimi tarafından hazırlanan kişisel plaklar ve düşük konsantrasyonlu jel kiti kullanılır. 10-14 gün boyunca günde 4-8 saat uygulanır.

## Kimler Diş Beyazlatma Yaptırabilir?

Dişleri sağlıklı, dolgu ve kaplama bulunmayan bireyler beyazlatma tedavisinden en iyi sonucu alır. Hamile ve emziren bireyler bu tedaviden muaf tutulmalıdır. Kanal tedavili dişler ve dolgu ya da kron içeren dişler beyazlatma tedavisine yanıt vermez.

## Beyazlatma Sonrası Dikkat Edilmesi Gerekenler

Beyazlatma tedavisinin ardından 48 saat boyunca renklendiricisi yüksek besinlerden (kahve, çay, kırmızı şarap) ve sigaradan kaçınılmalıdır. Diş hassasiyetini azaltmak için diş hekiminin önerdiği duyarsızlaştırıcı macun kullanılabilir.
""",
            },
        ],
    },
    # 4 — İncelemede (in_review) — 2 versiyon
    {
        "topic_title": "İmplant Tedavisi Süreci ve Sonrası",
        "status": "in_review",
        "versions": [
            {
                "v": 1,
                "content": """# İmplant Tedavisi Süreci ve Sonrası

İmplant tedavisi, eksik dişlerin yerine çene kemiğine titanyum vida yerleştirilerek üzerine porselen veya zirkonyum protez yapılmasına dayanan kalıcı diş tedavisi yöntemidir.

## İmplant Tedavisi Acıtır mı?

İmplant operasyonu lokal anestezi altında gerçekleştirildiğinden işlem sırasında ağrı hissedilmez. Operasyon sonrasında hafif şişlik ve ağrı beklenen bir süreçtir; diş hekiminin reçete ettiği ağrı kesiciler ile bu süreç konforlu geçirilir.

## İmplantın Kemikle Kaynama Süresi

Alt çenede ortalama 2-3 ay, üst çenede 3-4 ay süren osteointegrasyon (kemikle kaynaşma) süreci tamamlandıktan sonra üst yapı (kron) uygulanır. Kemik grefti gereken vakalarda bu süre 6 aya kadar uzayabilir.

## İmplant Sonrası Bakım

İmplant tedavisinin uzun ömürlü olması için günlük ağız hijyeni kritik önem taşır. Arayüz fırçası ve diş ipi düzenli kullanılmalı; 6 ayda bir profesyonel diş temizliği (tartar/scale) yaptırılmalıdır.
""",
            }
        ],
    },
    # 5 — İncelemede (in_review)
    {
        "topic_title": "Lamine Diş Kaplama: Avantajları ve Dezavantajları",
        "status": "in_review",
        "versions": [
            {
                "v": 1,
                "content": """# Lamine Diş Kaplama: Avantajları ve Dezavantajları

Lamine diş kaplama (veneer), dişin yalnızca ön yüzeyine yapıştırılan, seramik ya da kompozit malzemeden üretilen ince bir kaplama tabakasıdır. Minimal diş tıraşı ile estetik dönüşüm sağlar.

## Lamine Kaplamanın Avantajları

- Minimal diş tıraşı gerektirir (0.3-0.5 mm); sağlıklı diş dokusu korunur.
- Doğal diş şeffaflığına çok yakın görünüm sağlar.
- Renk, şekil ve boyut düzeltmesini tek prosedürde gerçekleştirir.
- Porselen laminate yüzeyi leke tutmaz ve zamanla renk değiştirmez.

## Lamine Kaplamanın Dezavantajları

- Diş tıraşı geri döndürülemez bir işlemdir; tedavinin sona ermesi durumunda yeni kaplama zorunlu olur.
- Aşırı diş gıcırdatanlar (bruksizm) için önerilmez; kırılma riski artar.
- İmplant veya dolgu bulunan dişlere uygulanamaz.

## Kimler Lamine Kaplama Yaptırabilir?

Diş yüzeyinde renk değişimi, hafif çapraşıklık, kırık veya çatlak olan ve diastema (dişler arası boşluk) sorunu yaşayan bireyler için uygun bir tedavi seçeneğidir. Detaylı muayene sonrasında diş hekimi uygunluğu değerlendirir.
""",
            }
        ],
    },
    # 6 — Taslak (draft)
    {
        "topic_title": "Diş Eti Hastalıkları (Periodontitis) Belirtileri ve Tedavisi",
        "status": "draft",
        "versions": [
            {
                "v": 1,
                "content": """# Diş Eti Hastalıkları (Periodontitis) Belirtileri ve Tedavisi

Periodontitis, dişleri destekleyen dokuların (diş eti, kemik ve bağ dokusu) bakteriyel enfeksiyon kaynaklı iltihaplanmasıdır. Tedavi edilmediğinde diş kayıplarına yol açan ciddi bir ağız hastalığıdır.

## Periodontitis Belirtileri Nelerdir?

- Diş etlerinde kanama (fırçalama sırasında)
- Diş etlerinde kızarıklık, şişlik ve hassasiyet
- Dişlerde sallantı veya uzama hissi
- Kötü ağız kokusu (halitoz)
- Diş eti çekilmesi ve köklerin görünür hale gelmesi

## Periodontitis Nasıl Tedavi Edilir?

**Hafif vakalar:** Diş taşı (tartar) temizliği ve kök yüzeyi düzlemesi (scaling ve root planing) ile kontrol altına alınabilir.

**İleri vakalar:** Cerrahi müdahale gerekebilir. Flap operasyonu ile diş eti açılarak derin temizlik yapılır; kemik kaybı varsa greft uygulanabilir.

Tedavi sonrasında düzenli diş hekimi takibi ve günlük ağız hijyeni önem taşır.
""",
            }
        ],
    },
    # 7 — Taslak (draft)
    {
        "topic_title": "Kanal Tedavisi (Endodonti) Hakkında Merak Edilenler",
        "status": "draft",
        "versions": [
            {
                "v": 1,
                "content": """# Kanal Tedavisi (Endodonti) Hakkında Merak Edilenler

Kanal tedavisi (endodontik tedavi), diş pulpasının (sinir ve damar ağının) hasar görmesi veya enfekte olması durumunda uygulanan ve dişin çekilmeden kurtarılmasını sağlayan tedavi yöntemidir.

## Kanal Tedavisi Ne Zaman Gerekir?

- Derin çürük nedeniyle pulpanın enfekte olması
- Travma sonrası diş sinirinin hasar görmesi
- Dişte yoğun ağrı, şişlik veya ateş

## Kanal Tedavisi Nasıl Yapılır?

Tedavi lokal anestezi altında birkaç seansta tamamlanır:
1. Enfekte pulpa dokusu özel aletlerle temizlenir.
2. Kanal şekillendirilir ve antimikrobiyal solüsyonlarla yıkanır.
3. Kanal, biyouyumlu guta-perka materyaliyle doldurulur.
4. Diş, üzerine yapılacak kron ile güçlendirilir.

## Kanal Tedavisi Acıtır mı?

Kanal tedavisi lokal anestezi altında yapıldığı için işlem sırasında ağrı hissedilmez. İşlem sonrasında hafif hassasiyet birkaç gün sürebilir; diş hekiminin önerdiği ağrı kesicilerle rahatça yönetilebilir.
""",
            }
        ],
    },
    # 8 — Taslak (draft)
    {
        "topic_title": "Ağız İçi Protez Çeşitleri: Sabit ve Hareketli Protezler",
        "status": "draft",
        "versions": [
            {
                "v": 1,
                "content": """# Ağız İçi Protez Çeşitleri: Sabit ve Hareketli Protezler

Diş protezleri, eksik dişlerin fonksiyon ve estetiğini yeniden kazandırmak amacıyla uygulanan yapay diş çözümleridir. Sabit ve hareketli olmak üzere iki temel kategoride incelenir.

## Sabit Protezler

Sabit protezler çıkarılamaz; implant ya da mevcut dişlere yapıştırılarak kalıcı olarak ağızda tutulur:
- **İmplant üstü protez:** Kemike bütünleşen titanyum vida üzerine yerleştirilen kron.
- **Köprü (bridge):** Eksik dişin iki yanındaki komşu dişlere destek alınarak yapılan kaplama köprüsü.

## Hareketli Protezler

Hareketli protezler günlük olarak ağızdan çıkarılabilir:
- **Tam protez (takma diş):** Tüm dişlerin yokluğunda uygulanan, pembe akrilik plak üzerine yapılan protez.
- **Parsiyel (bölümsel) protez:** Yalnızca bazı dişlerin eksik olduğu durumlarda kalan dişlere tutturulan kısmi protez.

## Hangi Protez Türü Tercih Edilmeli?

Tercih, çene kemiği sağlığına, mevcut diş sayısına ve hastanın genel sağlık durumuna göre diş hekimi tarafından belirlenir. İmplant destekli sabit protezler uzun vadede en konforlu çözümü sunar; ancak kemik yoğunluğu yeterli olmayan vakalarda hareketli protez tercih edilebilir.
""",
            }
        ],
    },
]


def seed_extra_topics(db, brand_guide_id: str) -> dict[str, str]:
    """Ek konuları ekler; başlık → id map'i döner."""
    existing = {
        row.topic_title
        for row in db.query(KatipTopicQueue.topic_title)
        .filter(KatipTopicQueue.tenant_id == PILOT_TENANT_ID)
        .all()
    }

    title_to_id: dict[str, str] = {}

    # Mevcut olanları da map'e ekle
    for row in db.query(KatipTopicQueue.id, KatipTopicQueue.topic_title).filter(
        KatipTopicQueue.tenant_id == PILOT_TENANT_ID
    ):
        title_to_id[row.topic_title] = row.id

    added = 0
    for t in EXTRA_TOPICS:
        if t["topic_title"] in existing:
            logger.info("Konu zaten var: %s", t["topic_title"])
            continue
        new_t = KatipTopicQueue(
            tenant_id=PILOT_TENANT_ID,
            brand_guide_id=brand_guide_id,
            topic_title=t["topic_title"],
            target_keywords=t["target_keywords"],
            priority=t["priority"],
            status="pending",
        )
        db.add(new_t)
        db.flush()
        title_to_id[new_t.topic_title] = new_t.id
        existing.add(t["topic_title"])
        added += 1

    logger.info("%d yeni konu eklendi.", added)
    return title_to_id


def seed_drafts(db, brand_guide_id: str, title_to_id: dict[str, str]) -> None:
    """Hazır taslakları ve versiyonlarını ekler."""
    added = 0

    for draft_data in DRAFT_CONTENTS:
        title = draft_data["topic_title"]
        topic_id = title_to_id.get(title)

        if not topic_id:
            logger.warning("Konu bulunamadı, atlıyorum: %s", title)
            continue

        # Aynı konu için zaten draft var mı?
        existing_draft = (
            db.query(KatipDraft)
            .filter(KatipDraft.topic_id == topic_id, KatipDraft.tenant_id == PILOT_TENANT_ID)
            .first()
        )
        if existing_draft:
            logger.info("Draft zaten mevcut, atlıyorum: %s", title)
            continue

        # Taslak oluştur
        draft = KatipDraft(
            topic_id=topic_id,
            tenant_id=PILOT_TENANT_ID,
            brand_guide_id=brand_guide_id,
            status=draft_data["status"],
        )
        db.add(draft)
        db.flush()

        # Konuyu done yap
        topic = db.query(KatipTopicQueue).filter(KatipTopicQueue.id == topic_id).first()
        if topic:
            topic.status = "done"

        # Versiyonları ekle — farklı tarihler simüle et
        for i, v in enumerate(draft_data["versions"]):
            created_offset = timedelta(days=-(len(draft_data["versions"]) - i))
            version = KatipDraftVersion(
                draft_id=draft.id,
                version_number=v["v"],
                content=v["content"],
                word_count=len(v["content"].split()),
            )
            db.add(version)

        logger.info("Draft eklendi: [%s] %s — %d versiyon", draft_data["status"], title, len(draft_data["versions"]))
        added += 1

    logger.info("Toplam %d yeni draft eklendi.", added)


def main() -> None:
    logger.info("=" * 60)
    logger.info("Kâtip Pilot — Seed Drafts başlatılıyor")
    logger.info("=" * 60)

    with SessionLocal() as db:
        # Tenant kontrolü
        tenant = db.query(DBTenant).filter(DBTenant.id == PILOT_TENANT_ID).first()
        if not tenant:
            logger.error(
                "Tenant '%s' bulunamadı! Önce seed.py çalıştırın.", PILOT_TENANT_ID
            )
            sys.exit(1)

        # BrandGuide bul
        bg = (
            db.query(KatipBrandGuide)
            .filter(KatipBrandGuide.tenant_id == PILOT_TENANT_ID)
            .first()
        )
        if not bg:
            logger.error("BrandGuide bulunamadı! Önce seed.py çalıştırın.")
            sys.exit(1)

        brand_guide_id = bg.id
        logger.info("BrandGuide bulundu: %s (id: %s)", bg.brand_name, brand_guide_id)

        # 1. Ek konular
        title_to_id = seed_extra_topics(db, brand_guide_id)

        # 2. Hazır taslaklar
        seed_drafts(db, brand_guide_id, title_to_id)

        db.commit()

    logger.info("=" * 60)
    logger.info("✅ Seed Drafts tamamlandı!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
