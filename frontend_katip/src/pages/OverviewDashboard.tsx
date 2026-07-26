/**
 * OverviewDashboard.tsx
 * ────────────────────
 * Mergen Kâtip — Genel Bakış & KPI Dashboard
 */

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { getDashboardSummaryApi, api } from "../lib/api";

interface SummaryData {
  total_topics: number;
  topics_by_status: Record<string, number>;
  total_drafts: number;
  drafts_by_status: Record<string, number>;
  projects: Array<{
    id: string;
    brand_name: string;
    sector: string;
    topic_count: number;
    draft_count: number;
  }>;
  recent_drafts: Array<{
    draft_id: string;
    topic_id: string;
    topic_title: string;
    status: string;
    latest_version_number: number;
    brand_name: string;
    sector: string;
    updated_at: string;
  }>;
  pending_topics: Array<{
    id: string;
    topic_title: string;
    target_keywords: string[] | null;
    priority: number;
    created_at: string;
  }>;
}

interface OverviewDashboardProps {
  selectedProjectId: string;
}

export default function OverviewDashboard({ selectedProjectId }: OverviewDashboardProps) {
  const navigate = useNavigate();
  const [data, setData] = useState<SummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [generatingTopicId, setGeneratingTopicId] = useState<string | null>(null);

  const fetchSummary = useCallback(async () => {
    setLoading(true);
    try {
      const summary = await getDashboardSummaryApi(selectedProjectId || undefined);
      setData(summary);
    } catch (err: any) {
      console.error("Dashboard summary load error:", err);
    } finally {
      setLoading(false);
    }
  }, [selectedProjectId]);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  const handleGenerateDraft = async (topicId: string) => {
    setGeneratingTopicId(topicId);
    try {
      const response = await api.post("/katip/drafts/generate", { topic_id: topicId });
      if (response.data.status === "success") {
        fetchSummary();
        navigate(`/drafts/${response.data.draft_id}`);
      }
    } catch (err: any) {
      alert(err.response?.data?.detail ?? "Taslak üretimi başarısız.");
    } finally {
      setGeneratingTopicId(null);
    }
  };

  const draftStatusStyles: Record<string, { bg: string; text: string; label: string }> = {
    draft: { bg: "bg-slate-800 border-slate-700", text: "text-slate-300", label: "Taslak" },
    in_review: { bg: "bg-amber-950/60 border-amber-800/80", text: "text-amber-300", label: "İncelemede" },
    approved: { bg: "bg-emerald-950/60 border-emerald-800/80", text: "text-emerald-300", label: "Onaylandı" },
    published: { bg: "bg-blue-950/60 border-blue-800/80", text: "text-blue-300", label: "Yayınlandı" },
    archived: { bg: "bg-slate-900 border-slate-800", text: "text-slate-500", label: "Arşiv" },
  };

  if (loading) {
    return (
      <div className="p-8 flex justify-center items-center h-64 text-slate-500 text-sm">
        Dashboard verileri yükleniyor...
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-8 text-center text-slate-400">
        Veri yüklenemedi. Lütfen sayfayı yenileyin.
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Page Title & Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">Performans & Üretim Özeti</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Markalarınıza ve projelerinize ait içerik üretim durumu ve KPI metrikleri.
          </p>
        </div>
        <button
          onClick={() => navigate("/topics")}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow-lg shadow-blue-900/30 transition-all"
        >
          <span>+ Yeni Konu Ekle</span>
        </button>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Toplam Konu */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Toplam Konu
            </span>
            <div className="w-8 h-8 rounded-xl bg-blue-900/40 text-blue-400 flex items-center justify-center border border-blue-800/50">
              📌
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-black text-white">{data.total_topics}</span>
            <span className="text-xs text-slate-400">kuyrukta</span>
          </div>
          <div className="text-[11px] text-slate-500 flex items-center gap-1">
            <span className="text-emerald-400 font-semibold">{data.topics_by_status.done ?? 0}</span> üretildi
          </div>
        </div>

        {/* Card 2: Bekleyen Konular */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Üretim Bekleyen
            </span>
            <div className="w-8 h-8 rounded-xl bg-amber-900/40 text-amber-400 flex items-center justify-center border border-amber-800/50">
              ⚡
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-black text-amber-300">
              {data.topics_by_status.pending ?? 0}
            </span>
            <span className="text-xs text-amber-400/80">konu</span>
          </div>
          <div className="text-[11px] text-slate-500">Otonom scheduler sırada</div>
        </div>

        {/* Card 3: Toplam Taslak */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Hazır Taslaklar
            </span>
            <div className="w-8 h-8 rounded-xl bg-purple-900/40 text-purple-400 flex items-center justify-center border border-purple-800/50">
              📄
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-black text-white">{data.total_drafts}</span>
            <span className="text-xs text-slate-400">taslak</span>
          </div>
          <div className="text-[11px] text-slate-500 flex items-center gap-1">
            <span className="text-amber-400 font-semibold">{data.drafts_by_status.in_review ?? 0}</span> revizyonda
          </div>
        </div>

        {/* Card 4: Yayınlanan */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Yayınlanan
            </span>
            <div className="w-8 h-8 rounded-xl bg-emerald-900/40 text-emerald-400 flex items-center justify-center border border-emerald-800/50">
              🚀
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-black text-emerald-400">
              {data.drafts_by_status.published ?? 0}
            </span>
            <span className="text-xs text-emerald-400/80">makale</span>
          </div>
          <div className="text-[11px] text-slate-500">CMS entegrasyonu aktif</div>
        </div>
      </div>

      {/* Production Pipeline Overview */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-4">
        <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center justify-between">
          <span>İçerik Pipeline Akışı</span>
          <span className="text-xs text-slate-500 font-normal">Süreç Dağılımı</span>
        </h3>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-center">
            <div className="text-xs text-slate-400 font-medium">1. Bekliyor</div>
            <div className="text-xl font-bold text-amber-400 mt-1">{data.topics_by_status.pending ?? 0}</div>
          </div>
          <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-center">
            <div className="text-xs text-slate-400 font-medium">2. Taslak / İncelemede</div>
            <div className="text-xl font-bold text-blue-400 mt-1">
              {(data.drafts_by_status.draft ?? 0) + (data.drafts_by_status.in_review ?? 0)}
            </div>
          </div>
          <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-center">
            <div className="text-xs text-slate-400 font-medium">3. Onaylandı</div>
            <div className="text-xl font-bold text-emerald-400 mt-1">{data.drafts_by_status.approved ?? 0}</div>
          </div>
          <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-center">
            <div className="text-xs text-slate-400 font-medium">4. CMS Yayınlandı</div>
            <div className="text-xl font-bold text-teal-400 mt-1">{data.drafts_by_status.published ?? 0}</div>
          </div>
        </div>
      </div>

      {/* Two Column Layout: Recent Drafts & Pending Topics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Recent Drafts */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <span>📄 Son Güncellenen Taslaklar</span>
            </h3>
            <button
              onClick={() => navigate("/drafts")}
              className="text-xs text-blue-400 hover:underline font-semibold"
            >
              Tümünü Gör →
            </button>
          </div>

          {data.recent_drafts.length === 0 ? (
            <div className="text-slate-500 text-xs py-8 text-center">Henüz üretilmiş taslak yok.</div>
          ) : (
            <div className="space-y-2.5">
              {data.recent_drafts.map((d) => {
                const st = draftStatusStyles[d.status] ?? draftStatusStyles.draft;
                return (
                  <div
                    key={d.draft_id}
                    onClick={() => navigate(`/drafts/${d.draft_id}`)}
                    className="bg-slate-950 hover:bg-slate-800/80 border border-slate-800/80 hover:border-blue-500/40 rounded-xl p-3.5 flex items-center justify-between cursor-pointer transition-all gap-3"
                  >
                    <div className="space-y-1 min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold border ${st.bg} ${st.text}`}>
                          {st.label}
                        </span>
                        <span className="text-[10px] font-mono text-blue-400 bg-blue-950/60 px-1.5 py-0.5 rounded border border-blue-800/40">
                          v{d.latest_version_number}
                        </span>
                      </div>
                      <h4 className="font-bold text-slate-100 text-xs truncate">{d.topic_title}</h4>
                      <p className="text-[11px] text-slate-500 truncate">{d.brand_name}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <span className="text-[11px] text-slate-500 block">
                        {new Date(d.updated_at).toLocaleDateString("tr-TR")}
                      </span>
                      <span className="text-xs text-blue-400 font-bold">Detay →</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Column: Pending Topics */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <span>⚡ Sıradaki Konular (Hızlı Üret)</span>
            </h3>
            <button
              onClick={() => navigate("/topics")}
              className="text-xs text-blue-400 hover:underline font-semibold"
            >
              Kuyruğa Git →
            </button>
          </div>

          {data.pending_topics.length === 0 ? (
            <div className="text-slate-500 text-xs py-8 text-center">Bekleyen konu bulunmuyor.</div>
          ) : (
            <div className="space-y-2.5">
              {data.pending_topics.map((t) => {
                const isGenerating = generatingTopicId === t.id;
                return (
                  <div
                    key={t.id}
                    className="bg-slate-950 border border-slate-800/80 rounded-xl p-3.5 flex items-center justify-between gap-3"
                  >
                    <div className="space-y-1 min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono text-amber-300 bg-amber-950/60 px-1.5 py-0.5 rounded border border-amber-800/40">
                          Öncelik: {t.priority}
                        </span>
                      </div>
                      <h4 className="font-bold text-slate-100 text-xs truncate">{t.topic_title}</h4>
                      {t.target_keywords && t.target_keywords.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {t.target_keywords.slice(0, 3).map((kw, i) => (
                            <span key={i} className="text-[10px] text-slate-400 bg-slate-900 px-1.5 py-0.5 rounded">
                              #{kw}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    <button
                      onClick={() => handleGenerateDraft(t.id)}
                      disabled={isGenerating}
                      className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shrink-0 transition-colors shadow-md shadow-blue-900/20"
                    >
                      {isGenerating ? "..." : "Üret"}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
