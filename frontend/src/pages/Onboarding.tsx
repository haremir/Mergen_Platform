import { useState } from 'react';
import { submitOnboarding } from '../api';
import type { OnboardingPayload, OnboardingResult } from '../api';
import { 
  Building2, FileText, Sparkles, CheckCircle2, AlertCircle, RefreshCw 
} from 'lucide-react';

export default function Onboarding() {
  const [formData, setFormData] = useState<OnboardingPayload>({
    business_name: '',
    phone_number: '',
    business_hours: '',
    location: '',
    cancellation_policy: '',
    contact_info: '',
    services: '',
    pricing: '',
    plan: 'starter'
  });

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<OnboardingResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    setErrorMsg(null);

    try {
      const response = await submitOnboarding(formData);
      setResult(response);
      if (response.status !== 'pending_verification') {
        setErrorMsg(response.error || `Kayıt işlemi şu durumla bitti: ${response.status}`);
      }
    } catch (err: any) {
      console.error(err);
      if (err.response?.data?.detail) {
        const detail = err.response.data.detail;
        if (Array.isArray(detail)) {
          const missing = detail.map((d: any) => d.loc[d.loc.length - 1]).join(', ');
          setErrorMsg(`Doğrulama Hatası: Eksik veya hatalı alanlar: ${missing}`);
        } else {
          setErrorMsg(JSON.stringify(detail));
        }
      } else {
        setErrorMsg(err.message || 'Kayıt gönderimi sırasında beklenmeyen bir hata oluştu.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setResult(null);
    setErrorMsg(null);
  };

  return (
    <div className="max-w-4xl mx-auto py-12 px-6 sm:px-8">
      {/* Title Header */}
      <div className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
          <Sparkles className="w-8 h-8 text-blue-500 animate-pulse" />
          Yeni Müşteri Kaydı
        </h1>
        <p className="text-gray-400 mt-2 text-sm leading-relaxed">
          Mergen sistemine yeni bir işletme ekleyin. Buraya girdiğiniz bilgiler, yapay zekanın o işletme hakkında her şeyi öğrenmesini (RAG) sağlayacaktır.
        </p>
      </div>

      {!result ? (
        <form onSubmit={handleSubmit} className="space-y-8">
          
          {/* Card 1: Business Identity */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 sm:p-8 shadow-xl space-y-6">
            <div className="flex items-center gap-2 border-b border-gray-800 pb-3">
              <Building2 className="w-5 h-5 text-blue-500" />
              <h2 className="text-lg font-semibold tracking-tight text-white">İşletme Kimliği (WhatsApp Bağlantısı)</h2>
            </div>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              {/* Business Name */}
              <div>
                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                  İşletme Adı *
                </label>
                <input
                  type="text"
                  name="business_name"
                  required
                  placeholder="Örn: Acme Kuaför Salonu"
                  value={formData.business_name}
                  onChange={handleChange}
                  className="w-full bg-gray-950 border border-gray-700 text-gray-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                />
              </div>

              {/* WhatsApp Phone Number */}
              <div>
                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                  WhatsApp Numarası *
                </label>
                <input
                  type="text"
                  name="phone_number"
                  required
                  placeholder="Örn: +905551234567"
                  value={formData.phone_number}
                  onChange={handleChange}
                  className="w-full bg-gray-950 border border-gray-700 text-gray-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                />
              </div>
            </div>
          </div>

          {/* Card 2: Knowledge Ingestion */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 sm:p-8 shadow-xl space-y-6">
            <div className="flex items-center gap-2 border-b border-gray-800 pb-3">
              <FileText className="w-5 h-5 text-blue-500" />
              <h2 className="text-lg font-semibold tracking-tight text-white">Yapay Zeka Bilgi Bankası (RAG Context)</h2>
            </div>

            <div className="space-y-6">
              {/* Business Hours */}
              <div>
                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                  Çalışma Saatleri *
                </label>
                <input
                  type="text"
                  name="business_hours"
                  required
                  placeholder="Örn: Hafta içi 09:00-18:00, Cumartesi 10:00-15:00. Yapay zeka randevuları buna göre ayarlar."
                  value={formData.business_hours}
                  onChange={handleChange}
                  className="w-full bg-gray-950 border border-gray-700 text-gray-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                />
              </div>

              {/* Location */}
              <div>
                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                  Açık Adres ve Konum Tarifi *
                </label>
                <input
                  type="text"
                  name="location"
                  required
                  placeholder="Örn: Kadıköy Boğa heykelinden sağa dönünce 2. sokak. Müşterilere yol tarif ederken kullanılır."
                  value={formData.location}
                  onChange={handleChange}
                  className="w-full bg-gray-950 border border-gray-700 text-gray-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                />
              </div>

              {/* Cancellation Policy */}
              <div>
                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                  İptal ve İade Politikası *
                </label>
                <textarea
                  name="cancellation_policy"
                  required
                  rows={3}
                  placeholder="Örn: Randevuya 24 saat kaladan sonra iptal yapılamaz. Kapora yanar."
                  value={formData.cancellation_policy}
                  onChange={handleChange}
                  className="w-full bg-gray-950 border border-gray-700 text-gray-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all resize-none"
                />
              </div>

              {/* Contact Info */}
              <div>
                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                  İletişim ve Destek Bilgileri *
                </label>
                <input
                  type="text"
                  name="contact_info"
                  required
                  placeholder="Örn: Acil durumlarda ahmet@kuaför.com veya 0212 555 55 55 üzerinden bize ulaşın."
                  value={formData.contact_info}
                  onChange={handleChange}
                  className="w-full bg-gray-950 border border-gray-700 text-gray-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                />
              </div>

              {/* Additional Configurations */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
                <div>
                  <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                    Sunulan Hizmetler (Opsiyonel)
                  </label>
                  <input
                    type="text"
                    name="services"
                    placeholder="Örn: Saç kesimi, sakal tıraşı, cilt bakımı."
                    value={formData.services}
                    onChange={handleChange}
                    className="w-full bg-gray-950 border border-gray-700 text-gray-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                    Fiyatlandırma Listesi (Opsiyonel)
                  </label>
                  <input
                    type="text"
                    name="pricing"
                    placeholder="Örn: Saç Kesimi: 300 TL, Sakal: 150 TL. Fiyat soranlara bu liste verilir."
                    value={formData.pricing}
                    onChange={handleChange}
                    className="w-full bg-gray-950 border border-gray-700 text-gray-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                    Aylık Paket (Limit)
                  </label>
                  <select
                    name="plan"
                    value={formData.plan}
                    onChange={handleChange}
                    className="w-full bg-gray-950 border border-gray-700 text-gray-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all cursor-pointer"
                  >
                    <option value="starter">Başlangıç Paketi (500 Mesaj)</option>
                    <option value="business">İşletme Paketi (2000 Mesaj)</option>
                    <option value="premium">Premium (Sınırsız)</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          {/* Validation Alert */}
          {errorMsg && (
            <div className="bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl p-4 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
              <div className="text-sm font-medium">
                <span className="font-semibold block">Kayıt Başarısız Oldu</span>
                <span className="opacity-95 mt-1 block leading-relaxed">{errorMsg}</span>
              </div>
            </div>
          )}

          {/* Action CTA */}
          <div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:opacity-50 text-white font-bold py-4 rounded-lg shadow-lg hover:shadow-blue-600/10 transition-all flex items-center justify-center gap-2 cursor-pointer text-sm uppercase tracking-wider"
            >
              {loading && <RefreshCw className="w-4 h-4 animate-spin" />}
              {loading ? 'Kiracı Kaydediliyor...' : 'Müşteriyi Kaydet ve Botu Başlat'}
            </button>
          </div>
        </form>
      ) : (
        /* Success State card view */
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 sm:p-10 shadow-xl text-center space-y-6">
          {result.status === 'pending_verification' ? (
            <div className="w-16 h-16 bg-emerald-500/15 text-emerald-400 rounded-full flex items-center justify-center mx-auto mb-4 border border-emerald-500/30">
              <CheckCircle2 className="w-9 h-9" />
            </div>
          ) : (
            <div className="w-16 h-16 bg-red-500/15 text-red-400 rounded-full flex items-center justify-center mx-auto mb-4 border border-red-500/30">
              <AlertCircle className="w-9 h-9" />
            </div>
          )}

          <h2 className="text-2xl font-bold tracking-tight text-white">
            {result.status === 'pending_verification' 
              ? 'Müşteri Kaydı Başarıyla Tamamlandı!' 
              : 'Onboarding Başarısız Oldu'}
          </h2>

          <p className="text-gray-400 text-sm max-w-md mx-auto leading-relaxed">
            {result.status === 'pending_verification'
              ? 'Müşteri bilgileri doğrulandı ve RAG veritabanına aktarıldı. WhatsApp Business numara doğrulaması bekleniyor.'
              : 'Müşteri kaydı tamamlanamadı. Lütfen aşağıdaki hata detaylarını inceleyin.'}
          </p>

          <div className="bg-gray-950 border border-gray-800 rounded-xl p-6 text-left space-y-5 max-w-xl mx-auto font-sans text-sm">
            <div>
              <span className="text-[10px] font-semibold text-gray-500 block uppercase tracking-wider mb-1">Kiracı (Tenant) Kimliği</span>
              <span className="font-mono text-white block select-all break-all">{result.tenant_id}</span>
            </div>

            <div>
              <span className="text-[10px] font-semibold text-gray-500 block uppercase tracking-wider mb-1">WhatsApp Telefon No ID</span>
              <span className="font-mono text-blue-400 block break-all">
                {result.phone_number_id || 'Kayıt Yapılmadı (Simülasyon Modu)'}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-6 pt-2 border-t border-gray-900">
              <div>
                <span className="text-[10px] font-semibold text-gray-500 block uppercase tracking-wider mb-1">Bilgi Bankası</span>
                <span className="text-white font-medium block">{result.knowledge_fields_ingested} bilgi kartı eklendi</span>
              </div>
              <div>
                <span className="text-[10px] font-semibold text-gray-500 block uppercase tracking-wider mb-1">Aktif Karakter (Persona)</span>
                <span className="text-white font-medium block">{result.persona || 'Bilinmiyor'}</span>
              </div>
            </div>

            {result.error && (
              <div className="border-t border-gray-900 pt-4">
                <span className="text-[10px] font-semibold text-red-500 block uppercase tracking-wider mb-1">Karşılaşılan Hata</span>
                <span className="text-red-400 font-medium block leading-relaxed">{result.error}</span>
              </div>
            )}
          </div>

          <div className="pt-6 flex flex-col sm:flex-row gap-4 justify-center">
            <button
              onClick={handleReset}
              className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg transition-all cursor-pointer text-sm"
            >
              Yeni Bir Müşteri Kaydet
            </button>
            <button
              onClick={() => {
                window.location.hash = `#/dashboard?tenant_id=${result.tenant_id}`;
              }}
              className="bg-gray-800 hover:bg-gray-700 text-white border border-gray-700 font-semibold py-3 px-6 rounded-lg transition-all cursor-pointer text-sm"
            >
              Kontrol Paneline Git
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
