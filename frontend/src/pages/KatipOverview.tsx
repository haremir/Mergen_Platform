import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  FileText, RefreshCw, Key, Eye, UserCheck, Search, X
} from 'lucide-react';
import { 
  adminGetTenants, 
  adminGetTenant, 
  adminGetTenantDrafts, 
  adminGetTenantDraft,
  adminSetTenantPassword as setPasswordApi
} from '../api';

interface AdminTenantItem {
  tenant_id: string;
  business_name: string;
  sector: string;
  plan: string;
  enabled_products: string[];
  email?: string;
  has_password: boolean;
  project_count: number;
  draft_count: number;
  created_at: string;
  bot_active: boolean;
}

interface ProjectSummary {
  id: string;
  brand_name: string;
  sector: string;
  draft_count: number;
  created_at: string;
}

interface DraftSummary {
  draft_id: string;
  topic_id: string;
  topic_title: string;
  tenant_id: string;
  brand_guide_id?: string;
  status: string;
  latest_version_number?: number;
  created_at: string;
  updated_at: string;
}

export default function KatipOverview() {
  const { tenantId: routeTenantId } = useParams<{ tenantId?: string }>();
  const navigate = useNavigate();

  const [tenants, setTenants] = useState<AdminTenantItem[]>([]);
  const [selectedTenantId, setSelectedTenantId] = useState<string>(routeTenantId || '');
  const [selectedTenantDetails, setSelectedTenantDetails] = useState<{
    tenant_id: string;
    business_name: string;
    sector: string;
    plan: string;
    email?: string;
    has_password: boolean;
    projects: ProjectSummary[];
  } | null>(null);

  useEffect(() => {
    if (routeTenantId && routeTenantId !== selectedTenantId) {
      setSelectedTenantId(routeTenantId);
    }
  }, [routeTenantId]);

  const handleSelectTenant = (tid: string) => {
    setSelectedTenantId(tid);
    navigate(`/bayiler/${tid}`);
  };

  const [drafts, setDrafts] = useState<DraftSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  // Set Password Modal State
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [targetTenantId, setTargetTenantId] = useState('');
  const [emailInput, setEmailInput] = useState('');
  const [passwordInput, setPasswordInput] = useState('');
  const [passwordLoading, setPasswordLoading] = useState(false);

  // Selected Draft Detail Modal State
  const [showDraftModal, setShowDraftModal] = useState(false);
  const [selectedDraftDetail, setSelectedDraftDetail] = useState<any>(null);
  const [draftDetailLoading, setDraftDetailLoading] = useState(false);

  // Notification state
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const showNotify = (type: 'success' | 'error', message: string) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 4000);
  };

  // Fetch all tenants
  const fetchTenantsList = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminGetTenants();
      const katipTenants = (data.items ?? []).filter((t: AdminTenantItem) => 
        !t.enabled_products || t.enabled_products.includes('katip') || t.enabled_products.length === 0
      );
      setTenants(katipTenants);
      if (katipTenants.length > 0 && !selectedTenantId) {
        setSelectedTenantId(katipTenants[0].tenant_id);
      }
    } catch (err: any) {
      showNotify('error', err.response?.data?.detail ?? 'Kiracı listesi çekilemedi.');
    } finally {
      setLoading(false);
    }
  }, [selectedTenantId]);

  // Fetch details for selected tenant
  const fetchTenantDetails = useCallback(async (tid: string) => {
    if (!tid) return;
    try {
      const [detailsData, draftsData] = await Promise.all([
        adminGetTenant(tid),
        adminGetTenantDrafts(tid),
      ]);
      setSelectedTenantDetails(detailsData);
      setDrafts(draftsData.items ?? []);
    } catch (err: any) {
      showNotify('error', err.response?.data?.detail ?? 'Kiracı detayı veya taslakları yüklenemedi.');
    }
  }, []);

  useEffect(() => {
    fetchTenantsList();
  }, [fetchTenantsList]);

  useEffect(() => {
    if (selectedTenantId) {
      fetchTenantDetails(selectedTenantId);
    }
  }, [selectedTenantId, fetchTenantDetails]);

  // Open set password modal
  const handleOpenPasswordModal = (tenant: AdminTenantItem) => {
    setTargetTenantId(tenant.tenant_id);
    setEmailInput(tenant.email || `${tenant.tenant_id}@ajans.com`);
    setPasswordInput('');
    setShowPasswordModal(true);
  };

  // Submit set password
  const handleSavePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetTenantId || !emailInput || !passwordInput) {
      showNotify('error', 'Lütfen tüm alanları doldurun.');
      return;
    }
    setPasswordLoading(true);
    try {
      await setPasswordApi(targetTenantId, emailInput.trim(), passwordInput);
      showNotify('success', `Kiracı (${targetTenantId}) için e-posta ve şifre başarıyla güncellendi!`);
      setShowPasswordModal(false);
      fetchTenantsList();
      if (selectedTenantId === targetTenantId) {
        fetchTenantDetails(targetTenantId);
      }
    } catch (err: any) {
      showNotify('error', err.response?.data?.detail ?? 'Şifre atama hatası.');
    } finally {
      setPasswordLoading(false);
    }
  };

  // View draft detail
  const handleViewDraftDetail = async (draftId: string) => {
    if (!selectedTenantId || !draftId) return;
    setDraftDetailLoading(true);
    setShowDraftModal(true);
    try {
      const data = await adminGetTenantDraft(selectedTenantId, draftId);
      setSelectedDraftDetail(data);
    } catch (err: any) {
      showNotify('error', err.response?.data?.detail ?? 'Taslak detayı çekilemedi.');
      setShowDraftModal(false);
    } finally {
      setDraftDetailLoading(false);
    }
  };

  const filteredTenants = tenants.filter(t => 
    t.business_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    t.tenant_id.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Top Header Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <span className="p-2.5 bg-indigo-600/20 border border-indigo-500/30 text-indigo-400 rounded-xl text-xl font-bold">
              ✍️
            </span>
            <div>
              <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                Süper Admin — Kâtip Ajans & Bayi Yönetimi
                <span className="text-xs bg-indigo-900/60 text-indigo-300 border border-indigo-700/50 px-2 py-0.5 rounded font-mono">
                  B2B SaaS
                </span>
              </h1>
              <p className="text-slate-400 text-xs mt-0.5">
                Kâtip ürününü kullanan ajansları, alt markalarını ve taslak içeriklerini tek noktadan denetleyin.
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={fetchTenantsList}
          className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl border border-slate-700 text-xs font-semibold flex items-center gap-2 transition-all"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Yenile
        </button>
      </div>

      {/* Notifications */}
      {notification && (
        <div className={`p-4 rounded-xl text-sm border flex items-center gap-3 ${
          notification.type === 'success' 
            ? 'bg-emerald-950/60 text-emerald-300 border-emerald-800' 
            : 'bg-red-950/60 text-red-300 border-red-800'
        }`}>
          <span>{notification.type === 'success' ? '✅' : '⚠️'}</span>
          <div>{notification.message}</div>
        </div>
      )}

      {/* Grid: Tenant Select & Projects / Drafts View */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Column: Tenant Master List */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <UserCheck className="w-4 h-4 text-indigo-400" />
              Kâtip Kullanıcısı Ajanslar ({filteredTenants.length})
            </h2>
          </div>

          <div className="relative">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Ajans adı veya Tenant ID ara..."
              className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-4 py-2.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
            {filteredTenants.map((t) => {
              const isSelected = t.tenant_id === selectedTenantId;
              return (
                <div
                  key={t.tenant_id}
                  onClick={() => handleSelectTenant(t.tenant_id)}
                  className={`p-3.5 rounded-xl border transition-all cursor-pointer space-y-2 ${
                    isSelected
                      ? 'bg-indigo-950/40 border-indigo-500/50 shadow-md'
                      : 'bg-slate-950/60 border-slate-800/80 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-bold text-white">{t.business_name}</span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                      {t.tenant_id}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-xs text-slate-400 pt-1 border-t border-slate-800/60">
                    <span>Proje: <strong className="text-indigo-400">{t.project_count}</strong></span>
                    <span>Taslak: <strong className="text-emerald-400">{t.draft_count}</strong></span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleOpenPasswordModal(t);
                      }}
                      className="px-2 py-1 bg-indigo-600/20 hover:bg-indigo-600/40 text-indigo-300 rounded border border-indigo-500/40 text-[11px] font-semibold flex items-center gap-1"
                    >
                      <Key className="w-3 h-3" />
                      {t.has_password ? 'Şifre Güncelle' : 'Şifre Ata'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: Selected Tenant Detail & Projects & Drafts */}
        <div className="lg:col-span-2 space-y-6">
          {selectedTenantDetails ? (
            <>
              {/* Tenant Header Info */}
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-bold text-white">{selectedTenantDetails.business_name}</h2>
                    <p className="text-xs text-slate-400 font-mono">ID: {selectedTenantDetails.tenant_id}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs px-2.5 py-1 rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800 font-semibold">
                      Plan: {selectedTenantDetails.plan}
                    </span>
                    <button
                      onClick={() => handleOpenPasswordModal({
                        tenant_id: selectedTenantDetails.tenant_id,
                        business_name: selectedTenantDetails.business_name,
                        sector: selectedTenantDetails.sector,
                        plan: selectedTenantDetails.plan,
                        enabled_products: ['katip'],
                        email: selectedTenantDetails.email,
                        has_password: selectedTenantDetails.has_password,
                        project_count: selectedTenantDetails.projects.length,
                        draft_count: drafts.length,
                        created_at: '',
                        bot_active: true
                      })}
                      className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all shadow-md shadow-indigo-600/20"
                    >
                      <Key className="w-3.5 h-3.5" />
                      Giriş Şifresi Tanımla
                    </button>
                  </div>
                </div>

                {/* Sub-Projects Summary */}
                <div>
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
                    Alt Projeler / Markalar ({selectedTenantDetails.projects.length})
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {selectedTenantDetails.projects.map((p) => (
                      <div key={p.id} className="bg-slate-950 border border-slate-800 rounded-xl p-3 space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-white">{p.brand_name}</span>
                          <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-indigo-300 font-mono">
                            {p.sector}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-400">Taslak İçerik: <strong className="text-slate-200">{p.draft_count}</strong></p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Drafts List for Tenant */}
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4">
                <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                  <FileText className="w-4 h-4 text-emerald-400" />
                  Üretilen Taslaklar ({drafts.length})
                </h3>

                {drafts.length === 0 ? (
                  <div className="text-center py-8 text-slate-500 text-xs italic">
                    Bu ajans henüz hiç taslak üretmemiş.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {drafts.map((d) => (
                      <div key={d.draft_id} className="bg-slate-950 border border-slate-800 rounded-xl p-3.5 flex items-center justify-between gap-4 hover:border-slate-700 transition-colors">
                        <div>
                          <h4 className="text-xs font-bold text-white">{d.topic_title}</h4>
                          <div className="flex items-center gap-2 text-[11px] text-slate-400 mt-1">
                            <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                              v{d.latest_version_number || 1}
                            </span>
                            <span className="capitalize text-indigo-400 font-semibold">{d.status}</span>
                            <span>• {new Date(d.updated_at).toLocaleDateString('tr-TR')}</span>
                          </div>
                        </div>

                        <button
                          onClick={() => handleViewDraftDetail(d.draft_id)}
                          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          Detay Gör
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center text-slate-500 text-sm italic">
              Lütfen soldaki listeden bir Ajans / Tenant seçin.
            </div>
          )}
        </div>
      </div>

      {/* Modal: Set Password */}
      {showPasswordModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-5 shadow-2xl">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Key className="w-5 h-5 text-indigo-400" />
                Kiracı Giriş Bilgileri Ata
              </h3>
              <button onClick={() => setShowPasswordModal(false)} className="text-slate-500 hover:text-slate-300">
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-slate-400">
              Bu ajansın Mergen Katip ekranına (`http://localhost:5174`) giriş yapabilmesi için e-posta ve şifre belirleyin.
            </p>

            <form onSubmit={handleSavePassword} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">E-posta</label>
                <input
                  type="email"
                  value={emailInput}
                  onChange={(e) => setEmailInput(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Şifre</label>
                <input
                  type="password"
                  value={passwordInput}
                  onChange={(e) => setPasswordInput(e.target.value)}
                  placeholder="En az 6 karakter"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                  required
                  minLength={6}
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowPasswordModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold"
                >
                  İptal
                </button>
                <button
                  type="submit"
                  disabled={passwordLoading}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-indigo-600/20"
                >
                  {passwordLoading ? 'Kaydediliyor...' : 'Kaydet'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: View Draft Detail */}
      {showDraftModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-3xl w-full max-h-[85vh] p-6 space-y-4 shadow-2xl overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <FileText className="w-5 h-5 text-emerald-400" />
                Taslak Detayı & Versiyon Geçmişi
              </h3>
              <button onClick={() => setShowDraftModal(false)} className="text-slate-500 hover:text-slate-300">
                <X className="w-5 h-5" />
              </button>
            </div>

            {draftDetailLoading ? (
              <div className="text-center py-12 text-slate-400 text-xs italic">
                Taslak yükleniyor...
              </div>
            ) : selectedDraftDetail ? (
              <div className="space-y-4 text-xs text-slate-300">
                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-white">Taslak ID: {selectedDraftDetail.draft_id}</span>
                    <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 uppercase text-[10px] font-bold">
                      {selectedDraftDetail.status}
                    </span>
                  </div>
                  <p className="text-slate-400">Versiyon Sayısı: <strong>{selectedDraftDetail.versions?.length || 0}</strong></p>
                </div>

                {selectedDraftDetail.latest_version && (
                  <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
                    <h4 className="font-bold text-slate-200">En Son Üretilen İçerik (v{selectedDraftDetail.latest_version.version_number}):</h4>
                    <div className="prose prose-invert max-w-none text-slate-300 text-xs bg-slate-900 p-4 rounded-lg font-mono whitespace-pre-wrap max-h-60 overflow-y-auto">
                      {selectedDraftDetail.latest_version.content}
                    </div>
                  </div>
                )}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
