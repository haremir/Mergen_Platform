# Mergen Platform — Veritabanı Mimari Stratejisi

> **Doküman Kodu:** DOC-ARCH-DB-001  
> **Kapsam:** PostgreSQL, SQLAlchemy 2.x Async, Alembic, pgvector, Multi-Tenancy  
> **Durum:** Onaylandı / Aktif Standart

---

## 1. Mimari Karar Özeti (ADR)

| Karar Alanı | Seçilen Yaklaşım | Gerekçe / Rasyonel |
|-------------|------------------|-------------------|
| **VT Yapısı** | **Tek PostgreSQL Kümesi (`mergen_db`)** | Bağlantı havuzu israfını önler, cross-table JOIN ve multi-tenant veri yönetimini basitleştirir. |
| **İzolasyon** | **Tablo Öneki / Şema (Schema) Ayrımı** | `katip_*`, `desk_*`, `core.*` şeklinde modüler isim alanı (namespace) temizliği sağlar. |
| **ORM & Driver** | **SQLAlchemy 2.x + `asyncpg`** | Tam asenkron IO, yüksek eşzamanlılık (concurrency), tip güvenliği ve async/await entegrasyonu. |
| **Şema Evrimi** | **Alembic (Async Migration)** | Kod içi `create_all` yasaktır. Tüm şema değişiklikleri versiyonlanır ve DDL olarak uygulanır. |
| **Vektör Depo** | **PostgreSQL `pgvector`** | Ekstra vektör veritabanı karmaşıklığı yaratmadan relational veri ile embedding'leri aynı transaction içinde tutar. |

---

## 2. Şema Yapısı ve İsimlendirme Standartları

### A. Çekirdek Tablolar (`core`)
- `tenants`: Platforma kayıtlı tüm işletmeler ve abonelik detayları.
- `plan_usages`: Aylık kullanım kotaları ve token limit takibi.
- `platform_settings`: Sistem geneli konfigürasyonlar (bakım modu, alert'ler).
- `sector_prompts`: Sektör bazlı varsayılan sistem promptları.

### B. Kâtip Modülü Tabloları (`katip_*`)
- `katip_brand_guides`: Tenant marka kuralları, ton ve yasaklı kelimeler (`rules_json`, `token_count`).
- `katip_topics_queue`: Scheduler tarafından işlenecek konular (`status`, `locked_at`, `processed_at`).
- `katip_drafts`: Kök taslak kaydı (`topic_id` FK, `status`).
- `katip_draft_versions`: Taslak versiyonları (`draft_id` FK, `version_number`, `parent_version_id` self-ref FK).
- `katip_feedback_notes`: Editör revizyon notları (`draft_version_id` FK).
- `katip_generation_logs`: LLM üretim logları (`prompt_hash`, `token_count`, `model_used`).
- `katip_example_articles`: Referans makaleler (`embedding` pgvector).
- `katip_revision_patterns`: Editör geçmiş revizyon kalipları (`embedding` pgvector).

---

## 3. Eşzamanlılık, Idempotency ve Kilit Yönetimi

Aynı anda 50 farklı tenant için cron veya worker çalıştığında race condition ve duplicate üretimi engellemek için şu prensipler uygulanır:

### `SELECT FOR UPDATE SKIP LOCKED` Kalıbı
Konu kuyruğundan (`katip_topics_queue`) iş çekilirken naif sorgu kullanılmaz:

```python
# DOĞRU: Idempotent ve Distributed Kuyruk İşleme
stmt = (
    select(KatipTopicQueue)
    .where(KatipTopicQueue.status == "pending")
    .order_by(KatipTopicQueue.priority.desc())
    .with_for_update(skip_locked=True)
    .limit(1)
)
```

- **`locked_at`**: Konu işlenmeye başlandığında zaman damgası vurulur.
- **`processed_at`**: Başarıyla bittiğinde doldurulur.
- **`retry_count` & `error_message`**: Hata durumunda 3 denemeden sonra `failed` statüsüne alınır.

---

## 4. Alembic Migration İş Akışı

Veritabanı şemasında değişiklik yapılacağı zaman takip edilecek komutlar:

```bash
# 1. Docker PostgreSQL servisinin ayakta olduğundan emin ol
docker compose -f infra/docker-compose.yml up -d

# 2. Modeli kodda tanımla/güncelle (models.py)
# 3. Alembic otomatik revizyon oluştur
uv run alembic revision --autogenerate -m "Açıklayıcı migrasyon mesajı"

# 4. Oluşan migrasyon dosyasını incele (alembic/versions/xxxx.py)
# 5. Migrasyonu veritabanına uygula
uv run alembic upgrade head

# 6. Değişiklikleri git'e ekle
git add alembic/versions/
```

---

## 5. SQLAlchemy Async Bağlantı Kodu Kalıbı (`core/mergen_core/database.py`)

```python
# Async Engine & SessionFactory Yapılandırması
async_engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

async_session_factory = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)
```
