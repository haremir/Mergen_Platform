/**
 * KatipDashboard.tsx
 * ──────────────────
 * Mergen Kâtip — Konu Kuyruğu & Taslak Yönetim Paneli
 *
 * Özellikler:
 *   - Müşteri (Tenant) Seçimi & Değiştirme
 *   - Konu Kuyruğu (Topic Queue): Öncelik, Durum etiketleri, Manuel Konu Ekleme
 *   - Tek Tıkla Taslak Üretimi (POST /api/katip/drafts/generate)
 *   - Taslak Listesi: Durum Filtreleri (Tümü, Taslak, İncelemede, Onaylandı, Yayınlandı)
 *   - Editör Detayına Yönlendirme (/drafts/:draftId)
 */

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import axios, { AxiosError } from "axios";

const API_BASE = (import.meta as any).env?.VITE_API_BASE ?? "http://localhost:8000";

function getTenantId(): string {
  return localStorage.getItem("katip_tenant_id") ?? "pilot-dental-clinic-01";
}

function setTenantId(id: string): void {
  localStorage.setItem("katip_tenant_id", id.trim());
}

// ---------------------------------------------------------------------------
// Tipler
// ---------------------------------------------------------------------------

interface TopicItem {
  id: string;
  tenant_id: string;
  topic_title: string;
  target_keywords: string[] | null;
  status: "pending" | "processing" | "done" | "failed";
  priority: number;
  retry_count: number;
  created_at: string;
  locked_at: string | null;
  processed_at: string | null;
}

interface TopicsResponse {
  tenant_id: string;
  total: number;
  items: TopicItem[];
}

interface DraftListItem {
  draft_id: string;
  topic_id: string;
  tenant_id: string;
  status: "draft" | "in_review" | "approved" | "published" | "archived";
  latest_version_number: number | null;
  created_at: string;
  updated_at: string;
}

interface DraftsListResponse {
  tenant_id: string;
  total: number;
  items: DraftListItem[];
}

// ---------------------------------------------------------------------------
// Alt Bileşenler: Badges
// ---------------------------------------------------------------------------

function TopicStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending: "bg-amber-900/40 text-amber-300 border-amber-700/50",
    processing: "bg-blue-900/40 text-blue-300 border-blue-700/50 animate-pulse",
    done: "bg-emerald-900/40 text-emerald-300 border-emerald-700/50",
    failed: "bg-red-900/40 text-red-300 border-red-700/50",
  };
  const labels: Record<string, string> = {
    pending: "Bekliyor",
    processing: "Üretiliyor...",
    done: "Tamamlandı",
    failed: "Hata",
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${
        styles[status] ?? "bg-slate-800 text-slate-400 border-slate-700"
      }`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-80" />
      {labels[status] ?? status}
    </span>
  );
}

function DraftStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    draft: "bg-slate-800 text-slate-300 border-slate-700",
    in_review: "bg-amber-900/40 text-amber-300 border-amber-700/50",
    approved: "bg-emerald-900/40 text-emerald-300 border-emerald-700/50",
    published: "bg-blue-900/40 text-blue-300 border-blue-700/50",
    archived: "bg-slate-900 text-slate-500 border-slate-800",
  };
  const labels: Record<string, string> = {
    draft: "Taslak",
    in_review: "İncelemede",
    approved: "Onaylandı",
    published: "Yayınlandı",
    archived: "Arşiv",
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
        styles[status] ?? "bg-slate-800 text-slate-400 border-slate-700"
      }`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-80" />
      {labels[status] ?? status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Ana Bileşen: KatipDashboard
// ---------------------------------------------------------------------------

export default function KatipDashboard() {
  const navigate = useNavigate();

  // Tenant state
  const [currentTenant, setCurrentTenant] = useState<string>(getTenantId());
  const [tenantInput, setTenantInput] = useState<string>(getTenantId());
  const [isEditingTenant, setIsEditingTenant] = useState(false);
  const [registeredTenants, setRegisteredTenants] = useState<{ tenant_id: string; business_name: string }[]>([]);

  // Registered Tenants List Fetch
  const fetchRegisteredTenants = useCallback(async () => {
    try {
      const { data } = await axios.get<{ items: { tenant_id: string; business_name: string }[] }>(
        `${API_BASE}/api/katip/tenants`
      );
      setRegisteredTenants(data.items ?? []);
    } catch (_e) {
      console.log("Katip tenants fetch warning", _e);
    }
  }, []);

  useEffect(() => {
    fetchRegisteredTenants();
  }, [fetchRegisteredTenants]);

  // Tab State
  const [activeTab, setActiveTab] = useState<"topics" | "drafts">("topics");

  // Topics State
  const [topics, setTopics] = useState<TopicItem[]>([]);
  const [topicsLoading, setTopicsLoading] = useState(false);
  const [generatingTopicId, setGeneratingTopicId] = useState<string | null>(null);

  // New Topic Form State
  const [showAddTopicModal, setShowAddTopicModal] = useState(false);
  const [newTopicTitle, setNewTopicTitle] = useState("");
  const [newKeywords, setNewKeywords] = useState("");
  const [newPriority, setNewPriority] = useState(5);
  const [addTopicSubmitting, setAddTopicSubmitting] = useState(false);

  // Drafts State
  const [drafts, setDrafts] = useState<DraftListItem[]>([]);
  const [draftsLoading, setDraftsLoading] = useState(false);
  const [draftStatusFilter, setDraftStatusFilter] = useState<string>("all");

  // General Notification
  const [notification, setNotification] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  const showNotify = (type: "success" | "error", msg: string) => {
    setNotification({ type, msg });
    setTimeout(() => setNotification(null), 4000);
  };

  // ---------------------------------------------------------------------------
  // Veri Çekme Fonksiyonları
  // ---------------------------------------------------------------------------

  const fetchTopics = useCallback(async () => {
    setTopicsLoading(true);
    try {
      const { data } = await axios.get<TopicsResponse>(`${API_BASE}/api/katip/topics`, {
        headers: { "X-Tenant-ID": currentTenant },
      });
      setTopics(data.items);
    } catch (err) {
      const ae = err as AxiosError<{ detail: string }>;
      showNotify("error", ae.response?.data?.detail ?? "Konu kuyruğu yüklenemedi.");
    } finally {
      setTopicsLoading(false);
    }
  }, [currentTenant]);

  const fetchDrafts = useCallback(async () => {
    setDraftsLoading(true);
    try {
      const url =
        draftStatusFilter !== "all"
          ? `${API_BASE}/api/katip/drafts?draft_status=${draftStatusFilter}`
          : `${API_BASE}/api/katip/drafts`;

      const { data } = await axios.get<DraftsListResponse>(url, {
        headers: { "X-Tenant-ID": currentTenant },
      });
      setDrafts(data.items);
    } catch (err) {
      const ae = err as AxiosError<{ detail: string }>;
      showNotify("error", ae.response?.data?.detail ?? "Taslaklar yüklenemedi.");
    } finally {
      setDraftsLoading(false);
    }
  }, [currentTenant, draftStatusFilter]);

  useEffect(() => {
    if (activeTab === "topics") {
      fetchTopics();
    } else {
      fetchDrafts();
    }
  }, [activeTab, fetchTopics, fetchDrafts]);

  // Tenant Değiştirme
  const handleSaveTenant = () => {
    if (!tenantInput.trim()) return;
    setTenantId(tenantInput);
    setCurrentTenant(tenantInput.trim());
    setIsEditingTenant(false);
    showNotify("success", `Tenant "${tenantInput.trim()}" olarak güncellendi.`);
  };

  // 1-Tıkla Taslak Üretimi (POST /api/katip/drafts/generate)
  const handleGenerateDraft = async (topicId: string, topicTitle: string) => {
    setGeneratingTopicId(topicId);
    try {
      const { data } = await axios.post(
        `${API_BASE}/api/katip/drafts/generate`,
        { topic_id: topicId },
        { headers: { "X-Tenant-ID": currentTenant } }
      );

      if (data.status === "success" || data.status === "already_processed") {
        showNotify("success", `'${topicTitle}' için v${data.version_number} taslağı başarıyla üretildi!`);
        fetchTopics();
        // İsteğe bağlı hemen editöre git
        navigate(`/drafts/${data.draft_id}`);
      }
    } catch (err) {
      const ae = err as AxiosError<{ detail: string }>;
      showNotify("error", ae.response?.data?.detail ?? "Taslak üretimi sırasında hata oluştu.");
    } finally {
      setGeneratingTopicId(null);
    }
  };

  // Yeni Konu Ekleme (POST /api/katip/topics)
  const handleCreateTopic = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTopicTitle.trim()) return;

    setAddTopicSubmitting(true);
    try {
      const keywordsArray = newKeywords
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean);

      await axios.post(
        `${API_BASE}/api/katip/topics`,
        {
          topic_title: newTopicTitle.trim(),
          target_keywords: keywordsArray.length ? keywordsArray : undefined,
          priority: newPriority,
        },
        { headers: { "X-Tenant-ID": currentTenant } }
      );

      showNotify("success", `Yeni konu kuyruğa eklendi: "${newTopicTitle.trim()}"`);
      setNewTopicTitle("");
      setNewKeywords("");
      setNewPriority(5);
      setShowAddTopicModal(false);
      fetchTopics();
    } catch (err) {
      const ae = err as AxiosError<{ detail: string }>;
      showNotify("error", ae.response?.data?.detail ?? "Konu eklenemedi.");
    } finally {
      setAddTopicSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* ── ÜST HEADER ────────────────────────────────────────────────────── */}
      <header className="bg-slate-900 border-b border-slate-800 px-6 py-4 sticky top-0 z-20 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-900/30">
            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z"
              />
            </svg>
          </div>
          <div>
            <h1 className="text-white font-bold text-lg leading-tight flex items-center gap-2">
              Mergen Kâtip
              <span className="text-xs px-2 py-0.5 rounded bg-blue-900/40 text-blue-400 border border-blue-800/60 font-mono">
                v2.0
              </span>
            </h1>
            <p className="text-slate-400 text-xs">Yapay Zeka Blog & İçerik Üretim Motoru</p>
          </div>
        </div>

        {/* TENANT SEÇİCİ */}
        <div className="flex items-center gap-3 bg-slate-800/60 border border-slate-700/60 rounded-xl px-3 py-1.5">
          <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
          </svg>
          <span className="text-xs text-slate-400 font-semibold">Aktif Müşteri / Ajans:</span>
          
          <select
            value={currentTenant}
            onChange={(e) => {
              const val = e.target.value;
              if (val === "__custom__") {
                setIsEditingTenant(true);
              } else {
                setTenantId(val);
                setCurrentTenant(val);
                setTenantInput(val);
                setIsEditingTenant(false);
                showNotify("success", `Müşteri "${val}" olarak değiştirildi.`);
              }
            }}
            className="bg-slate-900 border border-slate-600 rounded-lg px-2.5 py-1 text-xs text-blue-300 font-mono font-semibold focus:outline-none focus:border-blue-500 cursor-pointer"
          >
            {registeredTenants.map((t) => (
              <option key={t.tenant_id} value={t.tenant_id}>
                {t.business_name} ({t.tenant_id})
              </option>
            ))}
            <option value="pilot-dental-clinic-01">Pilot Diş Kliniği (pilot-dental-clinic-01)</option>
            <option value="__custom__">+ Elle Manuel Müşteri ID Yaz...</option>
          </select>

          {isEditingTenant && (
            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="Örn: dumedan-ajans-1"
                value={tenantInput}
                onChange={(e) => setTenantInput(e.target.value)}
                className="bg-slate-900 border border-slate-600 rounded px-2 py-0.5 text-xs text-white focus:outline-none focus:border-blue-500 font-mono"
              />
              <button
                onClick={handleSaveTenant}
                className="px-2 py-0.5 bg-blue-600 text-white rounded text-xs hover:bg-blue-500"
              >
                Kaydet
              </button>
            </div>
          )}
        </div>
      </header>

      {/* ── BİLDİRİM BANNER ───────────────────────────────────────────────── */}
      {notification && (
        <div
          className={`mx-6 mt-4 px-4 py-3 rounded-xl border flex items-center justify-between text-sm ${
            notification.type === "success"
              ? "bg-emerald-900/30 border-emerald-700/50 text-emerald-300"
              : "bg-red-900/30 border-red-700/50 text-red-300"
          }`}
        >
          <span>{notification.msg}</span>
          <button onClick={() => setNotification(null)} className="opacity-70 hover:opacity-100">
            ✕
          </button>
        </div>
      )}

      {/* ── ANA İÇERİK ALANI ──────────────────────────────────────────────── */}
      <main className="flex-1 p-6 max-w-7xl w-full mx-auto space-y-6">
        {/* TABS HEADER */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center gap-2 bg-slate-900 p-1.5 rounded-xl border border-slate-800">
            <button
              onClick={() => setActiveTab("topics")}
              className={`px-5 py-2 rounded-lg text-sm font-semibold transition-all flex items-center gap-2 ${
                activeTab === "topics"
                  ? "bg-blue-600 text-white shadow-lg shadow-blue-900/30"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
              </svg>
              Konu Kuyruğu ({topics.length})
            </button>

            <button
              onClick={() => setActiveTab("drafts")}
              className={`px-5 py-2 rounded-lg text-sm font-semibold transition-all flex items-center gap-2 ${
                activeTab === "drafts"
                  ? "bg-blue-600 text-white shadow-lg shadow-blue-900/30"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Taslaklarım ({drafts.length})
            </button>
          </div>

          {activeTab === "topics" && (
            <button
              onClick={() => setShowAddTopicModal(true)}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-semibold flex items-center gap-2 shadow-lg shadow-blue-900/20 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Yeni Konu Ekle
            </button>
          )}
        </div>

        {/* ── TAB 1: KONU KUYRUĞU (TOPICS) ─────────────────────────────────── */}
        {activeTab === "topics" && (
          <div className="space-y-4">
            {topicsLoading ? (
              <div className="py-12 flex justify-center text-slate-500 text-sm">Konular yükleniyor...</div>
            ) : topics.length === 0 ? (
              <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-12 text-center space-y-3">
                <p className="text-slate-400 text-base">Bu müşteri için henüz konu eklenmemiş.</p>
                <button
                  onClick={() => setShowAddTopicModal(true)}
                  className="px-4 py-2 bg-blue-600 text-white rounded-xl text-xs font-semibold"
                >
                  İlk Konuyu Ekle
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {topics.map((t) => {
                  const isGenerating = generatingTopicId === t.id;
                  return (
                    <div
                      key={t.id}
                      className="bg-slate-900/80 border border-slate-800 hover:border-slate-700 rounded-2xl p-5 flex flex-col justify-between gap-4 transition-all"
                    >
                      <div className="space-y-3">
                        <div className="flex items-center justify-between gap-2">
                          <TopicStatusBadge status={t.status} />
                          <span className="text-xs font-mono text-slate-500 bg-slate-800 px-2 py-0.5 rounded">
                            Öncelik: {t.priority}
                          </span>
                        </div>

                        <h3 className="font-bold text-slate-100 text-base leading-snug">{t.topic_title}</h3>

                        {t.target_keywords && t.target_keywords.length > 0 && (
                          <div className="flex flex-wrap gap-1.5">
                            {t.target_keywords.map((kw, i) => (
                              <span
                                key={i}
                                className="text-[11px] bg-slate-800/90 text-slate-400 border border-slate-700/60 px-2 py-0.5 rounded-md"
                              >
                                #{kw}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="pt-3 border-t border-slate-800/60 flex items-center justify-between">
                        <span className="text-[11px] text-slate-500">
                          {new Date(t.created_at).toLocaleDateString("tr-TR")}
                        </span>

                        {t.status === "pending" || t.status === "failed" ? (
                          <button
                            onClick={() => handleGenerateDraft(t.id, t.topic_title)}
                            disabled={isGenerating}
                            className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-md shadow-blue-900/20"
                          >
                            {isGenerating ? (
                              <>
                                <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                Üretiliyor...
                              </>
                            ) : (
                              <>
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                </svg>
                                Taslak Üret
                              </>
                            )}
                          </button>
                        ) : (
                          <span className="text-xs text-emerald-400 font-medium flex items-center gap-1">
                            ✓ Üretildi
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ── TAB 2: TASLAKLARIM (DRAFTS) ─────────────────────────────────── */}
        {activeTab === "drafts" && (
          <div className="space-y-4">
            {/* Status Filter Sub-bar */}
            <div className="flex items-center gap-2 overflow-x-auto pb-2">
              {["all", "draft", "in_review", "approved", "published"].map((st) => (
                <button
                  key={st}
                  onClick={() => setDraftStatusFilter(st)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors border ${
                    draftStatusFilter === st
                      ? "bg-slate-800 text-blue-400 border-blue-500/40"
                      : "bg-slate-900/60 text-slate-400 border-slate-800 hover:bg-slate-800"
                  }`}
                >
                  {st === "all"
                    ? "Tümü"
                    : st === "draft"
                    ? "Taslak"
                    : st === "in_review"
                    ? "İncelemede"
                    : st === "approved"
                    ? "Onaylandı"
                    : "Yayınlandı"}
                </button>
              ))}
            </div>

            {draftsLoading ? (
              <div className="py-12 flex justify-center text-slate-500 text-sm">Taslaklar yükleniyor...</div>
            ) : drafts.length === 0 ? (
              <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-12 text-center space-y-3">
                <p className="text-slate-400 text-base">Seçilen filtrede henüz taslak bulunmuyor.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {drafts.map((d) => (
                  <div
                    key={d.draft_id}
                    onClick={() => navigate(`/drafts/${d.draft_id}`)}
                    className="bg-slate-900/80 border border-slate-800 hover:border-blue-500/50 rounded-2xl p-5 flex items-center justify-between gap-4 cursor-pointer transition-all hover:bg-slate-900"
                  >
                    <div className="space-y-1 min-w-0">
                      <div className="flex items-center gap-3">
                        <DraftStatusBadge status={d.status} />
                        <span className="text-xs font-mono text-blue-400 bg-blue-900/30 px-2 py-0.5 rounded border border-blue-800/40">
                          v{d.latest_version_number ?? 1}
                        </span>
                      </div>
                      <h4 className="font-bold text-slate-100 text-base truncate">
                        Taslak #{d.draft_id.slice(0, 8)}
                      </h4>
                      <p className="text-xs text-slate-500 font-mono truncate">Konu ID: {d.topic_id}</p>
                    </div>

                    <div className="flex items-center gap-4 flex-shrink-0">
                      <span className="text-xs text-slate-500">
                        {new Date(d.updated_at).toLocaleString("tr-TR")}
                      </span>
                      <div className="p-2 rounded-xl bg-slate-800 text-slate-300 hover:text-white">
                        →
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      {/* ── YENİ KONU EKLEME MODALI ───────────────────────────────────────── */}
      {showAddTopicModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 space-y-5 shadow-2xl">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-lg text-white">Yeni Konu Ekle</h3>
              <button
                onClick={() => setShowAddTopicModal(false)}
                className="text-slate-400 hover:text-white text-lg"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateTopic} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1 uppercase">
                  Konu Başlığı <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={newTopicTitle}
                  onChange={(e) => setNewTopicTitle(e.target.value)}
                  placeholder="Örn: Zirkonyum Diş Kaplama Nasıl Yapılır?"
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1 uppercase">
                  Anahtar Kelimeler (Virgülle ayırın)
                </label>
                <input
                  type="text"
                  value={newKeywords}
                  onChange={(e) => setNewKeywords(e.target.value)}
                  placeholder="zirkonyum, diş kaplama, estetik diş"
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1 uppercase">
                  Öncelik (1 - 10)
                </label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={newPriority}
                  onChange={(e) => setNewPriority(Number(e.target.value))}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowAddTopicModal(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl text-sm font-semibold hover:bg-slate-700"
                >
                  İptal
                </button>
                <button
                  type="submit"
                  disabled={addTopicSubmitting}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-semibold disabled:opacity-50"
                >
                  {addTopicSubmitting ? "Ekleniyor..." : "Kuyruğa Ekle"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
