import { useEffect, useState } from 'react';
import { getPlatformSettings, updatePlatformSettings } from '../api';
import { Settings as SettingsIcon, RefreshCw, CheckCircle2, AlertTriangle, MessageSquare, ShieldAlert } from 'lucide-react';

export default function Settings() {
  const [maintenanceMode, setMaintenanceMode] = useState(false);
  const [allowNewRegistrations, setAllowNewRegistrations] = useState(true);
  const [globalSystemAlerts, setGlobalSystemAlerts] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchSettings = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await getPlatformSettings();
      setMaintenanceMode(data.maintenance_mode);
      setAllowNewRegistrations(data.allow_new_registrations);
      setGlobalSystemAlerts(data.global_system_alerts || '');
    } catch (err: any) {
      console.error("API Fetch Error:", err);
      setErrorMsg(
        err.response?.data?.detail || 
        err.message || 
        'Global platform ayarları yüklenemedi. Sunucu bağlantısını kontrol edin.'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSuccessMsg(null);
    setErrorMsg(null);

    try {
      const res = await updatePlatformSettings({
        maintenance_mode: maintenanceMode,
        allow_new_registrations: allowNewRegistrations,
        global_system_alerts: globalSystemAlerts
      });
      setSuccessMsg(res.message || 'Ayarlar başarıyla güncellendi.');
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: any) {
      console.error("API Fetch Error:", err);
      setErrorMsg(
        err.response?.data?.detail || 
        err.message || 
        'Ayarlar kaydedilirken bir hata oluştu.'
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-12 px-6 space-y-8">
      
      {/* Title Header */}
      <div className="flex justify-between items-center border-b border-slate-800 pb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
            <SettingsIcon className="w-8 h-8 text-blue-500" />
            Platform ve Sistem Ayarları
          </h1>
          <p className="text-slate-400 mt-2 text-sm">
            Mergen Platformu genelindeki global sistem durumlarını, erişim kısıtlamalarını ve sistem bildirimlerini yapılandırın.
          </p>
        </div>

        <button
          onClick={fetchSettings}
          disabled={loading}
          className="flex items-center gap-2 bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 hover:text-white px-4 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Ayarları Yenile
        </button>
      </div>

      {/* Error & Success banners */}
      {errorMsg && (
        <div className="bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div className="text-sm font-medium">
            <span className="font-semibold block">Hata Oluştu</span>
            <span className="opacity-95 mt-1 block leading-relaxed">{errorMsg}</span>
          </div>
        </div>
      )}

      {successMsg && (
        <div className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-xl p-4 flex items-start gap-3">
          <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5" />
          <div className="text-sm font-medium">
            <span className="font-semibold block">Başarılı</span>
            <span className="opacity-95 mt-1 block leading-relaxed">{successMsg}</span>
          </div>
        </div>
      )}

      {loading && !globalSystemAlerts && !maintenanceMode ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center text-slate-400">
          Global ayarlar yükleniyor...
        </div>
      ) : (
        <form onSubmit={handleSave} className="space-y-8">
          
          {/* Card 1: Platform status triggers */}
          <div className="bg-slate-900 border border-slate-800 border-l-4 border-l-blue-500 rounded-xl p-8 shadow-xl space-y-6">
            <div className="flex items-center gap-2 border-b border-slate-850 pb-3">
              <ShieldAlert className="w-5 h-5 text-blue-500" />
              <h2 className="text-lg font-semibold tracking-tight text-white">Sistem Erişim Kontrolleri</h2>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Maintenance Mode Toggle */}
              <div className="bg-slate-950 border border-slate-800 rounded-xl p-6 flex flex-col justify-between space-y-4">
                <div className="space-y-1">
                  <span className="text-sm font-bold text-white flex items-center gap-2">
                    Bakım Modu (Maintenance Mode)
                  </span>
                  <p className="text-[11px] text-slate-400 leading-relaxed">
                    Sistemi bakım moduna aldığınızda tüm kiracı asistanları geçici olarak pasif duruma geçer ve API isteklerine bakım yanıtı döner.
                  </p>
                </div>
                
                <div className="flex items-center justify-between pt-2">
                  <span className={`text-xs font-semibold uppercase ${maintenanceMode ? 'text-amber-500 font-bold' : 'text-slate-500'}`}>
                    {maintenanceMode ? 'Aktif (Bakımda)' : 'Pasif (Çevrimiçi)'}
                  </span>
                  
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={maintenanceMode}
                      onChange={(e) => setMaintenanceMode(e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600 peer-checked:after:bg-white"></div>
                  </label>
                </div>
              </div>

              {/* Close Registrations Toggle */}
              <div className="bg-slate-950 border border-slate-800 rounded-xl p-6 flex flex-col justify-between space-y-4">
                <div className="space-y-1">
                  <span className="text-sm font-bold text-white flex items-center gap-2">
                    Yeni Müşteri Kayıtları
                  </span>
                  <p className="text-[11px] text-slate-400 leading-relaxed">
                    Yeni müşteri kayıtlarını kapattığınızda, Onboarding kayıt formu doldurulsa dahi sisteme yeni kiracı kaydedilmeyecektir.
                  </p>
                </div>
                
                <div className="flex items-center justify-between pt-2">
                  <span className={`text-xs font-semibold uppercase ${allowNewRegistrations ? 'text-emerald-500 font-bold' : 'text-red-500 font-bold'}`}>
                    {allowNewRegistrations ? 'Açık' : 'Kapalı (Yeni Kayıt Yok)'}
                  </span>
                  
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={!allowNewRegistrations}
                      onChange={(e) => setAllowNewRegistrations(!e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-red-600 peer-checked:after:bg-white"></div>
                  </label>
                </div>
              </div>
            </div>
          </div>

          {/* Card 2: Platform system alert notification settings */}
          <div className="bg-slate-900 border border-slate-800 border-l-4 border-l-indigo-500 rounded-xl p-8 shadow-xl space-y-6">
            <div className="flex items-center gap-2 border-b border-slate-850 pb-3">
              <MessageSquare className="w-5 h-5 text-blue-500" />
              <h2 className="text-lg font-semibold tracking-tight text-white">Sistem Bildirim Ayarları</h2>
            </div>
            
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Global Sistem Uyarı Mesajı (Admin Duyurusu)
                </label>
                <textarea
                  rows={4}
                  placeholder="Örn: 15 Temmuz tarihinde planlı veritabanı bakımı yapılacaktır."
                  value={globalSystemAlerts}
                  onChange={(e) => setGlobalSystemAlerts(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 text-slate-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all text-xs resize-none font-sans"
                />
                <p className="text-[11px] text-slate-500 mt-1.5 leading-relaxed">
                  Bu alana yazdığınız metin, platformdaki tüm kiracıların panel giriş ekranlarında global bir duyuru bandı olarak görüntülenecektir.
                </p>
              </div>
            </div>
          </div>

          {/* Action Save CTA */}
          <div>
            <button
              type="submit"
              disabled={saving}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-850 text-white font-bold py-4 rounded-lg shadow-lg hover:shadow-blue-600/10 transition-all flex items-center justify-center gap-2 cursor-pointer text-sm uppercase tracking-wider font-semibold"
            >
              {saving && <RefreshCw className="w-4 h-4 animate-spin" />}
              {saving ? 'Kaydediliyor...' : 'Sistem Ayarlarını Kaydet'}
            </button>
          </div>

        </form>
      )}

    </div>
  );
}
