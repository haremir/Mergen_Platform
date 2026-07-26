/**
 * TopicsPage.tsx
 * ──────────────
 * Mergen Kâtip — Konu Kuyruğu Yönetim Sayfası
 */

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { getTopicsApi, createTopicApi, api } from "../lib/api";

interface TopicItem {
  id: string;
  tenant_id: string;
  brand_guide_id?: string | null;
  topic_title: string;
  target_keywords: string[] | null;
  status: "pending" | "processing" | "done" | "failed";
  priority: number;
  retry_count: number;
  created_at: string;
  locked_at: string | null;
  processed_at: string | null;
}

interface TopicsPageProps {
  selectedProjectId: string;
}

export default function TopicsPage({ selectedProjectId }: TopicsPageProps) {
  const navigate = useNavigate();
  const [topics, setTopics] = useState<TopicItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [generatingTopicId, setGeneratingTopicId] = useState<string | null>(null);

  // Add Topic Modal State
  const [showAddModal, setShowAddModal] = useState(false);
  const [topicChips, setTopicChips] = useState<string[]>([]);
  const [topicInput, setTopicInput] = useState("");
  const [keywordsInput, setKeywordsInput] = useState("");
  const [priority, setPriority] = useState(5);
  const [submitting, setSubmitting] = useState(false);

  const fetchTopics = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getTopicsApi({
        brand_guide_id: selectedProjectId || undefined,
        topic_status: statusFilter !== "all" ? statusFilter : undefined,
      });
      setTopics(data.items);
    } catch (err: any) {
      console.error("Topics fetch error:", err);
    } finally {
      setLoading(false);
    }
  }, [selectedProjectId, statusFilter]);

  useEffect(() => {
    fetchTopics();
  }, [fetchTopics]);

  const handleGenerateDraft = async (topicId: string) => {
    setGeneratingTopicId(topicId);
    try {
      const response = await api.post("/katip/drafts/generate", { topic_id: topicId });
      if (response.data.status === "success" || response.data.status === "already_processed") {
        fetchTopics();
        navigate(`/drafts/${response.data.draft_id}`);
      }
    } catch (err: any) {
      alert(err.response?.data?.detail ?? "Taslak üretimi başarısız.");
    } finally {
      setGeneratingTopicId(null);
    }
  };

  const handleAddChip = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      const val = topicInput.trim().replace(/,/g, "");
      if (val && !topicChips.includes(val)) {
        setTopicChips((prev) => [...prev, val]);
        setTopicInput("");
      }
    }
  };

  const handleRemoveChip = (idx: number) => {
    setTopicChips((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleCreateTopics = async (e: React.FormEvent) => {
    e.preventDefault();
    const finalTitles = [...topicChips];
    if (topicInput.trim()) finalTitles.push(topicInput.trim());

    if (finalTitles.length === 0) {
      alert("Lütfen en az bir konu başlığı ekleyin.");
      return;
    }

    setSubmitting(true);
    try {
      const kwArray = keywordsInput
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean);

      for (const tTitle of finalTitles) {
        await createTopicApi({
          topic_title: tTitle,
          brand_guide_id: selectedProjectId || undefined,
          target_keywords: kwArray.length ? kwArray : undefined,
          priority: priority,
        });
      }

      setTopicChips([]);
      setTopicInput("");
      setKeywordsInput("");
      setPriority(5);
      setShowAddModal(false);
      fetchTopics();
    } catch (err: any) {
      alert(err.response?.data?.detail ?? "Konu eklenemedi.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">Konu Kuyruğu (Topics)</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Otonom içerik üretimi için sıradaki ve üretilmiş tüm konular.
          </p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow-lg shadow-blue-900/30 transition-all"
        >
          <span>+ Yeni Konu Ekle</span>
        </button>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        {[
          { id: "all", label: "Tüm Konular" },
          { id: "pending", label: "Bekliyor (Sırada)" },
          { id: "processing", label: "Üretiliyor" },
          { id: "done", label: "Tamamlandı" },
          { id: "failed", label: "Hata Alındı" },
        ].map((f) => (
          <button
            key={f.id}
            onClick={() => setStatusFilter(f.id)}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors border ${
              statusFilter === f.id
                ? "bg-slate-800 text-blue-400 border-blue-500/40"
                : "bg-slate-900/60 text-slate-400 border-slate-800 hover:bg-slate-800"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Topics Grid */}
      {loading ? (
        <div className="py-12 text-center text-slate-500 text-sm">Konular yükleniyor...</div>
      ) : topics.length === 0 ? (
        <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-12 text-center space-y-3">
          <p className="text-slate-400 text-sm">Bu filtrede henüz konu bulunmuyor.</p>
          <button
            onClick={() => setShowAddModal(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-xl text-xs font-semibold"
          >
            Yeni Konu Ekle
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
                    <span
                      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                        t.status === "pending"
                          ? "bg-amber-950/60 text-amber-300 border-amber-800/60"
                          : t.status === "processing"
                          ? "bg-blue-950/60 text-blue-300 border-blue-800/60 animate-pulse"
                          : t.status === "done"
                          ? "bg-emerald-950/60 text-emerald-300 border-emerald-800/60"
                          : "bg-red-950/60 text-red-300 border-red-800/60"
                      }`}
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-current" />
                      {t.status === "pending"
                        ? "Bekliyor"
                        : t.status === "processing"
                        ? "Üretiliyor"
                        : t.status === "done"
                        ? "Tamamlandı"
                        : "Hata"}
                    </span>

                    <span className="text-xs font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded border border-slate-700">
                      Öncelik: {t.priority}
                    </span>
                  </div>

                  <h3 className="font-bold text-slate-100 text-sm leading-snug">{t.topic_title}</h3>

                  {t.target_keywords && t.target_keywords.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {t.target_keywords.map((kw, i) => (
                        <span
                          key={i}
                          className="text-[10px] bg-slate-800 text-slate-400 border border-slate-700 px-2 py-0.5 rounded-md"
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
                      onClick={() => handleGenerateDraft(t.id)}
                      disabled={isGenerating}
                      className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold flex items-center gap-1 transition-colors"
                    >
                      {isGenerating ? "Üretiliyor..." : "⚡ Taslak Üret"}
                    </button>
                  ) : (
                    <span className="text-xs text-emerald-400 font-medium">✓ Taslak Hazır</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Add Topic Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 space-y-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="font-bold text-lg text-white">Yeni Konu / Makale Ekle</h3>
                <p className="text-xs text-slate-400">Konuları etiket kutuları (Chips) olarak girin.</p>
              </div>
              <button onClick={() => setShowAddModal(false)} className="text-slate-400 hover:text-white">
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateTopics} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wider">
                  Konu Başlıkları (Enter veya Virgül)
                </label>
                <div className="bg-slate-950 border border-slate-800 rounded-xl p-3 flex flex-wrap items-center gap-2 min-h-[80px] focus-within:border-blue-500">
                  {topicChips.map((chip, idx) => (
                    <span
                      key={idx}
                      className="bg-blue-900/40 text-blue-300 border border-blue-700/60 text-xs px-2.5 py-1 rounded-full font-medium flex items-center gap-1.5"
                    >
                      {chip}
                      <button
                        type="button"
                        onClick={() => handleRemoveChip(idx)}
                        className="text-blue-400 hover:text-white font-bold ml-1"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                  <input
                    type="text"
                    value={topicInput}
                    onChange={(e) => setTopicInput(e.target.value)}
                    onKeyDown={handleAddChip}
                    placeholder={
                      topicChips.length === 0 ? "Örn. Zirkonyum Diş Kaplama (Enter'a basın)..." : "Başka konu ekle..."
                    }
                    className="flex-1 min-w-[180px] bg-transparent text-sm text-white placeholder-slate-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1 uppercase">
                  Hedef SEO Anahtar Kelimeleri (Virgülle ayırın)
                </label>
                <input
                  type="text"
                  value={keywordsInput}
                  onChange={(e) => setKeywordsInput(e.target.value)}
                  placeholder="zirkonyum, diş kaplama, estetik diş"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1 uppercase">
                  Öncelik Seviyesi (1-10)
                </label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={priority}
                  onChange={(e) => setPriority(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl text-sm font-semibold hover:bg-slate-700"
                >
                  İptal
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-bold shadow-lg shadow-blue-600/30 disabled:opacity-50"
                >
                  {submitting ? "Ekleniyor..." : "⚡ Konuları Ekle"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
