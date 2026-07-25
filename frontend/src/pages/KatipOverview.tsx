import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { 
  FileText, Layers, CheckCircle2, RefreshCw, Cpu, Bot, Plus, Tag, Sparkles
} from 'lucide-react';

const API_BASE = 'http://localhost:8000';

interface ProjectItem {
  id: string;
  tenant_id: string;
  brand_name: string;
  sector: string;
  tone_rules?: string[];
  forbidden_words?: string[];
  is_default: boolean;
}

interface TopicItem {
  id: string;
  tenant_id: string;
  brand_guide_id?: string;
  topic_title: string;
  target_keywords?: string[];
  status: string;
  priority: number;
  created_at: string;
}

interface DraftItem {
  draft_id: string;
  topic_id: string;
  tenant_id: string;
  brand_guide_id?: string;
  status: string;
  latest_version_number: number;
  created_at: string;
  updated_at: string;
}

export default function KatipOverview() {
  const [currentTenant] = useState<string>('pilot-dental-clinic-01');
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  
  // Modals
  const [showAddProjectModal, setShowAddProjectModal] = useState(false);
  const [newBrandName, setNewBrandName] = useState('');
  const [newSector, setNewSector] = useState('dental_clinic');

  const [showAddTopicModal, setShowAddTopicModal] = useState(false);
  const [topicChips, setTopicChips] = useState<string[]>([]);
  const [topicInput, setTopicInput] = useState('');
  const [newKeywords, setNewKeywords] = useState('');
  const [newPriority] = useState(5);
  const [addTopicSubmitting, setAddTopicSubmitting] = useState(false);

  // Lists
  const [topics, setTopics] = useState<TopicItem[]>([]);
  const [topicsLoading, setTopicsLoading] = useState(false);
  const [drafts, setDrafts] = useState<DraftItem[]>([]);
  const [draftsLoading, setDraftsLoading] = useState(false);
  const [draftStatusFilter] = useState<string>('all');
  const [generatingTopicId, setGeneratingTopicId] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<'topics' | 'drafts'>('topics');
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const showNotify = (type: 'success' | 'error', message: string) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 4000);
  };

  // Fetch Projects
  const fetchProjects = useCallback(async () => {
    try {
      const { data } = await axios.get<{ items: ProjectItem[] }>(`${API_BASE}/api/katip/projects`, {
        headers: { 'X-Tenant-ID': currentTenant },
      });
      const items = data.items ?? [];
      setProjects(items);
      if (items.length > 0 && !selectedProjectId) {
        setSelectedProjectId(items[0].id);
      }
    } catch (_e) {
      console.warn("Katip projects fetch error", _e);
    }
  }, [currentTenant, selectedProjectId]);

  // Fetch Topics
  const fetchTopics = useCallback(async () => {
    setTopicsLoading(true);
    try {
      const { data } = await axios.get<{ items: TopicItem[] }>(`${API_BASE}/api/katip/topics`, {
        headers: { 'X-Tenant-ID': currentTenant },
        params: selectedProjectId ? { brand_guide_id: selectedProjectId } : {},
      });
      setTopics(data.items ?? []);
    } catch (_e) {
      console.warn("Katip topics fetch error", _e);
    } finally {
      setTopicsLoading(false);
    }
  }, [currentTenant, selectedProjectId]);

  // Fetch Drafts
  const fetchDrafts = useCallback(async () => {
    setDraftsLoading(true);
    try {
      const params: Record<string, string> = {};
      if (draftStatusFilter !== 'all') params.status_filter = draftStatusFilter;
      if (selectedProjectId) params.brand_guide_id = selectedProjectId;

      const { data } = await axios.get<{ items: DraftItem[] }>(`${API_BASE}/api/katip/drafts`, {
        headers: { 'X-Tenant-ID': currentTenant },
        params,
      });
      setDrafts(data.items ?? []);
    } catch (_e) {
      console.warn("Katip drafts fetch error", _e);
    } finally {
      setDraftsLoading(false);
    }
  }, [currentTenant, selectedProjectId, draftStatusFilter]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  useEffect(() => {
    fetchTopics();
    fetchDrafts();
  }, [fetchTopics, fetchDrafts]);

  // Handlers
  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newBrandName.trim()) return;

    try {
      const { data } = await axios.post(
        `${API_BASE}/api/katip/projects`,
        { brand_name: newBrandName.trim(), sector: newSector },
        { headers: { 'X-Tenant-ID': currentTenant } }
      );
      showNotify('success', `Yeni marka projesi eklendi: "${data.brand_name}"`);
      setNewBrandName('');
      setShowAddProjectModal(false);
      fetchProjects();
      setSelectedProjectId(data.id);
    } catch (err: any) {
      showNotify('error', err.response?.data?.detail ?? 'Proje eklenemedi.');
    }
  };

  const handleAddChip = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      const val = topicInput.trim().replace(/,/g, '');
      if (val && !topicChips.includes(val)) {
        setTopicChips((prev) => [...prev, val]);
        setTopicInput('');
      }
    }
  };

  const handleRemoveChip = (indexToRemove: number) => {
    setTopicChips((prev) => prev.filter((_, idx) => idx !== indexToRemove));
  };

  const handleCreateTopic = async (e: React.FormEvent) => {
    e.preventDefault();
    const finalTitles = [...topicChips];
    if (topicInput.trim()) finalTitles.push(topicInput.trim());

    if (finalTitles.length === 0) {
      showNotify('error', 'Lütfen en az bir konu başlığı ekleyin.');
      return;
    }

    setAddTopicSubmitting(true);
    try {
      const keywordsArray = newKeywords.split(',').map((k) => k.trim()).filter(Boolean);
      for (const tTitle of finalTitles) {
        await axios.post(
          `${API_BASE}/api/katip/topics`,
          {
            topic_title: tTitle,
            brand_guide_id: selectedProjectId || undefined,
            target_keywords: keywordsArray.length ? keywordsArray : undefined,
            priority: newPriority,
          },
          { headers: { 'X-Tenant-ID': currentTenant } }
        );
      }
      showNotify('success', `${finalTitles.length} konu kuyruğa eklendi!`);
      setTopicChips([]);
      setTopicInput('');
      setNewKeywords('');
      setShowAddTopicModal(false);
      fetchTopics();
    } catch (err: any) {
      showNotify('error', err.response?.data?.detail ?? 'Konu eklenemedi.');
    } finally {
      setAddTopicSubmitting(false);
    }
  };

  const handleGenerateDraft = async (topicId: string) => {
    setGeneratingTopicId(topicId);
    try {
      await axios.post(
        `${API_BASE}/api/katip/drafts/generate`,
        { topic_id: topicId },
        { headers: { 'X-Tenant-ID': currentTenant } }
      );
      showNotify('success', 'Taslak başarıyla üretildi ve incelemeye alındı!');
      fetchTopics();
      fetchDrafts();
      setActiveTab('drafts');
    } catch (err: any) {
      showNotify('error', err.response?.data?.detail ?? 'Taslak üretilemedi.');
    } finally {
      setGeneratingTopicId(null);
    }
  };

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto font-sans">
      {/* Notifications */}
      {notification && (
        <div className={`p-4 rounded-xl text-sm font-semibold border flex items-center justify-between ${
          notification.type === 'success' ? 'bg-emerald-950/60 border-emerald-700 text-emerald-300' : 'bg-red-950/60 border-red-700 text-red-300'
        }`}>
          <span>{notification.message}</span>
          <button onClick={() => setNotification(null)}>✕</button>
        </div>
      )}

      {/* ── HEADER & PROJECT SWITCHER ────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-900/30 shrink-0">
            <FileText className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-3">
              Mergen Kâtip Yönetim Paneli
              <span className="text-xs font-mono px-2.5 py-0.5 rounded-full bg-blue-900/40 text-blue-400 border border-blue-800/60">
                Multi-Tenant B2B
              </span>
            </h1>
            <p className="text-slate-400 text-sm mt-0.5">
              Ajanslar için Otonom SEO & Blog İçerik Motoru ve Marka İzolasyonlu RAG Yönetimi
            </p>
          </div>
        </div>

        {/* ACTIVE BRAND/PROJECT DROP DOWN */}
        <div className="flex items-center gap-3 bg-blue-950/40 border border-blue-800/60 rounded-xl px-4 py-2">
          <Sparkles className="w-4 h-4 text-blue-400" />
          <span className="text-xs text-blue-300 font-bold">Aktif Marka / Proje:</span>
          <select
            value={selectedProjectId}
            onChange={(e) => setSelectedProjectId(e.target.value)}
            className="bg-slate-900 border border-blue-600/60 rounded-lg px-3 py-1.5 text-xs text-white font-bold focus:outline-none focus:border-blue-400 cursor-pointer"
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.brand_name} ({p.sector})
              </option>
            ))}
          </select>
          <button
            onClick={() => setShowAddProjectModal(true)}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold transition-all shadow-md"
          >
            + Proje Ekle
          </button>
        </div>
      </div>

      {/* ── METRİK VE SİSTEM KARTLARI ────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase">
            <span>Kuyruktaki Konular</span>
            <Cpu className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-3xl font-extrabold text-amber-400">{topics.length}</div>
          <p className="text-xs text-slate-500">Üretim İçin Sıralandı</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase">
            <span>Üretilen Taslaklar</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-3xl font-extrabold text-emerald-400">{drafts.length}</div>
          <p className="text-xs text-slate-500">İnceleme & Onay Bekliyor</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase">
            <span>Aktif Marka Projeleri</span>
            <Layers className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-3xl font-extrabold text-purple-400">{projects.length}</div>
          <p className="text-xs text-slate-500">İzole RAG Hafızası</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase">
            <span>LLM Gateway</span>
            <Bot className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-xl font-bold text-white">Qwen 2.5 32B</div>
          <p className="text-xs text-slate-500">English XML Guardrails</p>
        </div>
      </div>

      {/* ── TAB & ACTIONS ─────────────────────────────────────────────────── */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div className="flex items-center gap-2 bg-slate-950 p-1 rounded-xl border border-slate-800">
            <button
              onClick={() => setActiveTab('topics')}
              className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                activeTab === 'topics' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-400 hover:text-white'
              }`}
            >
              Konu Kuyruğu ({topics.length})
            </button>
            <button
              onClick={() => setActiveTab('drafts')}
              className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                activeTab === 'drafts' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-400 hover:text-white'
              }`}
            >
              Taslaklar ({drafts.length})
            </button>
          </div>

          {activeTab === 'topics' && (
            <button
              onClick={() => setShowAddTopicModal(true)}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl text-xs flex items-center gap-2 shadow-lg shadow-blue-600/30"
            >
              <Plus className="w-4 h-4" /> + Yeni Konu / Makale Ekle
            </button>
          )}
        </div>

        {/* TOPICS TAB CONTENT */}
        {activeTab === 'topics' && (
          <div>
            {topicsLoading ? (
              <div className="py-12 text-center text-slate-500">Konular yükleniyor...</div>
            ) : topics.length === 0 ? (
              <div className="py-12 text-center text-slate-400 bg-slate-950/50 border border-slate-800 rounded-xl space-y-3">
                <p>Seçili projede henüz konu bulunmuyor.</p>
                <button
                  onClick={() => setShowAddTopicModal(true)}
                  className="px-4 py-2 bg-blue-600 text-white text-xs font-bold rounded-lg"
                >
                  + İlk Konuyu Ekle
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {topics.map((t) => (
                  <div
                    key={t.id}
                    className="bg-slate-950 border border-slate-800 rounded-xl p-4 flex items-center justify-between gap-4 hover:border-slate-700 transition-all"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 px-2 py-0.5 rounded uppercase">
                          {t.status}
                        </span>
                        <span className="text-xs font-bold text-blue-400 bg-blue-950 px-2 py-0.5 rounded border border-blue-800/40">
                          Öncelik: {t.priority}
                        </span>
                      </div>
                      <h4 className="text-white font-bold text-sm">{t.topic_title}</h4>
                      {t.target_keywords && (
                        <div className="flex items-center gap-1.5 text-xs text-slate-400">
                          <Tag className="w-3 h-3 text-slate-500" />
                          <span>{t.target_keywords.join(', ')}</span>
                        </div>
                      )}
                    </div>

                    <button
                      onClick={() => handleGenerateDraft(t.id)}
                      disabled={generatingTopicId === t.id}
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs rounded-xl shadow-lg shadow-emerald-900/30 disabled:opacity-50 flex items-center gap-2 shrink-0"
                    >
                      {generatingTopicId === t.id ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                          Üretiliyor...
                        </>
                      ) : (
                        <>⚡ Taslak Üret</>
                      )}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* DRAFTS TAB CONTENT */}
        {activeTab === 'drafts' && (
          <div>
            {draftsLoading ? (
              <div className="py-12 text-center text-slate-500">Taslaklar yükleniyor...</div>
            ) : drafts.length === 0 ? (
              <div className="py-12 text-center text-slate-400 bg-slate-950/50 border border-slate-800 rounded-xl">
                Henüz üretilmiş taslak bulunmuyor.
              </div>
            ) : (
              <div className="space-y-3">
                {drafts.map((d) => (
                  <div
                    key={d.draft_id}
                    className="bg-slate-950 border border-slate-800 rounded-xl p-4 flex items-center justify-between gap-4 hover:border-blue-500/50 transition-all"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded uppercase border ${
                          d.status === 'approved' ? 'bg-emerald-950 text-emerald-400 border-emerald-800' : 'bg-slate-900 text-slate-400 border-slate-700'
                        }`}>
                          {d.status}
                        </span>
                        <span className="text-xs text-slate-400 font-mono">
                          v{d.latest_version_number ?? 1}
                        </span>
                      </div>
                      <h4 className="text-white font-bold text-sm">Taslak #{d.draft_id.slice(0, 8)}</h4>
                    </div>

                    <a
                      href={`http://localhost:5174/#/drafts/${d.draft_id}`}
                      target="_blank"
                      rel="noreferrer"
                      className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs rounded-xl flex items-center gap-1.5"
                    >
                      Taslağı İncele →
                    </a>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── YENİ PROJE EKLEME MODALI ───────────────────────────────────────── */}
      {showAddProjectModal && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="font-bold text-lg text-white border-b border-slate-800 pb-3">Yeni Marka / Proje Ekle</h3>
            <form onSubmit={handleCreateProject} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Marka / Proje Adı *</label>
                <input
                  type="text"
                  required
                  value={newBrandName}
                  onChange={(e) => setNewBrandName(e.target.value)}
                  placeholder="Örn: DentSmile Klinik veya Elite İnşaat"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-sm text-white focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Sektör *</label>
                <select
                  value={newSector}
                  onChange={(e) => setNewSector(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-sm text-white focus:outline-none focus:border-blue-500"
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

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
                <button type="button" onClick={() => setShowAddProjectModal(false)} className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl text-xs font-semibold">İptal</button>
                <button type="submit" className="px-5 py-2 bg-blue-600 text-white rounded-xl text-xs font-bold">Proje Oluştur</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── YENİ KONU EKLEME MODALI (CHIPS) ───────────────────────────────── */}
      {showAddTopicModal && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <h3 className="font-bold text-lg text-white border-b border-slate-800 pb-3">Konu / Makale Ekle</h3>
            <form onSubmit={handleCreateTopic} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">Konu Başlıkları (Enter veya Virgül ile Ekleyin)</label>
                <div className="bg-slate-950 border border-slate-800 rounded-xl p-3 flex flex-wrap gap-2 min-h-[80px]">
                  {topicChips.map((chip, idx) => (
                    <span key={idx} className="bg-blue-900/40 text-blue-300 border border-blue-700/60 text-xs px-3 py-1 rounded-full flex items-center gap-1">
                      {chip}
                      <button type="button" onClick={() => handleRemoveChip(idx)} className="text-blue-400 font-bold ml-1">×</button>
                    </span>
                  ))}
                  <input
                    type="text"
                    value={topicInput}
                    onChange={(e) => setTopicInput(e.target.value)}
                    onKeyDown={handleAddChip}
                    placeholder={topicChips.length === 0 ? "Örn. Zirkonyum Diş Kaplama (Enter)..." : "Başka konu ekle..."}
                    className="flex-1 min-w-[180px] bg-transparent text-sm text-white focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1">SEO Anahtar Kelimeleri</label>
                <input
                  type="text"
                  value={newKeywords}
                  onChange={(e) => setNewKeywords(e.target.value)}
                  placeholder="zirkonyum, diş kaplama, estetik diş"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-sm text-white focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
                <button type="button" onClick={() => setShowAddTopicModal(false)} className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl text-xs font-semibold">İptal</button>
                <button type="submit" disabled={addTopicSubmitting} className="px-5 py-2 bg-blue-600 text-white rounded-xl text-xs font-bold disabled:opacity-50">
                  {addTopicSubmitting ? "Ekleniyor..." : "⚡ Konuları Kuyruğa Ekle"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
