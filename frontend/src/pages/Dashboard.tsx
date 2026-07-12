import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getLogs, getPlan } from '../api';
import type { LogEntry, PlanResult } from '../api';
import { 
  Terminal, ShieldCheck, Cpu, RefreshCw, 
  MessageSquare, User, Bot, AlertTriangle 
} from 'lucide-react';

export default function Dashboard() {
  const [searchParams] = useSearchParams();
  const [tenantId, setTenantId] = useState<string>(
    searchParams.get('tenant_id') || '4cc9eef0-82eb-54ea-9999-desktest9999'
  );

  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [plan, setPlan] = useState<PlanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchDashboardData = async (targetId: string) => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [logsData, planData] = await Promise.all([
        getLogs(targetId),
        getPlan(targetId)
      ]);
      setLogs(logsData.messages);
      setPlan(planData);
    } catch (err: any) {
      console.error(err);
      setErrorMsg(
        err.response?.data?.detail || 
        err.message || 
        'Panel API sunucusuna bağlanılamadı. Lütfen FastAPI sunucusunun çalıştığından emin olun.'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (tenantId) {
      fetchDashboardData(tenantId);
    }
  }, [tenantId]);

  const handleRefresh = () => {
    if (tenantId) fetchDashboardData(tenantId);
  };

  return (
    <div className="max-w-6xl mx-auto py-12 px-6 sm:px-8 space-y-8">
      {/* Dashboard Top Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 border-b border-gray-800 pb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
            <Cpu className="w-8 h-8 text-blue-500" />
            Kontrol Paneli
          </h1>
          <p className="text-gray-400 mt-2 text-sm">
            Gelen müşteri konuşma kayıtlarını izleyin ve aktif kota kullanım oranlarını yönetin.
          </p>
        </div>

        {/* Tenant Switcher Input Field */}
        <div className="flex items-center gap-3 bg-gray-900 border border-gray-800 p-2 rounded-lg w-full md:w-auto">
          <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider pl-2 select-none">
            Müşteri (Kiracı):
          </span>
          <input
            type="text"
            value={tenantId}
            onChange={(e) => setTenantId(e.target.value)}
            placeholder="Kiracı UUID Giriniz"
            className="bg-gray-950 border border-gray-700 text-xs font-mono text-gray-100 px-3 py-2 rounded-md w-full md:w-64 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
          />
          <button
            onClick={handleRefresh}
            disabled={loading}
            className="p-2 hover:bg-gray-800 text-gray-400 hover:text-white rounded-md transition-all cursor-pointer shrink-0"
            title="Verileri Yenile"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Alert Component */}
      {errorMsg && (
        <div className="bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div className="text-sm font-medium">
            <span className="font-semibold block">Bağlantı Hatası</span>
            <span className="opacity-95 mt-1 block leading-relaxed">{errorMsg}</span>
          </div>
        </div>
      )}

      {/* Grid Dashboard */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Card 1: Limits & Plan Status (1 Column) */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold tracking-tight text-white flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-blue-500" />
            Aylık Mesaj Kotası Kullanımı
          </h2>
          
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-6 shadow-xl">
            <div>
              <span className="text-[10px] font-semibold text-gray-500 block uppercase tracking-wider mb-1">Aktif Paket</span>
              <span className="text-2xl font-bold text-white capitalize">{plan?.plan || 'Başlangıç Paketi'}</span>
            </div>

            {plan ? (
              <div className="space-y-6">
                {Object.entries(plan.limits).map(([key, limitVal]) => {
                  const percent = Math.min(100, Math.round((limitVal.used / limitVal.limit) * 100));
                  return (
                    <div key={key} className="space-y-2">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-gray-400 capitalize">{key.replace('_', ' ')}</span>
                        <span className="text-gray-200">
                          {limitVal.used} / {limitVal.limit} {limitVal.unit.split('/')[0]}
                        </span>
                      </div>
                      
                      {/* Premium Progress Bar */}
                      <div className="w-full bg-gray-950 h-2 rounded-full overflow-hidden border border-gray-850">
                        <div 
                          className={`h-full rounded-full transition-all duration-500 ${
                            percent > 90 ? 'bg-red-500' : percent > 75 ? 'bg-amber-500' : 'bg-blue-600'
                          }`} 
                          style={{ width: `${percent}%` }}
                        />
                      </div>

                      <div className="flex justify-between text-[10px] text-gray-500 font-medium">
                        <span>%{percent} tüketildi</span>
                        <span>{limitVal.remaining} kalan</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-gray-500 text-sm py-4">Kullanım limitleri yüklenemedi.</div>
            )}
            
            <div className="border-t border-gray-800 pt-4 text-xs text-gray-500 italic leading-relaxed">
              {plan?.note || 'Standart limit tanımlaması etkin.'}
            </div>
          </div>
        </div>

        {/* Card 2: Webhook Log Stream (2 Columns) */}
        <div className="lg:col-span-2 space-y-4">
          <h2 className="text-lg font-semibold tracking-tight text-white flex items-center gap-2">
            <Terminal className="w-5 h-5 text-blue-500" />
            Canlı Mesaj Kayıtları (Loglar)
          </h2>

          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden shadow-xl min-h-[400px] flex flex-col">
            <div className="bg-gray-950 px-6 py-4 border-b border-gray-800 flex justify-between items-center shrink-0">
              <span className="text-xs font-bold text-white uppercase tracking-wider">Canlı Akış</span>
              <span className="text-[10px] text-gray-500 font-mono">KANAL: WHATSAPP</span>
            </div>

            <div className="p-6 overflow-y-auto space-y-4 flex-grow max-h-[450px]">
              {logs.length > 0 ? (
                logs.map((log) => {
                  const isInbound = log.direction === 'inbound';
                  return (
                    <div 
                      key={log.message_id} 
                      className={`flex gap-4 p-4 rounded-lg border transition-all ${
                        isInbound 
                          ? 'bg-gray-950/40 border-gray-800/80 hover:bg-gray-950/80' 
                          : 'bg-blue-600/5 border-blue-500/10 hover:bg-blue-600/10'
                      }`}
                    >
                      {/* Identity Bubble */}
                      <div className={`w-10 h-10 rounded-full shrink-0 flex items-center justify-center border ${
                        isInbound 
                          ? 'bg-gray-900 border-gray-800 text-gray-400' 
                          : 'bg-blue-600/15 border-blue-500/30 text-blue-400'
                      }`}>
                        {isInbound ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                      </div>

                      {/* Content Section */}
                      <div className="flex-grow space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-white">
                            {isInbound ? `Gönderen (${log.sender})` : 'Yapay Zeka Asistanı'}
                          </span>
                          <span className="text-[10px] text-gray-500 font-mono">
                            {new Date(log.timestamp).toLocaleTimeString()}
                          </span>
                        </div>
                        
                        <p className="text-sm text-gray-300 whitespace-pre-line leading-relaxed font-sans">
                          {log.text}
                        </p>

                        <div className="flex items-center gap-4 pt-2 text-[10px] text-gray-500 font-mono">
                          <span>MESAJID: {log.message_id}</span>
                          <span>KANAL: {log.channel.toUpperCase()}</span>
                        </div>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="flex flex-col items-center justify-center py-20 text-center space-y-3">
                  <MessageSquare className="w-12 h-12 text-gray-700" />
                  <p className="text-gray-500 text-sm">Bu Kiracı kimliğine ait yakın zamanda gerçekleşmiş bir webhook mesaj kaydı bulunamadı.</p>
                </div>
              )}
            </div>

            <div className="bg-gray-950 px-6 py-4 border-t border-gray-800 text-xs text-gray-500 text-right shrink-0">
              Simüle edilmiş canlı veri akışı gösterilmektedir. Yeni mesaj gönderildikçe burası güncellenir.
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
