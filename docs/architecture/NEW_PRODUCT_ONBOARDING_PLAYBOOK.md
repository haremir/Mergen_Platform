# Mergen Platform — Yeni Ürün (Modül) Ekleme Oyun Kitabı (Playbook)

> **Doküman Kodu:** DOC-ARCH-PLAYBOOK-001  
> **Amaç:** Geliştiricilerin veya AI Ajanlarının platforma sıfırdan yeni bir ürün modülünü (backend, database, API, frontend) uçtan uca eksiksiz eklemesini sağlamak.

---

## Kontrol Listesi (Checklist)

- [ ] **Aşama 1:** Backend Paket Dizini Oluşturma (`products/mergen_product_<ürün>/`)
- [ ] **Aşama 2:** SQLAlchemy Modellerini Yazma (`models.py`)
- [ ] **Aşama 3:** Modelleri Alembic ve Core Base'e Kaydetme
- [ ] **Aşama 4:** Alembic Migrasyonunu Üretme ve Canlı PostgreSQL'e Uygulama
- [ ] **Aşama 5:** FastAPI Router Yazma (`router.py`) ve `panel/api_server.py`'a Mount Etme
- [ ] **Aşama 6:** Frontend Projesini İzolasyon Kurallarına Göre Oluşturma (`frontend_<ürün>/`)
- [ ] **Aşama 7:** End-to-End (E2E) Doğrulama Testlerini Çalıştırma

---

## Adım Adım Uygulama Rehberi

### Adım 1: Backend Ürün Dizini
`products/` altında yeni klasör açın:
```
products/mergen_product_danisman/
├── __init__.py
├── models.py
├── router.py
└── engine.py
```

### Adım 2: Veritabanı Modelleri (`models.py`)
- `from mergen_core.database import Base` import edin.
- Tüm tablolarda `tenant_id = mapped_column(String(36), nullable=False, index=True)` bulundurun.
- Tablo isimlerini `<ürün>_<tablo_adı>` şeklinde belirleyin (Örn: `danisman_sessions`).

### Adım 3: Base ve Alembic Kaydı
`core/mergen_core/db_models.py` dosyasına dinamik import ekleyin:
```python
try:
    import mergen_product_danisman.models  # noqa: F401
except ImportError:
    pass
```

### Adım 4: Migrasyon Çalıştırma
```bash
docker compose -f infra/docker-compose.yml up -d
uv run alembic revision --autogenerate -m "Add danisman product tables"
uv run alembic upgrade head
```

### Adım 5: FastAPI Router Entegrasyonu (`panel/api_server.py`)
`panel/api_server.py` sonuna router'ı mount edin:
```python
try:
    from mergen_product_danisman.router import router as danisman_router
    app.include_router(danisman_router, prefix="/api/danisman")
except ImportError:
    pass
```

### Adım 6: Frontend İstemcisi
`frontend_danisman/` dizinini oluşturun, `VITE_API_BASE` ve `X-Tenant-ID` header'ı ile API çağrılarını bağlayın. CORS iznini `api_server.py` içindeki `_default_origins` dizisine ekleyin.

---

## Zorunlu Kurallar (Non-Negotiable Rules)

1. **Hiçbir ürün kendi veritabanı bağlantı havuzunu veya SQLite dosyasını açamaz.** `mergen_core.database` üzerinden `async_session_factory` kullanılmalıdır.
2. **`Base.metadata.create_all()` runtime'da çağrılamaz.** Şema değişiklikleri yalnızca Alembic üzerinden yapılır.
3. **Müşteri arayüzleri asla Super Admin paneline (`frontend/`) sayfa olarak gömülemez.** `frontend_<ürün>` izolasyonu zorunludur.
