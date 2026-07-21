# Mergen AI Business Platform

**Mergen AI Business Platform**, İşletmeler ve Dijital Ajanslar için çoklu yapay zeka ürünlerini (Kâtip, Desk, vb.) tek bir modüler monorepo ve PostgreSQL altyapısında sunan kurumsal AI platformudur.

---

## 📚 Mimari Dokümantasyon ve Rehberler

Platform mimarisi, veritabanı kararları, web tarafı izolasyonu ve yeni ürün ekleme standartları `docs/architecture/` klasöründe detaylıca belgelenmiştir:

- 📐 **[Platform Ana Mimari Rehberi](docs/architecture/PLATFORM_ARCHITECTURE_GUIDE.md)** — Monorepo yapısı, çekirdek servisler ve genel prensipler.
- 🗄️ **[Veritabanı Mimari Stratejisi](docs/architecture/DATABASE_STRATEGY.md)** — PostgreSQL, Asenkron SQLAlchemy 2.x, Alembic, pgvector ve Multi-Tenant şema tasarımı.
- 🌐 **[Web & Frontend Mimari Stratejisi](docs/architecture/FRONTEND_STRATEGY.md)** — Super Admin Web vs Ürün Müşteri Web izolasyonu, CORS ve API standartları.
- 🚀 **[Yeni Ürün Ekleme Oyun Kitabı (Playbook)](docs/architecture/NEW_PRODUCT_ONBOARDING_PLAYBOOK.md)** — Platforma sıfırdan yeni bir ürün (backend, DB, router, frontend) ekleme adım adım geliştirici kontrol listesi.

---

## ⚡ Hızlı Başlangıç

### 1. PostgreSQL (pgvector) Servisini Başlatma
```bash
docker compose -f infra/docker-compose.yml up -d
```

### 2. Alembic Migrasyonlarını Çalıştırma
```bash
uv run alembic upgrade head
```

### 3. FastAPI Sunucusunu Çalıştırma
```bash
uv run uvicorn panel.api_server:app --reload --port 8000
```

### 4. Frontend Panellerini Çalıştırma
- **Super Admin Paneli:** `cd frontend && npm run dev` (Port 5173)
- **Kâtip Editör Paneli:** `cd frontend_katip && npm run dev` (Port 5174)

---

## 📁 Proje Yapısı

```
Mergen_Platform/
├── core/                  # Çekirdek Servisler (LLM Gateway, Tenant Manager, Plan Guard, RAG)
├── products/              # Ürün Modülleri (mergen_product_katip, mergen_product_desk)
├── packages/              # Ortak Kütüphaneler (WhatsApp Client, Telegram Client)
├── panel/                 # Ortak FastAPI Server (api_server.py)
├── frontend/              # Super Admin Master Web (React 19 + Vite)
├── frontend_katip/        # Kâtip Editör Web (React 19 + Vite)
├── alembic/               # Merkezi Asenkron Veritabanı Migrasyon Yönetimi
├── infra/                 # Docker Compose & Altyapı Tanımları
└── docs/                  # Mimari Dokümantasyon
```
