# Mergen Platform — Web & Frontend Mimari Stratejisi

> **Doküman Kodu:** DOC-ARCH-FE-001  
> **Kapsam:** React 19, Vite, Tailwind CSS v4, Subdomain / Port İzolasyonu, REST Entegrasyonu  
> **Durum:** Onaylandı / Aktif Standart

---

## 1. Frontend Mimarisine Genel Bakış

Mergen Platform'da tek bir devasa (monolitik) frontend istemcisi **kullanılmaz**. İki temel kullanıcı segmenti vardır ve bu iki segment mimari seviyede birbirinden ayrılmıştır:

```
                             ┌───────────────────────────────────┐
                             │    FastAPI API Server             │
                             │    (panel/api_server.py)          │
                             └─────────────────┬─────────────────┘
                                               │
                       ┌───────────────────────┴───────────────────────┐
                       ▼                                               ▼
         [Super Admin Web] :5173                        [Ürün Müşteri Web] :5174+
         frontend/                                      frontend_katip/
         - Platform Operatörleri                        - SEO Ajansları / Editörler
         - Onboarding, İstatistikler                    - Taslak İnceleme, Revizyon
         - Global Sistem Ayarları                       - Konu Kuyruğu Yönetimi
```

---

## 2. Web Uygulamalarının Sınıflandırılması

### 1. Super Admin / Master Yönetim Paneli (`frontend/`)
- **Teknoloji:** React 19 + Vite + Tailwind v4 + Lucide React + React Router v7.
- **Hedef Kitle:** Mergen platform kurucuları, destek ekibi ve sistem yöneticileri.
- **Sayfa Rotaları:**
  - `/onboarding`: Yeni işletme (tenant) kaydı, WhatsApp WABA token bağlama.
  - `/dashboard`: Canlı müşteri bot durumları, durdurma/başlatma butonları.
  - `/analytics`: Gelir/gider, mesaj hacmi ve LLM kullanım analitiği.
  - `/settings`: Sistem geneli bakım modu ve global duyuru yönetimi.

### 2. Ürün Özel Müşteri / Editör Panelleri (`frontend_<ürün>/`)
- **Teknoloji:** React 19 + Vite + Tailwind v4 + Axios.
- **Hedef Kitle:** İlgili ürünü satın alan müşteriler (örn. Kâtip için SEO ajansı editörleri).
- **İzolasyon Gerekçesi:**
  - Müşteriler asla admin/onboarding ekranlarını göremez.
  - Bağımsız CI/CD ve deploy imkanı.
  - Ürüne özel UI/UX dili (örn. Kâtip için zengin metin düzenleyici ve diff görünümü).
- **Sayfa Rotaları (Örnek: Kâtip):**
  - `/topics`: Konu kuyruğu listesi ve yeni konu girme.
  - `/drafts`: Tüm taslakların durumu (`draft`, `in_review`, `approved`, `published`).
  - `/drafts/:id`: Taslak okuma alanı, versiyon geçmişi (timeline) ve revizyon iste formu (`FeedbackForm`).
  - `/brand`: Marka kuralları ve yasaklı kelime yönetimi.

---

## 3. CORS ve API İletişim Standartları

Tüm frontend istemcileri backend FastAPI sunucusuyla (`panel/api_server.py`) haberleşir.

1. **Header Standartları:**
   - `X-Tenant-ID`: İstemcinin hangi tenant bağlamında çalıştığını belirtir (Zorunlu).
   - `Content-Type`: `application/json`
2. **CORS Yapılandırması (`panel/api_server.py`):**
   ```python
   _default_origins = [
       "http://localhost:3000",   # Next.js fallback
       "http://localhost:5173",   # Super Admin Frontend
       "http://localhost:5174",   # Kâtip Web Frontend
   ]
   ```
3. **Environment Değişkenleri:**
   Her frontend projesinde `.env` (veya `.env.example`) içinde API adresi tanımlanır:
   ```env
   VITE_API_BASE=http://localhost:8000
   ```

---

## 4. Yeni Bir Ürün Web Uygulaması Oluşturma Adımları

1. **Vite şablonu ile proje oluştur:**
   ```bash
   npx create-vite@latest frontend_<ürün_adı> --template react-ts
   ```
2. **Paketleri kur (Tailwind v4 & Icons):**
   ```bash
   cd frontend_<ürün_adı>
   npm install axios lucide-react react-router-dom @tailwindcss/vite tailwindcss
   ```
3. **Port ayarını `vite.config.ts` içinde yap (Çakışmayı önlemek için):**
   ```typescript
   export default defineConfig({
     plugins: [react(), tailwindcss()],
     server: { port: 5174 } // veya boş port
   })
   ```
4. **Backend CORS İzni:** `panel/api_server.py` içindeki `_default_origins` listesine yeni portu ekle.
