import { useState } from 'react';
import { submitOnboarding } from '../api';
import type { OnboardingPayload, OnboardingResult } from '../api';
import { 
  Building2, Sparkles, CheckCircle2, AlertCircle, RefreshCw, Layers, Bot, Edit3, Plus, Trash2, Globe, Clock, MapPin
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
  const [contactInfo, setContactInfo] = useState('');
  const [plan, setPlan] = useState('starter');
  const [productSelection, setProductSelection] = useState<'desk' | 'katip'>('katip');

  // Mergen Desk specific state
  const [metaPhoneId, setMetaPhoneId] = useState('');
  const [useInstagram, setUseInstagram] = useState(false);
  const [instagramToken, setInstagramToken] = useState('');
  const [useTelegram, setUseTelegram] = useState(false);
  const [telegramToken, setTelegramToken] = useState('');
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
  const [persona, setPersona] = useState('friendly_energetic');
  const [services, setServices] = useState<{ name: string; price: string; description: string }[]>([
    { name: 'Genel Danışmanlık / Hizmet', price: 'Standart', description: 'Müşteri hizmet detayı' },
  ]);
  const [faqs, setFaqs] = useState<{ question: string; answer: string }[]>([
    { question: 'Çalışma saatleriniz nedir?', answer: 'Hafta içi 09:00 - 18:00 saatleri arasında hizmet vermekteyiz.' },
  ]);

  // Mergen Kâtip specific state
  const [initialBrandName, setInitialBrandName] = useState('');
  const [sector, setSector] = useState('dental_clinic');
  const [toneRules, setToneRules] = useState('Resmi, kurumsal, bilgilendirici, 3. şahıs anlatım');
  const [forbiddenWords, setForbiddenWords] = useState('en ucuz, kesin tedavi, %100 garanti');
  const [wordpressUrl, setWordpressUrl] = useState('');

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<OnboardingResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleHourChange = (dayKey: string, val: string) => {
    setBusinessHours((prev) => ({ ...prev, [dayKey]: val }));
  };

  const handleAddService = () => {
    setServices((prev) => [...prev, { name: '', price: '', description: '' }]);
  };

  const handleRemoveService = (index: number) => {
    setServices((prev) => prev.filter((_, idx) => idx !== index));
  };

  const handleServiceChange = (index: number, field: 'name' | 'price' | 'description', val: string) => {
    setServices((prev) => {
      const copy = [...prev];
      copy[index][field] = val;
      return copy;
    });
  };

  const handleAddFaq = () => {
    setFaqs((prev) => [...prev, { question: '', answer: '' }]);
  };

  const handleRemoveFaq = (index: number) => {
    setFaqs((prev) => prev.filter((_, idx) => idx !== index));
  };

  const handleFaqChange = (index: number, field: 'question' | 'answer', val: string) => {
    setFaqs((prev) => {
      const copy = [...prev];
      copy[index][field] = val;
      return copy;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!businessName.trim() || !phoneNumber.trim()) {
      setErrorMsg('Lütfen Ajans/İşletme adı ve telefon numarasını doldurunuz.');
      return;
    }

    setLoading(true);
    setResult(null);
    setErrorMsg(null);

    const payload: OnboardingPayload = {
      business_name: businessName,
      phone_number: phoneNumber,
      business_hours: businessHours,
      location: location || 'Kadıköy/İstanbul',
      cancellation_policy: cancellationPolicy || 'Standard İptal Politikası',
      contact_info: contactInfo || phoneNumber,
      services: services.filter((s) => s.name.trim()),
      faqs: faqs.filter((f) => f.question.trim()),
      plan,
      sector,
      persona,
      meta_phone_id: metaPhoneId || `META_${Date.now().toString(36)}`,
      product: productSelection,
    };

    try {
      const response = await submitOnboarding(payload);
      setResult(response);
      if (response.status !== 'pending_verification' && response.status !== 'active') {
        setErrorMsg(response.error || `Kayıt işlemi şu durumla bitti: ${response.status}`);
      }
    } catch (err: any) {
      console.error(err);
      if (err.response?.data?.detail) {
        const detail = err.response.data.detail;
        if (Array.isArray(detail)) {
          const missing = detail.map((d: any) => d.loc[d.loc.length - 1]).join(', ');
          setErrorMsg(`Doğrulama Hatası: Eksik alanlar: ${missing}`);
        } else {
          setErrorMsg(JSON.stringify(detail));
        }
      } else {
        setErrorMsg(err.message || 'Kayıt gönderimi sırasında hata oluştu.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setResult(null);
    setErrorMsg(null);
    setBusinessName('');
    setPhoneNumber('');
    setInitialBrandName('');
  };

  return (
    <div className="max-w-5xl mx-auto py-10 px-6">
      {/* Title Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
          <Sparkles className="w-8 h-8 text-blue-500 animate-pulse" />
          Yeni Müşteri & Ajans Kaydı
        </h1>
        <p className="text-slate-400 mt-2 text-sm leading-relaxed">
          Mergen platformunda yeni bir Ajans veya Kurum hesabı oluşturun. Seçtiğiniz ürüne uygun olan kayıt adımları aşağıda dinamik olarak açılacaktır.
        </p>
      </div>

      {!result ? (
        <form onSubmit={handleSubmit} className="space-y-8">
          
          {/* Card 1: Ürün Seçimi */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 shadow-xl space-y-6">
            <h2 className="text-xl font-semibold text-white flex items-center gap-2.5">
              <Layers className="w-5 h-5 text-blue-400" />
              1. Etkinleştirilecek Ürün Seçimi *
            </h2>
            <p className="text-xs text-slate-400">
              Müşterinin erişeceği ürün modülünü seçiniz. Form detayları seçtiğiniz ürüne göre otomatik güncellenir.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Option 1: Mergen Kâtip */}
              <div 
                onClick={() => setProductSelection('katip')}
                className={`cursor-pointer rounded-xl p-6 border-2 transition-all duration-200 flex flex-col justify-between ${
                  productSelection === 'katip' 
                    ? 'bg-blue-950/50 border-blue-500 shadow-xl shadow-blue-900/30 ring-2 ring-blue-500/30' 
                    : 'bg-slate-950 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="space-y-3">
                  <div className="w-12 h-12 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
                    <Edit3 className="w-6 h-6" />
                  </div>
                  <h3 className="font-bold text-white text-lg">Mergen Kâtip</h3>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    İçerik Ajansları için Otonom SEO & Blog İçerik Motoru. Çoklu Marka (Multi-Brand / Multi-Tenant) Yönetimi.
                  </p>
                </div>
                <div className="mt-5 pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs font-semibold">
                  <span className="text-slate-400">İçerik Ajansı Modeli</span>
                  {productSelection === 'katip' && <CheckCircle2 className="w-5 h-5 text-blue-400" />}
                </div>
              </div>

              {/* Option 2: Mergen Desk */}
              <div 
                onClick={() => setProductSelection('desk')}
                className={`cursor-pointer rounded-xl p-6 border-2 transition-all duration-200 flex flex-col justify-between ${
                  productSelection === 'desk' 
                    ? 'bg-emerald-950/50 border-emerald-500 shadow-xl shadow-emerald-900/30 ring-2 ring-emerald-500/30' 
                    : 'bg-slate-950 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="space-y-3">
                  <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                    <Bot className="w-6 h-6" />
                  </div>
                  <h3 className="font-bold text-white text-lg">Mergen Desk</h3>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    WhatsApp & Sosyal Medya Müşteri Destek, Randevu & Hizmet Otomasyon Botu.
                  </p>
                </div>
                <div className="mt-5 pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs font-semibold">
                  <span className="text-slate-400">Destek & Otomasyon Botu</span>
                  {productSelection === 'desk' && <CheckCircle2 className="w-5 h-5 text-emerald-400" />}
                </div>
              </div>
            </div>
          </div>

          {/* Card 2: Temel Kurum & Abonelik Bilgileri */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 shadow-xl space-y-6">
            <h2 className="text-xl font-semibold text-white flex items-center gap-2.5">
              <Building2 className="w-5 h-5 text-blue-400" />
              2. Temel Kurum & Abonelik Bilgileri
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                  Ajans / Kurum Adı *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Örn. Pixel Medya Ajansı"
                  value={businessName}
                  onChange={(e) => setBusinessName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white text-sm focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                  İletişim Telefonu *
                </label>
                <input
                  type="text"
                  required
                  placeholder="+90 555 123 45 67"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white text-sm focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                  Abonelik Paketi
                </label>
                <select
                  value={plan}
                  onChange={(e) => setPlan(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white text-sm focus:outline-none focus:border-blue-500 cursor-pointer"
                >
                  <option value="starter">Starter Plan (5 Alt Proje)</option>
                  <option value="business">Business Plan (20 Alt Proje)</option>
                  <option value="enterprise">Enterprise Plan (Sınırsız Proje)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                  İletişim E-Postası / Not
                </label>
                <input
                  type="text"
                  placeholder="iletisim@pixelmedya.com"
                  value={contactInfo}
                  onChange={(e) => setContactInfo(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white text-sm focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
          </div>

          {/* Card 3 (CONDITIONAL): MERGEN KÂTİP İLK PROJE AYARLARI */}
          {productSelection === 'katip' && (
            <div className="bg-slate-900 border border-blue-900/60 rounded-xl p-8 shadow-xl space-y-6">
              <div className="flex items-center gap-3 border-b border-slate-800 pb-4">
                <div className="p-2 bg-blue-500/10 rounded-lg text-blue-400">
                  <Edit3 className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-white">3. Mergen Kâtip İlk Marka / Proje Yapılandırması</h2>
                  <p className="text-xs text-slate-400">Ajansın yöneteceği ilk alt projenin ayarları. Daha sonra Kâtip Dashboard'undan sınırsız proje eklenebilir.</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-xs font-semibold text-blue-300 uppercase tracking-wider mb-2">
                    İlk Marka / Proje Adı
                  </label>
                  <input
                    type="text"
                    placeholder="Örn: DentSmile Diş Kliniği"
                    value={initialBrandName}
                    onChange={(e) => setInitialBrandName(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white text-sm focus:outline-none focus:border-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-blue-300 uppercase tracking-wider mb-2">
                    Sektör Kategorisi *
                  </label>
                  <select
                    value={sector}
                    onChange={(e) => setSector(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white text-sm focus:outline-none focus:border-blue-500 cursor-pointer"
                  >
                    <option value="dental_clinic">Diş Kliniği & Ağız Sağlığı</option>
                    <option value="real_estate">Gayrimenkul & İnşaat</option>
                    <option value="legal">Hukuk & Danışmanlık</option>
                    <option value="ecommerce">E-Ticaret & Perakende</option>
                    <option value="health">Sağlık & Medikal</option>
                    <option value="tech">Teknoloji & Yazılım</option>
                    <option value="general">Genel Sektör</option>
                  </select>
                </div>

                <div className="md:col-span-2">
                  <label className="block text-xs font-semibold text-blue-300 uppercase tracking-wider mb-2">
                    Marka Tonu ve Üslup Kuralları (Tone Guidelines)
                  </label>
                  <textarea
                    rows={2}
                    placeholder="Resmi, bilimsel kaynaklara dayalı, hasta bilgilendirme odaklı dil kullanın."
                    value={toneRules}
                    onChange={(e) => setToneRules(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-white text-sm focus:outline-none focus:border-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-blue-300 uppercase tracking-wider mb-2">
                    Yasaklı Kelimeler (Forbidden Words)
                  </label>
                  <input
                    type="text"
                    placeholder="en ucuz, %100 kesin tedavi, ucuz kaplama"
                    value={forbiddenWords}
                    onChange={(e) => setForbiddenWords(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white text-sm focus:outline-none focus:border-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-blue-300 uppercase tracking-wider mb-2">
                    WordPress CMS URL (Opsiyonel Entegrasyon)
                  </label>
                  <input
                    type="url"
                    placeholder="https://dentsmile.com"
                    value={wordpressUrl}
                    onChange={(e) => setWordpressUrl(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white text-sm focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Card 4 (CONDITIONAL): MERGEN DESK BOT AYARLARI */}
          {productSelection === 'desk' && (
            <div className="bg-slate-900 border border-emerald-900/60 rounded-xl p-8 shadow-xl space-y-6">
              <div className="flex items-center gap-3 border-b border-slate-800 pb-4">
                <div className="p-2 bg-emerald-500/10 rounded-lg text-emerald-400">
                  <Bot className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-white">
                    3. Mergen Desk Müşteri Destek Botu Ayarları
                  </h2>
                  <p className="text-xs text-slate-400">WhatsApp, Instagram ve Telegram müşteri yanıt botu yapılandırması.</p>
                </div>
              </div>

              <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-xs font-semibold text-emerald-300 uppercase tracking-wider mb-2">
                      Meta WhatsApp Phone ID *
                    </label>
                    <input
                      type="text"
                      placeholder="Örn: 104857204857302"
                      value={metaPhoneId}
                      onChange={(e) => setMetaPhoneId(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white text-sm focus:outline-none focus:border-emerald-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-emerald-300 uppercase tracking-wider mb-2">
                      Bot Karakteri (Persona)
                    </label>
                    <select
                      value={persona}
                      onChange={(e) => setPersona(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white text-sm focus:outline-none focus:border-emerald-500 cursor-pointer"
                    >
                      <option value="friendly_energetic">Samimi & Enerjik</option>
                      <option value="professional_medical">Profesyonel & Klinik Tıbbi</option>
                      <option value="corporate_authoritative">Kurumsal & Otoriter</option>
                    </select>
                  </div>
                </div>

                {/* Social Entegrasyon Toggles */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 border-t border-slate-800 pt-4">
                  <label className="flex items-center gap-3 cursor-pointer select-none bg-slate-950 p-3 rounded-lg border border-slate-800">
                    <input
                      type="checkbox"
                      checked={useInstagram}
                      onChange={(e) => setUseInstagram(e.target.checked)}
                      className="w-4 h-4 rounded border-slate-700 bg-slate-900 text-emerald-500 focus:ring-emerald-500"
                    />
                    <span className="text-xs text-slate-300 font-semibold">Instagram DM Botunu Aktifleştir</span>
                  </label>
                  
                  <label className="flex items-center gap-3 cursor-pointer select-none bg-slate-950 p-3 rounded-lg border border-slate-800">
                    <input
                      type="checkbox"
                      checked={useTelegram}
                      onChange={(e) => setUseTelegram(e.target.checked)}
                      className="w-4 h-4 rounded border-slate-700 bg-slate-900 text-emerald-500 focus:ring-emerald-500"
                    />
                    <span className="text-xs text-slate-300 font-semibold">Telegram Botunu Aktifleştir</span>
                  </label>
                </div>

                {useInstagram && (
                  <div>
                    <label className="block text-xs font-semibold text-emerald-300 uppercase tracking-wider mb-2">
                      Instagram Graph API Access Token
                    </label>
                    <input
                      type="password"
                      placeholder="IGQV..."
                      value={instagramToken}
                      onChange={(e) => setInstagramToken(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-white font-mono text-xs focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                )}

                {useTelegram && (
                  <div>
                    <label className="block text-xs font-semibold text-emerald-300 uppercase tracking-wider mb-2">
                      Telegram Bot Token
                    </label>
                    <input
                      type="password"
                      placeholder="123456789:ABC..."
                      value={telegramToken}
                      onChange={(e) => setTelegramToken(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-white font-mono text-xs focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                )}

                {/* Working Hours */}
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <Clock className="w-4 h-4 text-emerald-400" />
                    <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Çalışma Saatleri</label>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {DAYS.map((d) => (
                      <div key={d.key} className="bg-slate-950 p-2.5 rounded-lg border border-slate-800">
                        <span className="text-[10px] text-slate-400 font-semibold block uppercase mb-1">{d.label}</span>
                        <input
                          type="text"
                          value={businessHours[d.key] || ''}
                          onChange={(e) => handleHourChange(d.key, e.target.value)}
                          className="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-white focus:outline-none focus:border-emerald-500"
                        />
                      </div>
                    ))}
                  </div>
                </div>

                {/* Address & Policy */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <MapPin className="w-4 h-4 text-emerald-400" />
                      <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Adres & Konum Tarifi</label>
                    </div>
                    <textarea
                      rows={2}
                      placeholder="Kadıköy Mah. Atatürk Cad. No:12, Kadıköy/İstanbul"
                      value={location}
                      onChange={(e) => setLocation(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-white text-sm focus:outline-none focus:border-emerald-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">İptal & İade Politikası</label>
                    <textarea
                      rows={2}
                      placeholder="Randevular en geç 24 saat öncesinden iptal edilebilir."
                      value={cancellationPolicy}
                      onChange={(e) => setCancellationPolicy(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-white text-sm focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                </div>

                {/* Services Dynamic List */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-emerald-300 uppercase tracking-wider">Sunulan Hizmetler & Fiyatlar</label>
                    <button
                      type="button"
                      onClick={handleAddService}
                      className="px-3 py-1 bg-emerald-600/20 text-emerald-400 border border-emerald-500/30 rounded-lg text-xs font-semibold hover:bg-emerald-600/30 flex items-center gap-1"
                    >
                      <Plus className="w-3.5 h-3.5" /> Hizmet Ekle
                    </button>
                  </div>

                  {services.map((serv, idx) => (
                    <div key={idx} className="bg-slate-950 border border-slate-800 rounded-lg p-3 grid grid-cols-1 sm:grid-cols-12 gap-3 items-center">
                      <input
                        type="text"
                        placeholder="Hizmet Adı"
                        value={serv.name}
                        onChange={(e) => handleServiceChange(idx, 'name', e.target.value)}
                        className="sm:col-span-4 bg-slate-900 border border-slate-700 rounded p-2 text-xs text-white"
                      />
                      <input
                        type="text"
                        placeholder="Fiyat"
                        value={serv.price}
                        onChange={(e) => handleServiceChange(idx, 'price', e.target.value)}
                        className="sm:col-span-3 bg-slate-900 border border-slate-700 rounded p-2 text-xs text-white"
                      />
                      <input
                        type="text"
                        placeholder="Açıklama"
                        value={serv.description}
                        onChange={(e) => handleServiceChange(idx, 'description', e.target.value)}
                        className="sm:col-span-4 bg-slate-900 border border-slate-700 rounded p-2 text-xs text-white"
                      />
                      <div className="sm:col-span-1 flex justify-center">
                        {services.length > 1 && (
                          <button type="button" onClick={() => handleRemoveService(idx)} className="text-slate-500 hover:text-red-400">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {/* FAQs Dynamic List */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-emerald-300 uppercase tracking-wider">Sıkça Sorulan Sorular (SSS)</label>
                    <button
                      type="button"
                      onClick={handleAddFaq}
                      className="px-3 py-1 bg-emerald-600/20 text-emerald-400 border border-emerald-500/30 rounded-lg text-xs font-semibold hover:bg-emerald-600/30 flex items-center gap-1"
                    >
                      <Plus className="w-3.5 h-3.5" /> SSS Ekle
                    </button>
                  </div>

                  {faqs.map((faq, idx) => (
                    <div key={idx} className="bg-slate-950 border border-slate-800 rounded-lg p-3 space-y-2">
                      <div className="flex items-center justify-between gap-2">
                        <input
                          type="text"
                          placeholder="Soru (Örn: Otopark var mı?)"
                          value={faq.question}
                          onChange={(e) => handleFaqChange(idx, 'question', e.target.value)}
                          className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-xs text-white font-semibold"
                        />
                        {faqs.length > 1 && (
                          <button type="button" onClick={() => handleRemoveFaq(idx)} className="text-slate-500 hover:text-red-400">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                      <textarea
                        rows={2}
                        placeholder="Cevap"
                        value={faq.answer}
                        onChange={(e) => handleFaqChange(idx, 'answer', e.target.value)}
                        className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-xs text-white"
                      />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

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
              className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:opacity-50 text-white font-bold py-4 rounded-xl shadow-xl shadow-blue-900/30 transition-all flex items-center justify-center gap-2 cursor-pointer text-sm uppercase tracking-wider"
            >
              {loading && <RefreshCw className="w-4 h-4 animate-spin" />}
              {loading ? 'Kiracı Kaydediliyor...' : '🚀 Ajans Kaydını Tamamla ve Hesabı Aktifleştir'}
            </button>
          </div>
        </form>
      ) : (
        /* Success State card view */
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 sm:p-10 shadow-xl text-center space-y-6">
          <div className="w-16 h-16 bg-emerald-500/15 text-emerald-400 rounded-full flex items-center justify-center mx-auto mb-4 border border-emerald-500/30">
            <CheckCircle2 className="w-9 h-9" />
          </div>

          <h2 className="text-2xl font-bold tracking-tight text-white">
            Müşteri / Ajans Kaydı Başarıyla Tamamlandı!
          </h2>

          <p className="text-slate-400 text-sm max-w-md mx-auto leading-relaxed">
            Ajans hesabı ve seçilen ürün modülleri başarıyla oluşturuldu ve RAG veritabanına aktarıldı.
          </p>

          <div className="bg-slate-950 border border-slate-800 rounded-xl p-6 text-left space-y-4 max-w-xl mx-auto font-sans text-sm">
            <div>
              <span className="text-[10px] font-semibold text-slate-500 block uppercase tracking-wider mb-1">Kiracı (Tenant) Kimliği</span>
              <span className="font-mono text-white block select-all break-all">{result.tenant_id}</span>
            </div>

            <div className="grid grid-cols-2 gap-4 pt-2 border-t border-slate-900">
              <div>
                <span className="text-[10px] font-semibold text-slate-500 block uppercase tracking-wider mb-1">Seçilen Ürün</span>
                <span className="text-blue-400 font-bold uppercase block">{productSelection}</span>
              </div>
              <div>
                <span className="text-[10px] font-semibold text-slate-500 block uppercase tracking-wider mb-1">Bilgi Kartları</span>
                <span className="text-emerald-400 font-bold block">{result.knowledge_fields_ingested} eklendi</span>
              </div>
            </div>
          </div>

          <div className="pt-6 flex flex-col sm:flex-row gap-4 justify-center">
            <button
              onClick={handleReset}
              className="bg-slate-800 hover:bg-slate-700 text-white font-semibold py-3 px-6 rounded-xl transition-all text-sm"
            >
              + Yeni Müşteri Ekle
            </button>
            <a
              href="http://localhost:5174"
              target="_blank"
              rel="noreferrer"
              className="bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 px-6 rounded-xl transition-all text-sm flex items-center justify-center gap-2 shadow-lg shadow-blue-600/30"
            >
              <Globe className="w-4 h-4" /> Kâtip Web Uygulamasını Aç →
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
