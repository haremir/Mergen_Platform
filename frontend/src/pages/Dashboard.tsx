import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getTenants, getLogs, getPlan, updateTenantSettings } from '../api';
import type { TenantListEntry, LogEntry, PlanResult } from '../api';
import { 
  ShieldCheck, Cpu, RefreshCw, 
  MessageSquare, Settings, CheckCircle2,
  Search, X, Eye, ShieldAlert
} from 'lucide-react';

export default function Dashboard() {
  const [searchParams, setSearchParams] = useSearchParams();
  
  // Master List & Filters
  const [tenants, setTenants] = useState<TenantListEntry[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [loadingTenants, setLoadingTenants] = useState(false);
  
  // Selected Tenant Details (Slide-over / Modal)
  const [selectedTenant, setSelectedTenant] = useState<TenantListEntry | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [plan, setPlan] = useState<PlanResult | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [detailsError, setDetailsError] = useState<string | null>(null);

  // Settings Override inside Slide-over
  const [botActive, setBotActive] = useState(true);
  const [promptOverride, setPromptOverride] = useState('');
  const [savingSettings, setSavingSettings] = useState(false);
  const [settingsSuccess, setSettingsSuccess] = useState<string | null>(null);

  // WhatsApp Web Chat History state
  const [activeChatSender, setActiveChatSender] = useState<string | null>(null);

  // Load master list on mount
  const fetchTenantsList = async () => {
    setLoadingTenants(true);
    try {
      const list = await getTenants();
      setTenants(list);
    } catch (err) {
      console.error('Failed to fetch tenants:', err);
    } finally {
      setLoadingTenants(false);
    }
  };

  useEffect(() => {
    fetchTenantsList();
  }, []);

  // Fetch detailed data for selected tenant
  const fetchDetails = async (tenantId: string) => {
    setLoadingDetails(true);
    setDetailsError(null);
    try {
      const [logsData, planData] = await Promise.all([
        getLogs(tenantId),
        getPlan(tenantId)
      ]);
      setLogs(logsData.messages);
      setPlan(planData);

      // Auto-select first chat sender if any logs exist
      if (logsData.messages && logsData.messages.length > 0) {
        const uniqueSenders = Array.from(new Set(logsData.messages.map((m: any) => m.sender)));
        if (uniqueSenders.length > 0) {
          setActiveChatSender(uniqueSenders[0]);
        } else {
          setActiveChatSender(null);
        }
      } else {
        setActiveChatSender(null);
      }
    } catch (err: any) {
      console.error(err);
      setDetailsError(
        err.response?.data?.detail || 
        err.message || 
        'İlgili kiracı detayları ve canlı loglar yüklenemedi.'
      );
    } finally {
      setLoadingDetails(false);
    }
  };

  // Open detail panel
  const handleOpenDetails = (tenant: TenantListEntry) => {
    setSelectedTenant(tenant);
    setBotActive(tenant.status === 'active');
    setPromptOverride('');
    setSettingsSuccess(null);
    setLogs([]);
    setPlan(null);
    setActiveChatSender(null);
    fetchDetails(tenant.tenant_id);
    
    // Sync to URL query param
    setSearchParams({ tenant_id: tenant.tenant_id });
  };

  // Close detail panel
  const handleCloseDetails = () => {
    setSelectedTenant(null);
    setSearchParams({});
  };

  // Save Settings Override
  const handleSaveSettings = async () => {
    if (!selectedTenant) return;
    setSavingSettings(true);
    setSettingsSuccess(null);
    try {
      const res = await updateTenantSettings(selectedTenant.tenant_id, {
        bot_active: botActive,
        system_prompt_override: promptOverride
      });
      setSettingsSuccess(res.message);
      
      // Update tenant status in list locally
      setTenants(prev => prev.map(t => 
        t.tenant_id === selectedTenant.tenant_id 
          ? { ...t, status: botActive ? 'active' : 'inactive' } 
          : t
      ));
      
      setTimeout(() => setSettingsSuccess(null), 4000);
    } catch (err: any) {
      console.error(err);
      setDetailsError(
        err.response?.data?.detail || 
        err.message || 
        'Ayarlar kaydedilirken hata oluştu.'
      );
    } finally {
      setSavingSettings(false);
    }
  };

  // Check URL query param on mount
  useEffect(() => {
    const urlTenantId = searchParams.get('tenant_id');
    if (urlTenantId && tenants.length > 0) {
      const matched = tenants.find(t => t.tenant_id === urlTenantId);
      if (matched) {
        handleOpenDetails(matched);
      }
    }
  }, [tenants]);

  // Filtering Logic
  const filteredTenants = tenants.filter(t => {
    const matchesSearch = t.business_name.toLowerCase().includes(searchTerm.toLowerCase()) || 
                          t.tenant_id.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || t.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  // Group logs by sender (conversations)
  const conversations: Record<string, LogEntry[]> = {};
  logs.forEach((log) => {
    if (!conversations[log.sender]) {
      conversations[log.sender] = [];
    }
    conversations[log.sender].push(log);
  });

  // Sort messages in each conversation chronologically
  const groupedChats = Object.entries(conversations).reduce((acc, [sender, msgs]) => {
    const sorted = [...msgs].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
    acc[sender] = sorted;
    return acc;
  }, {} as Record<string, LogEntry[]>);

  const senders = Object.keys(groupedChats);

  // KPI calculations
  const totalCount = tenants.length;
  const activeCount = tenants.filter(t => t.status === 'active').length;
  const pendingCount = tenants.filter(t => t.status === 'pending_verification').length;

  return (
    <div className="max-w-6xl mx-auto py-12 px-6 space-y-8 relative">
      
      {/* Header section */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 border-b border-slate-800 pb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
            <Cpu className="w-8 h-8 text-blue-500" />
            Yönetim Paneli (Master Admin)
          </h1>
          <p className="text-slate-400 mt-2 text-sm">
            Mergen Platformu genelindeki tüm müşteri kiracılarını (tenants) izleyin, kota kullanım oranlarını yönetin ve yapay zeka davranışlarını güncelleyin.
          </p>
        </div>

        <button
          onClick={fetchTenantsList}
          disabled={loadingTenants}
          className="flex items-center gap-2 bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 hover:text-white px-4 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loadingTenants ? 'animate-spin' : ''}`} />
          Müşteri Listesini Yenile
        </button>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <div className="bg-slate-900 border border-slate-800 border-l-4 border-l-blue-500 rounded-xl p-5 shadow-lg space-y-1">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Toplam Kayıtlı Müşteri</span>
          <span className="text-3xl font-bold text-white block">{totalCount}</span>
        </div>
        <div className="bg-slate-900 border border-slate-800 border-l-4 border-l-emerald-500 rounded-xl p-5 shadow-lg space-y-1">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Aktif Yapay Zeka Asistanı</span>
          <span className="text-3xl font-bold text-white block">{activeCount} / {totalCount}</span>
        </div>
        <div className="bg-slate-900 border border-slate-800 border-l-4 border-l-amber-500 rounded-xl p-5 shadow-lg space-y-1">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Onay Bekleyen İşletme</span>
          <span className="text-3xl font-bold text-white block">{pendingCount}</span>
        </div>
      </div>

      {/* Filters & Search Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
        <div className="p-6 border-b border-slate-800 bg-slate-900/60 flex flex-col sm:flex-row gap-4 justify-between items-center">
          
          {/* Search Box */}
          <div className="relative w-full sm:w-80">
            <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
              <Search className="w-4 h-4" />
            </span>
            <input
              type="text"
              placeholder="İşletme adı veya UUID ile ara..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 text-xs text-slate-100 pl-10 pr-4 py-2.5 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
            />
            {searchTerm && (
              <button 
                onClick={() => setSearchTerm('')} 
                className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-white"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Status Tabs */}
          <div className="flex gap-2 bg-slate-950 p-1 rounded-lg border border-slate-800 w-full sm:w-auto overflow-x-auto">
            <button
              onClick={() => setStatusFilter('all')}
              className={`px-3 py-1.5 rounded-md text-[11px] font-semibold transition-all cursor-pointer whitespace-nowrap ${
                statusFilter === 'all' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Tümü
            </button>
            <button
              onClick={() => setStatusFilter('active')}
              className={`px-3 py-1.5 rounded-md text-[11px] font-semibold transition-all cursor-pointer whitespace-nowrap ${
                statusFilter === 'active' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Aktif
            </button>
            <button
              onClick={() => setStatusFilter('pending_verification')}
              className={`px-3 py-1.5 rounded-md text-[11px] font-semibold transition-all cursor-pointer whitespace-nowrap ${
                statusFilter === 'pending_verification' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Onay Bekleyen
            </button>
            <button
              onClick={() => setStatusFilter('inactive')}
              className={`px-3 py-1.5 rounded-md text-[11px] font-semibold transition-all cursor-pointer whitespace-nowrap ${
                statusFilter === 'inactive' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Pasif
            </button>
          </div>
        </div>

        {/* Tenant Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-950/40 text-[10px] font-bold text-slate-500 uppercase tracking-wider select-none">
                <th className="py-4 px-6">İşletme Adı / UUID</th>
                <th className="py-4 px-6">Hizmet Sektörü</th>
                <th className="py-4 px-6">Paket</th>
                <th className="py-4 px-6">WhatsApp Durumu</th>
                <th className="py-4 px-6 text-center">Durum</th>
                <th className="py-4 px-6 text-right">İşlem</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-850">
              {filteredTenants.length > 0 ? (
                filteredTenants.map((t) => (
                  <tr 
                    key={t.tenant_id} 
                    className="hover:bg-slate-850/30 transition-colors cursor-pointer group"
                    onClick={() => handleOpenDetails(t)}
                  >
                    <td className="py-4 px-6 space-y-1">
                      <span className="font-semibold text-white block group-hover:text-blue-400 transition-colors">
                        {t.business_name}
                      </span>
                      <span className="font-mono text-[10px] text-slate-500 block">
                        {t.tenant_id}
                      </span>
                    </td>
                    <td className="py-4 px-6">
                      <span className="text-xs text-slate-300 font-medium">
                        {t.sector === 'desk' ? 'Desk (Resepsiyonist)' : t.sector}
                      </span>
                    </td>
                    <td className="py-4 px-6">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-900/30 text-blue-400 border border-blue-800/40 uppercase">
                        {t.plan}
                      </span>
                    </td>
                    <td className="py-4 px-6">
                      {t.whatsapp_phone_number_id ? (
                        <span className="font-mono text-[10px] text-emerald-400 font-medium">
                          ID: {t.whatsapp_phone_number_id}
                        </span>
                      ) : (
                        <span className="text-xs text-slate-500 font-medium italic">
                          Bağlı Değil (Simülasyon)
                        </span>
                      )}
                    </td>
                    <td className="py-4 px-6 text-center">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                        t.status === 'active' 
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                          : t.status === 'pending_verification'
                          ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          : 'bg-slate-800 text-slate-400 border border-slate-700'
                      }`}>
                        {t.status === 'active' ? 'Aktif' : t.status === 'pending_verification' ? 'Onay Bekliyor' : 'Pasif'}
                      </span>
                    </td>
                    <td className="py-4 px-6 text-right">
                      <button className="p-2 text-slate-400 group-hover:text-blue-400 hover:bg-slate-800 rounded-lg transition-all cursor-pointer">
                        <Eye className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-500 text-sm">
                    Kriterlere uygun kayıtlı kiracı bulunamadı.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
         Slide-over Detail Panel (Frosted glass fixed backdrop)
         ───────────────────────────────────────────────────────────── */}
      {selectedTenant && (
        <div className="fixed inset-0 z-50 flex justify-end">
          
          {/* Blur Backdrop overlay */}
          <div 
            onClick={handleCloseDetails}
            className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm transition-opacity"
          />

          {/* Slide panel */}
          <div className="w-full max-w-4xl bg-slate-950 border-l border-slate-800 shadow-2xl relative z-10 flex flex-col h-full overflow-hidden animate-slide-in">
            
            {/* Slide Header */}
            <div className="bg-slate-900 border-b border-slate-850 px-8 py-5 shrink-0 flex items-center justify-between">
              <div>
                <span className="text-[10px] font-bold text-blue-500 uppercase tracking-wider block mb-1">Müşteri Detay Akışı</span>
                <h3 className="text-xl font-bold text-white">{selectedTenant.business_name}</h3>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => fetchDetails(selectedTenant.tenant_id)}
                  disabled={loadingDetails}
                  className="p-2 bg-slate-800 hover:bg-slate-750 text-slate-300 hover:text-white rounded-lg transition-all cursor-pointer"
                  title="Verileri Yenile"
                >
                  <RefreshCw className={`w-4 h-4 ${loadingDetails ? 'animate-spin' : ''}`} />
                </button>
                <button
                  onClick={handleCloseDetails}
                  className="p-2 bg-slate-800 hover:bg-slate-750 text-slate-300 hover:text-white rounded-lg transition-all cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Slide Scrollable Content */}
            <div className="flex-grow overflow-y-auto p-8 space-y-8">
              
              {/* Alert Message for settings success or details error */}
              {detailsError && (
                <div className="bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl p-4 flex items-start gap-3">
                  <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" />
                  <div className="text-sm">
                    <span className="font-semibold block">Hata Oluştu</span>
                    <span className="opacity-90 block mt-1">{detailsError}</span>
                  </div>
                </div>
              )}

              {settingsSuccess && (
                <div className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-xl p-4 flex items-start gap-3">
                  <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5" />
                  <div className="text-sm font-medium">
                    <span className="font-semibold block">Değişiklikler Kaydedildi</span>
                    <span className="opacity-95 mt-1 block leading-relaxed">{settingsSuccess}</span>
                  </div>
                </div>
              )}

              {/* SECTION 1: Bot Control Center */}
              <div className="bg-slate-900 border border-slate-850 rounded-xl p-6 shadow-xl space-y-6">
                <div className="flex items-center gap-2 border-b border-slate-850 pb-3">
                  <Settings className="w-4.5 h-4.5 text-blue-500" />
                  <h4 className="text-sm font-bold text-white uppercase tracking-wider">Asistan Canlı Yönetim İstasyonu</h4>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-start">
                  {/* Active Switch */}
                  <div className="space-y-2">
                    <span className="block text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Çalışma Modu</span>
                    <div className="flex items-center gap-3 bg-slate-950 border border-slate-800 p-4.5 rounded-lg">
                      <input
                        type="checkbox"
                        id="slide_bot_active"
                        checked={botActive}
                        onChange={(e) => setBotActive(e.target.checked)}
                        className="w-4.5 h-4.5 text-blue-600 bg-slate-900 border-slate-700 rounded-md focus:ring-blue-500 cursor-pointer"
                      />
                      <label htmlFor="slide_bot_active" className="text-xs font-semibold text-slate-200 cursor-pointer">
                        Bot Yanıtı Aktif
                      </label>
                    </div>
                  </div>

                  {/* Prompt Textarea */}
                  <div className="md:col-span-2 space-y-2">
                    <span className="block text-[10px] font-semibold text-slate-400 uppercase tracking-wider text-blue-400">
                      Geçici Özel Kurallar (Örn: Bugün %10 indirim yap)
                    </span>
                    <textarea
                      rows={2}
                      placeholder="Genel karakter şablonunu değiştirmeden, sadece bugünlük kampanya kuralları, indirimler veya istisnai direktifleri buraya yazabilirsiniz. Örn: 'Bugün tüm saç kesimlerinde %10 indirimimiz olduğunu ilet.'"
                      value={promptOverride}
                      onChange={(e) => setPromptOverride(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700 text-slate-100 rounded-lg p-3 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500 font-sans"
                    />
                    <p className="text-[10px] text-slate-500 leading-relaxed">
                      Lütfen Dikkat: Burası ana sistem talimatı (Base System Prompt) yerine geçmez, sadece ana talimata anlık ek kurallar eklemek için kullanılır.
                    </p>
                  </div>
                </div>

                <div className="flex justify-end pt-3 border-t border-slate-850">
                  <button
                    onClick={handleSaveSettings}
                    disabled={savingSettings}
                    className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white font-semibold px-5 py-2 rounded-lg text-xs transition-all uppercase tracking-wider cursor-pointer"
                  >
                    {savingSettings ? 'Güncelleniyor...' : 'Konfigürasyonu Güncelle'}
                  </button>
                </div>
              </div>

              {/* SECTION 2: Quota & Usage */}
              <div className="bg-slate-900 border border-slate-850 rounded-xl p-6 shadow-xl space-y-4">
                <div className="flex items-center gap-2 border-b border-slate-850 pb-3">
                  <ShieldCheck className="w-4.5 h-4.5 text-blue-500" />
                  <h4 className="text-sm font-bold text-white uppercase tracking-wider">Abonelik Kota Analizi</h4>
                </div>

                {loadingDetails && !plan ? (
                  <div className="py-6 text-center text-xs text-slate-500">Kotalar hesaplanıyor...</div>
                ) : plan ? (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {Object.entries(plan.limits).map(([key, limitVal]) => {
                      const percent = Math.min(100, Math.round((limitVal.used / limitVal.limit) * 100));
                      return (
                        <div key={key} className="bg-slate-950 border border-slate-850 p-4 rounded-xl space-y-3">
                          <div className="flex justify-between text-xs font-semibold">
                            <span className="text-slate-400 capitalize">{key.replace('_', ' ')}</span>
                            <span className="text-slate-200">
                              {limitVal.used} / {limitVal.limit}
                            </span>
                          </div>
                          <div className="w-full bg-slate-900 h-1.5 rounded-full overflow-hidden border border-slate-800">
                            <div 
                              className={`h-full rounded-full transition-all duration-500 ${
                                percent > 90 ? 'bg-red-500' : percent > 75 ? 'bg-amber-500' : 'bg-blue-600'
                              }`} 
                              style={{ width: `${percent}%` }}
                            />
                          </div>
                          <div className="flex justify-between text-[10px] text-slate-500">
                            <span>%{percent} Tüketildi</span>
                            <span>{limitVal.remaining} Kalan</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-xs text-slate-500 italic py-2">Quota verisi yüklenemedi.</div>
                )}
              </div>

              {/* SECTION 3: WhatsApp Web-style Chat History */}
              <div className="bg-slate-900 border border-slate-850 rounded-xl overflow-hidden shadow-xl flex flex-col h-[500px]">
                <div className="bg-slate-950 px-6 py-4 border-b border-slate-850 flex justify-between items-center shrink-0">
                  <span className="text-xs font-bold text-white uppercase tracking-wider">Müşteri Sohbet Geçmişi (Canlı Akış)</span>
                  <span className="text-[10px] text-slate-500 font-mono">KANAL: WHATSAPP</span>
                </div>

                <div className="flex flex-1 overflow-hidden">
                  
                  {/* LEFT PANE: Unique customers */}
                  <div className="w-1/3 border-r border-slate-850 overflow-y-auto bg-slate-950/20">
                    {loadingDetails && logs.length === 0 ? (
                      <div className="p-6 text-center text-xs text-slate-500">Konuşmalar yükleniyor...</div>
                    ) : senders.length > 0 ? (
                      senders.map((sender) => {
                        const chatMsgs = groupedChats[sender];
                        const lastMsg = chatMsgs[chatMsgs.length - 1];
                        const isActive = activeChatSender === sender;
                        return (
                          <div
                            key={sender}
                            onClick={() => setActiveChatSender(sender)}
                            className={`p-4 border-b border-slate-850/40 cursor-pointer transition-all hover:bg-slate-800/40 ${
                              isActive ? 'bg-blue-600/10 border-l-4 border-l-blue-500' : ''
                            }`}
                          >
                            <div className="flex justify-between items-start mb-1">
                              <span className="text-xs font-bold text-slate-200 block truncate">{sender}</span>
                              <span className="text-[9px] text-slate-500 font-mono shrink-0">
                                {new Date(lastMsg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                              </span>
                            </div>
                            <p className="text-[11px] text-slate-400 truncate leading-relaxed">
                              {lastMsg.direction === 'outbound' ? 'Bot: ' : ''}{lastMsg.text}
                            </p>
                          </div>
                        );
                      })
                    ) : (
                      <div className="p-6 text-center text-xs text-slate-500 italic">Konuşma kaydı bulunamadı.</div>
                    )}
                  </div>

                  {/* RIGHT PANE: Chat History Bubbles */}
                  <div className="flex-1 flex flex-col overflow-hidden bg-slate-950/50">
                    {activeChatSender && groupedChats[activeChatSender] ? (
                      <>
                        {/* Chat Header */}
                        <div className="bg-slate-900/60 px-5 py-3 border-b border-slate-850 shrink-0 flex items-center justify-between">
                          <span className="text-xs font-semibold text-white">{activeChatSender} ile Konuşma</span>
                          <span className="text-[10px] text-slate-500 font-mono">{groupedChats[activeChatSender].length} mesaj</span>
                        </div>

                        {/* Message list container */}
                        <div className="flex-grow overflow-y-auto p-5 space-y-4 flex flex-col">
                          {groupedChats[activeChatSender].map((msg) => {
                            const isInbound = msg.direction === 'inbound';
                            return (
                              <div
                                key={msg.message_id}
                                className={`max-w-[75%] rounded-xl px-4 py-2.5 text-xs leading-relaxed space-y-1 relative group ${
                                  isInbound 
                                    ? 'bg-slate-800 text-slate-100 self-start rounded-tl-none' 
                                    : 'bg-blue-600 text-white self-end rounded-tr-none'
                                }`}
                              >
                                <p className="whitespace-pre-line font-sans select-text">{msg.text}</p>
                                <div className={`text-[8px] text-right font-mono mt-1 ${isInbound ? 'text-slate-400' : 'text-blue-200'}`}>
                                  {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </>
                    ) : (
                      <div className="flex-grow flex flex-col items-center justify-center text-center p-6 space-y-3">
                        <MessageSquare className="w-10 h-10 text-slate-700" />
                        <p className="text-slate-500 text-xs max-w-xs">Görüntülemek istediğiniz konuşmayı soldaki listeden seçin.</p>
                      </div>
                    )}
                  </div>

                </div>
              </div>

            </div>
          </div>
        </div>
      )}
    </div>
  );
}
