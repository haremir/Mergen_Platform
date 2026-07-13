import { useState } from 'react';
import { submitOnboarding } from '../api';
import type { OnboardingPayload, OnboardingResult } from '../api';
import { 
  Building2, FileText, Sparkles, CheckCircle2, AlertCircle, RefreshCw, Plus, Trash2, HelpCircle 
} from 'lucide-react';

const DAYS = [
  { key: 'monday', label: 'Pazartesi' },
  { key: 'tuesday', label: 'Salı' },
  { key: 'wednesday', label: 'Çarşamba' },
  { key: 'thursday', label: 'Perşembe' },
  { key: 'friday', label: 'Cuma' },
  { key: 'saturday', label: 'Cumartesi' },
  { key: 'sunday', label: 'Pazar' },
];

export default function Onboarding() {
  const [businessName, setBusinessName] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [metaPhoneId, setMetaPhoneId] = useState('');
  const [metaAccessToken, setMetaAccessToken] = useState('');
  
  // Structured Business Hours dictionary
  const [businessHours, setBusinessHours] = useState<Record<string, string>>({
    monday: '09:00-18:00',
    tuesday: '09:00-18:00',
    wednesday: '09:00-18:00',
    thursday: '09:00-18:00',
    friday: '09:00-18:00',
    saturday: '09:00-15:00',
    sunday: 'Kapalı',
  });

  const [location, setLocation] = useState('');
  const [cancellationPolicy, setCancellationPolicy] = useState('');
  const [contactInfo, setContactInfo] = useState('');
  const [pricing, setPricing] = useState('');
  const [plan, setPlan] = useState('starter');
  const [sector, setSector] = useState('hairdresser');
  const [persona, setPersona] = useState('friendly_energetic');

  // Dynamic lists for FAQs and Services
  const [faqs, setFaqs] = useState<{ question: string; answer: string }[]>([
    { question: 'Randevu nasıl alabilirim?', answer: 'WhatsApp hattımız üzerinden almak istediğiniz hizmeti yazarak kolayca randevu alabilirsiniz.' }
  ]);

  const [services, setServices] = useState<{ name: string; price: string; description: string }[]>([
    { name: 'Saç Kesimi', price: '300 TL', description: 'Klasik saç kesimi ve yıkama dahil.' }
  ]);

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<OnboardingResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Business Hours change handler
  const handleHourChange = (dayKey: string, val: string) => {
    setBusinessHours(prev => ({ ...prev, [dayKey]: val }));
  };

  // FAQ handlers
  const handleAddFaq = () => {
    setFaqs(prev => [...prev, { question: '', answer: '' }]);
  };

  const handleRemoveFaq = (index: number) => {
    setFaqs(prev => prev.filter((_, i) => i !== index));
  };

  const handleFaqChange = (index: number, field: 'question' | 'answer', val: string) => {
    setFaqs(prev => prev.map((item, i) => i === index ? { ...item, [field]: val } : item));
  };

  // Services handlers
  const handleAddService = () => {
    setServices(prev => [...prev, { name: '', price: '', description: '' }]);
  };

  const handleRemoveService = (index: number) => {
    setServices(prev => prev.filter((_, i) => i !== index));
  };

  const handleServiceChange = (index: number, field: 'name' | 'price' | 'description', val: string) => {
    setServices(prev => prev.map((item, i) => i === index ? { ...item, [field]: val } : item));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    setErrorMsg(null);

    // Filter out blank items before submitting
    const cleanedFaqs = faqs.filter(f => f.question.trim() !== '' && f.answer.trim() !== '');
    const cleanedServices = services.filter(s => s.name.trim() !== '');

    if (cleanedServices.length === 0) {
      setErrorMsg('Lütfen en az bir adet hizmet ekleyiniz.');
      setLoading(false);
      return;
    }

    const payload: OnboardingPayload = {
      business_name: businessName,
      phone_number: phoneNumber,
      business_hours: businessHours,
      location: location,
      cancellation_policy: cancellationPolicy,
      contact_info: contactInfo,
      services: cleanedServices,
      faqs: cleanedFaqs,
      pricing: pricing,
      plan: plan,
      sector: sector,
      persona: persona,
      meta_phone_id: metaPhoneId,
      meta_access_token: metaAccessToken || undefined
    };

    try {
      const response = await submitOnboarding(payload);
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
    <div className="max-w-4xl mx-auto py-12 px-6">
      {/* Title Header */}
      <div className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
          <Sparkles className="w-8 h-8 text-blue-500 animate-pulse" />
          Yeni Müşteri Kaydı
        </h1>
        <p className="text-slate-400 mt-2 text-sm leading-relaxed">
          Mergen sistemine yeni bir işletme ekleyin. Buraya girdiğiniz bilgiler, yapay zekanın o işletme hakkında her şeyi öğrenmesini (RAG) sağlayacaktır.
        </p>
      </div>

      {!result ? (
        <form onSubmit={handleSubmit} className="space-y-8">
          
          {/* Card 1: Business Identity & Meta API Integration */}
          <div className="bg-slate-900 border border-slate-800 border-l-4 border-l-blue-500 rounded-xl p-8 shadow-xl space-y-6">
            <div className="flex items-center gap-2 border-b border-slate-850 pb-3">
              <Building2 className="w-5 h-5 text-blue-500" />
              <h2 className="text-lg font-semibold tracking-tight text-white">İşletme Kimliği ve Meta API Entegrasyonu</h2>
            </div>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              {/* Business Name */}
              <div className="sm:col-span-2">
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  İşletme Adı *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Örn: Acme Kuaför Salonu"
                  value={businessName}
                  onChange={(e) => setBusinessName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 text-slate-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                />
              </div>

              {/* WhatsApp Phone Number */}
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  WhatsApp Telefon Numarası *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Örn: +905551234567"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 text-slate-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                />
              </div>

              {/* Meta Phone Number ID */}
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Meta Phone Number ID *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Örn: 104857204857302"
                  value={metaPhoneId}
                  onChange={(e) => setMetaPhoneId(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 text-slate-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                />
              </div>

              {/* Meta Access Token (Optional) */}
              <div className="sm:col-span-2">
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Meta Access Token (Geçici Bulut API Erişim Anahtarı - Opsiyonel)
                </label>
                <input
                  type="password"
                  placeholder="Eğer boş bırakılırsa, varsayılan platform erişim anahtarı kullanılacaktır"
                  value={metaAccessToken}
                  onChange={(e) => setMetaAccessToken(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 text-slate-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all font-mono"
                />
              </div>
            </div>
          </div>

          {/* Card 2: Business Hours (Structured) */}
          <div className="bg-slate-900 border border-slate-800 border-l-4 border-l-indigo-500 rounded-xl p-8 shadow-xl space-y-6">
            <div className="flex items-center gap-2 border-b border-slate-850 pb-3">
              <RefreshCw className="w-5 h-5 text-blue-500" />
              <h2 className="text-lg font-semibold tracking-tight text-white">Çalışma Saatleri (Haftalık Program) *</h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {DAYS.map((day) => (
                <div key={day.key} className="space-y-1">
                  <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                    {day.label}
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="Örn: 09:00-18:00 veya Kapalı"
                    value={businessHours[day.key] || ''}
                    onChange={(e) => handleHourChange(day.key, e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 text-slate-100 rounded-lg p-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                  />
                </div>
              ))}
            </div>
          </div>

          {/* Card 3: Location and Policies */}
          <div className="bg-slate-900 border border-slate-800 border-l-4 border-l-cyan-500 rounded-xl p-8 shadow-xl space-y-6">
            <div className="flex items-center gap-2 border-b border-slate-850 pb-3">
              <FileText className="w-5 h-5 text-blue-500" />
              <h2 className="text-lg font-semibold tracking-tight text-white">Temel Bilgiler ve Kurallar</h2>
            </div>

            <div className="space-y-6">
              {/* Location */}
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Açık Adres ve Konum Tarifi *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Örn: Kadıköy Boğa heykelinden sağa dönünce 2. sokak. Müşterilere yol tarif ederken kullanılır."
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 text-slate-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                />
              </div>

              {/* Cancellation Policy */}
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  İptal ve İade Politikası *
                </label>
                <textarea
                  required
                  rows={3}
                  placeholder="Örn: Randevuya 24 saat kaladan sonra iptal yapılamaz. Kapora yanar."
                  value={cancellationPolicy}
                  onChange={(e) => setCancellationPolicy(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 text-slate-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all resize-none"
                />
              </div>

              {/* Contact Info */}
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  İletişim ve Destek Bilgileri *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Örn: Acil durumlarda ahmet@kuaför.com veya 0212 555 55 55 üzerinden bize ulaşın."
                  value={contactInfo}
                  onChange={(e) => setContactInfo(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 text-slate-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                />
              </div>
            </div>
          </div>

          {/* Card 4: Services Ingestion (Dynamic) */}
          <div className="bg-slate-900 border border-slate-800 border-l-4 border-l-emerald-500 rounded-xl p-8 shadow-xl space-y-6">
            <div className="flex items-center justify-between border-b border-slate-850 pb-3">
              <div className="flex items-center gap-2">
                <Building2 className="w-5 h-5 text-blue-500" />
                <h2 className="text-lg font-semibold tracking-tight text-white">Sunulan Hizmetler Listesi *</h2>
              </div>
              <button
                type="button"
                onClick={handleAddService}
                className="flex items-center gap-1 bg-blue-600/10 hover:bg-blue-600/20 text-blue-400 border border-blue-500/20 hover:border-blue-500/40 text-xs font-semibold px-3 py-1.5 rounded-lg transition-all cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                Yeni Hizmet Ekle
              </button>
            </div>

            <div className="space-y-4">
              {services.map((service, index) => (
                <div key={index} className="flex gap-4 items-start bg-slate-950/40 border border-slate-850 p-4 rounded-xl relative group">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 flex-grow">
                    <div>
                      <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Hizmet Adı *</label>
                      <input
                        type="text"
                        required
                        placeholder="Örn: Saç Kesimi"
                        value={service.name}
                        onChange={(e) => handleServiceChange(index, 'name', e.target.value)}
                        className="w-full bg-slate-950 border border-slate-700 text-slate-100 rounded-lg p-2.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Ücret / Fiyat</label>
                      <input
                        type="text"
                        placeholder="Örn: 300 TL"
                        value={service.price}
                        onChange={(e) => handleServiceChange(index, 'price', e.target.value)}
                        className="w-full bg-slate-950 border border-slate-700 text-slate-100 rounded-lg p-2.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Açıklama (Bot Yanıtı İçin)</label>
                      <input
                        type="text"
                        placeholder="Örn: Yıkama ve fön dahildir."
                        value={service.description}
                        onChange={(e) => handleServiceChange(index, 'description', e.target.value)}
                        className="w-full bg-slate-950 border border-slate-700 text-slate-100 rounded-lg p-2.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                  </div>
                  
                  {services.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveService(index)}
                      className="mt-6 p-2 text-slate-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-all shrink-0 cursor-pointer"
                      title="Hizmeti Sil"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Card 5: FAQs Ingestion (Dynamic Stacked Layout) */}
          <div className="bg-slate-900 border border-slate-800 border-l-4 border-l-purple-500 rounded-xl p-8 shadow-xl space-y-6">
            <div className="flex items-center justify-between border-b border-slate-850 pb-3">
              <div className="flex items-center gap-2">
                <HelpCircle className="w-5 h-5 text-blue-500" />
                <h2 className="text-lg font-semibold tracking-tight text-white">Sıkça Sorulan Sorular (FAQs)</h2>
              </div>
              <button
                type="button"
                onClick={handleAddFaq}
                className="flex items-center gap-1 bg-blue-600/10 hover:bg-blue-600/20 text-blue-400 border border-blue-500/20 hover:border-blue-500/40 text-xs font-semibold px-3 py-1.5 rounded-lg transition-all cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                Yeni Soru Ekle
              </button>
            </div>

            <div className="space-y-6">
              {faqs.map((faq, index) => (
                <div key={index} className="flex gap-4 items-start bg-slate-950/40 border border-slate-850 p-6 rounded-xl relative group">
                  <div className="flex-grow space-y-4">
                    {/* Question (Full Width on Top) */}
                    <div>
                      <label className="block text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
                        Soru (Müşterinin Sorabileceği Soru) *
                      </label>
                      <input
                        type="text"
                        required
                        placeholder="Örn: Otoparkınız var mı?"
                        value={faq.question}
                        onChange={(e) => handleFaqChange(index, 'question', e.target.value)}
                        className="w-full bg-slate-950 border border-slate-700 text-slate-100 rounded-lg p-3 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                      />
                    </div>

                    {/* Answer Textarea (Full Width Stacked Below) */}
                    <div>
                      <label className="block text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
                        Cevap (Yapay Zeka Tarafından Verilecek Detaylı Cevap) *
                      </label>
                      <textarea
                        required
                        rows={3}
                        placeholder="Örn: Evet, salonumuzun önünde ücretsiz müşteri otoparkımız mevcuttur."
                        value={faq.answer}
                        onChange={(e) => handleFaqChange(index, 'answer', e.target.value)}
                        className="w-full bg-slate-950 border border-slate-700 text-slate-100 rounded-lg p-3 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all resize-none"
                      />
                    </div>
                  </div>

                  {faqs.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveFaq(index)}
                      className="mt-6 p-2 text-slate-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-all shrink-0 cursor-pointer"
                      title="Soruyu Sil"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Pricing Notes & AI Config Card */}
          <div className="bg-slate-900 border border-slate-800 border-l-4 border-l-slate-500 rounded-xl p-8 shadow-xl space-y-6">
            <div className="flex items-center gap-2 border-b border-slate-850 pb-3">
              <Sparkles className="w-5 h-5 text-blue-500" />
              <h2 className="text-lg font-semibold tracking-tight text-white">Ek Ayarlar ve Yapay Zeka Özellikleri</h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              
              {/* Faaliyet Alanı / Sektör */}
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Faaliyet Alanı / Sektör *
                </label>
                <select
                  value={sector}
                  onChange={(e) => setSector(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 text-slate-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all cursor-pointer text-xs"
                >
                  <option value="hairdresser">Kuaför / Barber</option>
                  <option value="beauty_salon">Güzellik Merkezi</option>
                  <option value="dental_clinic">Diş Kliniği</option>
                  <option value="restaurant">Restoran / Kafe</option>
                  <option value="other">Diğer</option>
                </select>
              </div>

              {/* Yapay Zeka Karakteri (Persona) */}
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Yapay Zeka Karakteri (Persona) *
                </label>
                <select
                  value={persona}
                  onChange={(e) => setPersona(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 text-slate-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all cursor-pointer text-xs"
                >
                  <option value="corporate_formal">Kurumsal / Resmi</option>
                  <option value="friendly_energetic">Samimi / Enerjik</option>
                  <option value="persuasive_sales">İkna Edici / Satış Odaklı</option>
                </select>
              </div>

              {/* Pricing notes */}
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Genel Fiyat Notları (Opsiyonel)
                </label>
                <input
                  type="text"
                  placeholder="Örn: Tüm fiyatlara KDV dahildir. Kredi kartı geçerlidir."
                  value={pricing}
                  onChange={(e) => setPricing(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 text-slate-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all text-xs"
                />
              </div>

              {/* Monthly Subscription plan */}
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Aylık Paket (Limit)
                </label>
                <select
                  value={plan}
                  onChange={(e) => setPlan(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 text-slate-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all cursor-pointer text-xs"
                >
                  <option value="starter">Başlangıç Paketi (500 Mesaj)</option>
                  <option value="business">İşletme Paketi (2000 Mesaj)</option>
                  <option value="premium">Premium (Sınırsız)</option>
                </select>
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
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 sm:p-10 shadow-xl text-center space-y-6">
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

          <p className="text-slate-400 text-sm max-w-md mx-auto leading-relaxed">
            {result.status === 'pending_verification'
              ? 'Müşteri bilgileri doğrulandı ve RAG veritabanına aktarıldı. WhatsApp Business numara doğrulaması bekleniyor.'
              : 'Müşteri kaydı tamamlanamadı. Lütfen aşağıdaki hata detaylarını inceleyin.'}
          </p>

          <div className="bg-slate-950 border border-slate-800 rounded-xl p-6 text-left space-y-5 max-w-xl mx-auto font-sans text-sm">
            <div>
              <span className="text-[10px] font-semibold text-slate-500 block uppercase tracking-wider mb-1">Kiracı (Tenant) Kimliği</span>
              <span className="font-mono text-white block select-all break-all">{result.tenant_id}</span>
            </div>

            <div>
              <span className="text-[10px] font-semibold text-slate-500 block uppercase tracking-wider mb-1">WhatsApp Telefon No ID</span>
              <span className="font-mono text-blue-400 block break-all">
                {result.phone_number_id || 'Kayıt Yapılmadı (Simülasyon Modu)'}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-6 pt-2 border-t border-slate-900">
              <div>
                <span className="text-[10px] font-semibold text-slate-500 block uppercase tracking-wider mb-1">Bilgi Bankası</span>
                <span className="text-white font-medium block">{result.knowledge_fields_ingested} bilgi kartı eklendi</span>
              </div>
              <div>
                <span className="text-[10px] font-semibold text-slate-500 block uppercase tracking-wider mb-1">Aktif Karakter (Persona)</span>
                <span className="text-white font-medium block">{result.persona || 'Bilinmiyor'}</span>
              </div>
            </div>

            {result.error && (
              <div className="border-t border-slate-900 pt-4">
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
              className="bg-slate-800 hover:bg-slate-700 text-white border border-slate-700 font-semibold py-3 px-6 rounded-lg transition-all cursor-pointer text-sm"
            >
              Kontrol Paneline Git
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
