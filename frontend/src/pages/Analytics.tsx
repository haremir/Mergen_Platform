import { useEffect, useState } from 'react';
import { getPlatformAnalytics } from '../api';
import type { PlatformAnalyticsResult } from '../api';
import { BarChart3, TrendingUp, DollarSign, Users, MessageSquare, AlertTriangle, RefreshCw } from 'lucide-react';

export default function Analytics() {
  const [data, setData] = useState<PlatformAnalyticsResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchAnalytics = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const stats = await getPlatformAnalytics();
      setData(stats);
    } catch (err: any) {
      console.error("API Fetch Error:", err);
      setErrorMsg(
        err.response?.data?.detail || 
        err.message || 
        'Sistem analitik verileri sunucudan çekilemedi.'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, []);

  return (
    <div className="max-w-6xl mx-auto py-12 px-6 space-y-8">
      
      {/* Header section */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 border-b border-slate-800 pb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
            <BarChart3 className="w-8 h-8 text-blue-500" />
            Analiz ve Performans Paneli
          </h1>
          <p className="text-slate-400 mt-2 text-sm">
            Mergen Platformu genelindeki finansal hacmi, sistem kaynak tüketimlerini ve kiracı büyüme oranlarını izleyin.
          </p>
        </div>

        <button
          onClick={fetchAnalytics}
          disabled={loading}
          className="flex items-center gap-2 bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 hover:text-white px-4 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Verileri Güncelle
        </button>
      </div>

      {errorMsg && (
        <div className="bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div className="text-sm font-medium">
            <span className="font-semibold block">Hata Oluştu</span>
            <span className="opacity-95 mt-1 block leading-relaxed">{errorMsg}</span>
          </div>
        </div>
      )}

      {loading && !data ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-12 text-center text-slate-400">
          Analitik veriler hesaplanıyor...
        </div>
      ) : (
        <div className="space-y-8">
          
          {/* Metrics Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            
            {/* Monthly Revenue Card */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg flex items-center justify-between">
              <div className="space-y-1">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Aylık Toplam Gelir</span>
                <span className="text-2xl font-bold text-white block">
                  {data ? `${data.revenue.toLocaleString('tr-TR')} ₺` : '0 ₺'}
                </span>
                <span className="text-[10px] text-emerald-400 flex items-center gap-0.5 font-semibold">
                  <TrendingUp className="w-3 h-3" />
                  +12.5% geçen ay
                </span>
              </div>
              <div className="w-12 h-12 bg-blue-600/10 border border-blue-500/20 rounded-xl flex items-center justify-center text-blue-500 shrink-0">
                <DollarSign className="w-6 h-6" />
              </div>
            </div>

            {/* Expenses Card */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg flex items-center justify-between">
              <div className="space-y-1">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">API / LLM Giderleri</span>
                <span className="text-2xl font-bold text-white block">
                  {data ? `${data.expenses.toLocaleString('tr-TR')} ₺` : '0 ₺'}
                </span>
                <span className="text-[10px] text-slate-500 block">
                  Net Kâr Oranı: {data ? `${((1 - data.expenses / data.revenue) * 100).toFixed(1)}%` : '0%'}
                </span>
              </div>
              <div className="w-12 h-12 bg-red-600/10 border border-red-500/20 rounded-xl flex items-center justify-center text-red-500 shrink-0">
                <DollarSign className="w-6 h-6" />
              </div>
            </div>

            {/* Active Tenants Card */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg flex items-center justify-between">
              <div className="space-y-1">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Aktif Kiracı Sayısı</span>
                <span className="text-2xl font-bold text-white block">
                  {data ? data.active_tenants : '0'}
                </span>
                <span className="text-[10px] text-slate-500 block">
                  Onay bekleyen: 1 işletme
                </span>
              </div>
              <div className="w-12 h-12 bg-indigo-600/10 border border-indigo-500/20 rounded-xl flex items-center justify-center text-indigo-500 shrink-0">
                <Users className="w-6 h-6" />
              </div>
            </div>

            {/* Total Messages Card */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg flex items-center justify-between">
              <div className="space-y-1">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">İşlenen Toplam Mesaj</span>
                <span className="text-2xl font-bold text-white block">
                  {data ? data.message_volume.toLocaleString('tr-TR') : '0'}
                </span>
                <span className="text-[10px] text-emerald-400 flex items-center gap-0.5 font-semibold">
                  <TrendingUp className="w-3 h-3" />
                  +4.2% günlük artış
                </span>
              </div>
              <div className="w-12 h-12 bg-emerald-600/10 border border-emerald-500/20 rounded-xl flex items-center justify-center text-emerald-500 shrink-0">
                <MessageSquare className="w-6 h-6" />
              </div>
            </div>

          </div>

          {/* Visual Chart Placeholders Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            
            {/* Gelir Dağılımı (Sektörlere Göre) Placeholder */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 shadow-xl space-y-6">
              <h2 className="text-lg font-semibold tracking-tight text-white border-b border-slate-850 pb-3">
                Gelir Dağılımı (Sektörlere Göre)
              </h2>
              
              {/* Dummy visual bar representation */}
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-slate-300">Kuaför / Barber</span>
                    <span className="text-white">60%</span>
                  </div>
                  <div className="w-full bg-slate-950 rounded-full h-3.5 overflow-hidden">
                    <div className="bg-blue-500 h-full rounded-full" style={{ width: '60%' }}></div>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-slate-300">Güzellik Merkezi</span>
                    <span className="text-white">25%</span>
                  </div>
                  <div className="w-full bg-slate-950 rounded-full h-3.5 overflow-hidden">
                    <div className="bg-indigo-500 h-full rounded-full" style={{ width: '25%' }}></div>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-slate-300">Restoran / Kafe</span>
                    <span className="text-white">10%</span>
                  </div>
                  <div className="w-full bg-slate-950 rounded-full h-3.5 overflow-hidden">
                    <div className="bg-teal-500 h-full rounded-full" style={{ width: '10%' }}></div>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-slate-300">Diğer Sektörler</span>
                    <span className="text-white">5%</span>
                  </div>
                  <div className="w-full bg-slate-950 rounded-full h-3.5 overflow-hidden">
                    <div className="bg-slate-700 h-full rounded-full" style={{ width: '5%' }}></div>
                  </div>
                </div>
              </div>
            </div>

            {/* Günlük API İstek Hacmi Placeholder */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 shadow-xl space-y-6">
              <h2 className="text-lg font-semibold tracking-tight text-white border-b border-slate-850 pb-3">
                Günlük API İstek Hacmi (Tüketim)
              </h2>
              
              {/* Dummy visual graph bars representation */}
              <div className="h-44 flex items-end justify-between gap-2 bg-slate-950 p-6 rounded-xl border border-slate-850 relative">
                <div className="bg-blue-600/20 hover:bg-blue-500/30 w-full h-[30%] rounded transition-all cursor-pointer" title="Pazartesi: 3.200 istek"></div>
                <div className="bg-blue-600/35 hover:bg-blue-500/40 w-full h-[55%] rounded transition-all cursor-pointer" title="Salı: 5.500 istek"></div>
                <div className="bg-blue-600/40 hover:bg-blue-500/50 w-full h-[70%] rounded transition-all cursor-pointer" title="Çarşamba: 7.000 istek"></div>
                <div className="bg-blue-600/30 hover:bg-blue-500/40 w-full h-[45%] rounded transition-all cursor-pointer" title="Perşembe: 4.500 istek"></div>
                <div className="bg-blue-600/60 hover:bg-blue-500/70 w-full h-[85%] rounded transition-all cursor-pointer" title="Cuma: 8.500 istek"></div>
                <div className="bg-blue-600 hover:bg-blue-500 w-full h-[100%] rounded transition-all cursor-pointer" title="Cumartesi: 10.000 istek"></div>
                <div className="bg-blue-600/25 hover:bg-blue-500/30 w-full h-[20%] rounded transition-all cursor-pointer" title="Pazar: 2.000 istek"></div>
                
                {/* Graph legends */}
                <div className="absolute bottom-1.5 left-0 right-0 flex justify-between px-6 text-[8px] text-slate-500 uppercase tracking-widest font-bold">
                  <span>Pzt</span>
                  <span>Sal</span>
                  <span>Çar</span>
                  <span>Per</span>
                  <span>Cum</span>
                  <span>Cmt</span>
                  <span>Paz</span>
                </div>
              </div>
            </div>

          </div>

        </div>
      )}

    </div>
  );
}
