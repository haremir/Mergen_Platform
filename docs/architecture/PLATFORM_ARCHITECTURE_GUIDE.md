# Mergen AI Business Platform — Ana Mimari ve Geliştirme Rehberi

> **Sürüm:** 1.0.0  
> **Hedef Kitle:** Yazılım Mimarları, Full-Stack Geliştiriciler, Yapay Zeka Ajanları (AI Agents)  
> **Son Güncelleme:** Temmuz 2026

---

## 1. Sistem Vizyonu & Monorepo Yapısı

Mergen AI Business Platform, İşletmeler ve Dijital Ajanslar için çoklu yapay zeka ürünlerini (Kâtip, Desk, vb.) tek bir ortak çekirdek (`mergen_core`) ve tek bir veritabanı altyapısı üzerinde sunan **Modular Monorepo** mimarisine sahiptir.

### Monorepo Dizini ve Sorumluluk Dağılımı

```
Mergen_Platform/
├── core/
│   └── mergen_core/             # Çekirdek Servisler (LLM Gateway, Tenant Manager, Plan Guard, RAG)
├── products/
│   ├── mergen_product_desk/     # Ürün 1: WhatsApp/Telegram Resepsiyon Asistanı
│   └── mergen_product_katip/    # Ürün 2: Yarı-Otonom SEO Blog Taslak Üreticisi
├── packages/                    # Bağımsız Kütüphaneler (WhatsApp Client, Telegram Bot, vb.)
├── panel/
│   └── api_server.py            # Tüm Platformun Ortak FastAPI REST API Sunucusu
├── frontend/                    # Mergen Super Admin / Master Yönetim Paneli (React 19 + Vite)
├── frontend_katip/              # Kâtip Ürünü Müşteri/Editör Web Arayüzü (React 19 + Vite)
├── infra/                       # Docker Compose, Kubernetes, Terraform altyapı kodları
├── alembic/                     # Merkezi Asenkron Veritabanı Migrasyon Yönetimi
└── docs/                        # Mimari Dokümantasyon ve Rehberler
```

---

## 2. Veritabanı Mimarisi & Standartları

Platform, **Tek Bir PostgreSQL Veritabanı (`mergen_db`)** ve **Asenkron SQLAlchemy 2.x + asyncpg** mimarisi kullanır. 

### Temel Veritabanı Prensipleri

1. **Ayrı Veritabanı (Multi-DB) YASAKTIR:** Her yeni ürün için ayrı bir PostgreSQL veritabanı açılmaz. Tüm ürünler ve core servisler aynı PostgreSQL kümesinde saklanır.
2. **Modüler Şema / Mantıksal İzolasyon:**
   - `core` tabloları: `tenants`, `plan_usages`, `platform_settings`, `sector_prompts`
   - `katip` tabloları: `katip_brand_guides`, `katip_topics_queue`, `katip_drafts`, `katip_draft_versions`, `katip_feedback_notes`, `katip_generation_logs`, `katip_example_articles`, `katip_revision_patterns`
3. **Multi-Tenant İzolasyon:**
   - Tüm ürün tablolarında `tenant_id` (String(36) UUID / Foreign Key) alanı **zorunludur**.
   - Sorgularda `WHERE tenant_id = :tenant_id` filtresi veritabanı katmanında veya API router'da doğrulanır.
4. **Vektör Arama & RAG:**
   - PostgreSQL `pgvector` eklentisi (`CREATE EXTENSION IF NOT EXISTS vector;`) standarttır.
   - Embeddings verileri `pgvector` indeksleri (IVFFlat/HNSW) ile semantik aramada kullanılır.
5. **Şema Yönetimi (Alembic):**
   - Tablolar kod içerisinde `create_all()` ile YARATILMAZ.
   - Değişiklikler yalnızca `uv run alembic revision --autogenerate` ve `uv run alembic upgrade head` komutlarıyla canlıya sürülür.

---

## 3. Frontend Mimarisi (Web Tarafı)

Web arayüzleri iki net kategoriye ayrılır:

### A. Super Admin / Master Yönetim Paneli (`frontend/`)
- **Kullanıcı:** Mergen Platform İç Operatörleri, Sistem Yöneticileri, Müşteri Temsilcileri.
- **Amacı:** Yeni tenant (müşteri) onboarding kaydı oluşturma, platform istatistiklerini izleme, LLM gateway kullanımını takip etme, sistem ayarlarını yapılandırma.
- **Port / Konum:** `http://localhost:5173` (veya `admin.mergen.ai`)

### B. Ürün Özel Müşteri / Editör Panelleri (`frontend_<ürün_adı>/`)
- **Kullanıcı:** SEO Ajansları, Müşteri Editörleri, Son Kullanıcılar.
- **Amacı:** Sadece ilgili ürünün (örn. Kâtip) işlevlerini sunar. Editör taslak inceleme, revizyon talebi, konu kuyruğu yönetimi.
- **Port / Konum:** `http://localhost:5174` (veya `katip.mergen.ai`)

### Web Mimarisi Kuralları
- **Farklı Kullanıcı Rolleri Karıştırılamaz:** Müşteri/editör ekranları asla Super Admin paneline sayfa olarak eklenmez. Ayrı Vite React uygulaması olarak izolasyon sağlanır.
- **Ortak API Sunucusu:** Tüm frontend uygulamaları tek bir FastAPI sunucusuna (`panel/api_server.py`) bağlanır. Prefix'ler ayrıştırılır (`/api/onboarding`, `/api/katip/*`, `/api/desk/*`).
- **Tenant Auth:** API isteklerinde `X-Tenant-ID` (veya JWT bearer token) header'ı gönderilir.

---

## 4. Yeni Bir Ürün (Modül) Ekleme Adım Adım Rehberi

Mergen Platformu'na yeni bir ürün (örneğin "Mergen Danışman" veya "Mergen Destek") ekleneceği zaman şu adımlar izlenir:

```
[1. Python Modülü]     → products/mergen_product_<ürün>/
                          ├── __init__.py
                          ├── models.py      (SQLAlchemy Base modelleri)
                          ├── router.py      (FastAPI APIRouter)
                          └── engine.py      (İş mantığı & LLM Gateway)

[2. DB Registration]   → core/mergen_core/db_models.py veya alembic/env.py
                          import mergen_product_<ürün>.models

[3. Migrasyon]          → uv run alembic revision --autogenerate -m "Add <ürün> models"
                          uv run alembic upgrade head

[4. API Mount]         → panel/api_server.py
                          from mergen_product_<ürün>.router import router
                          app.include_router(router, prefix="/api/<ürün>")

[5. Frontend App]       → frontend_<ürün>/ (Vite + React + Tailwind v4)
```

---

## 5. İlgili Detaylı Dokümanlar

- 📄 [Veritabanı Mimari Detayları ve Şemalar](DATABASE_STRATEGY.md)
- 📄 [Frontend Mimarisi ve Web İzolasyonu](FRONTEND_STRATEGY.md)
- 📄 [Yeni Ürün Ekleme Oyun Kitabı (Playbook)](NEW_PRODUCT_ONBOARDING_PLAYBOOK.md)
