/**
 * TopicsPage.tsx
 * ──────────────
 * Mergen Kâtip — Konu Kuyruğu + SEO Brief Modalı (Gelişmiş Editör Arayüzü)
 */

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { getTopicsApi, api } from "../lib/api";

interface TopicItem {
  id: string;
  tenant_id: string;
  brand_guide_id?: string | null;
  topic_title: string;
  target_keywords: string[] | null;
  target_subheadings?: string[] | null;
  special_instructions?: string | null;
  scheduled_for?: string | null;
  status: "pending" | "processing" | "done" | "failed" | "scheduled";
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

  // ─── SEO Brief Modal State ───────────────────────────────────────
  const [showAddModal, setShowAddModal] = useState(false);
  // Konu başlıkları (chip/tag girişi)
  const [topicChips, setTopicChips] = useState<string[]>([]);
  const [topicInput, setTopicInput] = useState("");
  // Keywords
  const [keywordsInput, setKeywordsInput] = useState("");
  // Zorunlu H2 Alt Başlıklar (chip/tag)
  const [subheadingChips, setSubheadingChips] = useState<string[]>([]);
  const [subheadingInput, setSubheadingInput] = useState("");
  // Editör Özel Talimatı
  const [specialInstructions, setSpecialInstructions] = useState("");
  // Priority
  const [priority, setPriority] = useState(5);
  // Submit state
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

  // ── Chip Input Handlers ──────────────────────────────────────────
  const handleTopicChipKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      const val = topicInput.trim().replace(/,/g, "");
      if (val && !topicChips.includes(val)) {
        setTopicChips((prev) => [...prev, val]);
        setTopicInput("");
      }
    }
  };

  const handleSubheadingChipKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      const val = subheadingInput.trim().replace(/,/g, "");
      if (val && !subheadingChips.includes(val)) {
        setSubheadingChips((prev) => [...prev, val]);
        setSubheadingInput("");
      }
    }
  };

  const resetModal = () => {
    setTopicChips([]);
    setTopicInput("");
    setSubheadingChips([]);
    setSubheadingInput("");
    setKeywordsInput("");
    setSpecialInstructions("");
    setPriority(5);
    setShowAddModal(false);
  };

  // ── Form Submit ──────────────────────────────────────────────────
  const submitTopics = async (scheduledFor?: string) => {
    const finalTitles = [...topicChips];
    if (topicInput.trim()) finalTitles.push(topicInput.trim());
    if (finalTitles.length === 0) {
      alert("Lütfen en az bir konu başlığı ekleyin.");
      return;
    }

    const finalSubheadings = [...subheadingChips];
    if (subheadingInput.trim()) finalSubheadings.push(subheadingInput.trim());

    const kwArray = keywordsInput
      .split(",")
      .map((k) => k.trim())
      .filter(Boolean);

    setSubmitting(true);
    try {
      for (const tTitle of finalTitles) {
        await api.post("/katip/topics", {
          topic_title: tTitle,
          brand_guide_id: selectedProjectId || undefined,
          target_keywords: kwArray.length ? kwArray : undefined,
          target_subheadings: finalSubheadings.length ? finalSubheadings : undefined,
          special_instructions: specialInstructions.trim() || undefined,
          scheduled_for: scheduledFor || undefined,
          priority,
        });
      }
      resetModal();
      fetchTopics();
    } catch (err: any) {
      alert(err.response?.data?.detail ?? "Konu eklenemedi.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmitNow = (e: React.FormEvent) => {
    e.preventDefault();
    submitTopics(); // scheduled_for yok → hemen kuyruğa al
  };

  const handleScheduleTomorrow = (e: React.MouseEvent) => {
    e.preventDefault();
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(9, 0, 0, 0);
    submitTopics(tomorrow.toISOString());
  };

  // ── Status Badge ──────────────────────────────────────────────────
  const statusBadge = (status: TopicItem["status"]) => {
    const map: Record<string, { classes: string; label: string }> = {
      pending: { classes: "bg-amber-950/60 text-amber-300 border-amber-800/60", label: "Bekliyor" },
      processing: { classes: "bg-blue-950/60 text-blue-300 border-blue-800/60 animate-pulse", label: "Üretiliyor" },
      done: { classes: "bg-emerald-950/60 text-emerald-300 border-emerald-800/60", label: "Tamamlandı" },
      failed: { classes: "bg-red-950/60 text-red-300 border-red-800/60", label: "Hata" },
      scheduled: { classes: "bg-purple-950/60 text-purple-300 border-purple-800/60", label: "Zamanlandı" },
    };
    const s = map[status] ?? map["pending"];
    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${s.classes}`}>
        <span className="w-1.5 h-1.5 rounded-full bg-current" />
        {s.label}
      </span>
    );
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">Konu Kuyruğu</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Otonom içerik üretimi için sıradaki ve üretilmiş tüm konular.
          </p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow-lg shadow-blue-900/30 transition-all"
        >
          <span>+ SEO Brief Ekle</span>
        </button>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        {[
          { id: "all", label: "Tüm Konular" },
          { id: "pending", label: "Bekliyor" },
          { id: "scheduled", label: "Zamanlandı" },
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
            SEO Brief ile Konu Ekle
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {topics.map((t) => {
            const isGenerating = generatingTopicId === t.id;
            const hasSubheadings = t.target_subheadings && t.target_subheadings.length > 0;
            const hasBrief = !!t.special_instructions;
            return (
              <div
                key={t.id}
                className="bg-slate-900/80 border border-slate-800 hover:border-slate-700 rounded-2xl p-5 flex flex-col justify-between gap-4 transition-all"
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    {statusBadge(t.status)}
                    <span className="text-xs font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded border border-slate-700">
                      Ön: {t.priority}
                    </span>
                  </div>

                  <h3 className="font-bold text-slate-100 text-sm leading-snug">{t.topic_title}</h3>

                  {t.target_keywords && t.target_keywords.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {t.target_keywords.slice(0, 4).map((kw, i) => (
                        <span key={i} className="text-[10px] bg-slate-800 text-slate-400 border border-slate-700 px-2 py-0.5 rounded-md">
                          #{kw}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* SEO Brief göstergeler */}
                  <div className="flex items-center gap-2 flex-wrap">
                    {hasSubheadings && (
                      <span className="text-[10px] bg-indigo-950/60 border border-indigo-800/60 text-indigo-300 px-2 py-0.5 rounded-full font-medium">
                        📐 {t.target_subheadings!.length} Zorunlu H2
                      </span>
                    )}
                    {hasBrief && (
                      <span className="text-[10px] bg-orange-950/60 border border-orange-800/60 text-orange-300 px-2 py-0.5 rounded-full font-medium">
                        ⚠️ Editör Talimatı
                      </span>
                    )}
                    {t.scheduled_for && (
                      <span className="text-[10px] bg-purple-950/60 border border-purple-800/60 text-purple-300 px-2 py-0.5 rounded-full font-medium">
                        🗓 {new Date(t.scheduled_for).toLocaleDateString("tr-TR")}
                      </span>
                    )}
                  </div>
                </div>

                <div className="pt-3 border-t border-slate-800/60 flex items-center justify-between">
                  <span className="text-[11px] text-slate-500">
                    {new Date(t.created_at).toLocaleDateString("tr-TR")}
                  </span>
                  {(t.status === "pending" || t.status === "failed") ? (
                    <button
                      onClick={() => handleGenerateDraft(t.id)}
                      disabled={isGenerating}
                      className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold flex items-center gap-1 transition-colors"
                    >
                      {isGenerating ? "Üretiliyor..." : "⚡ Taslak Üret"}
                    </button>
                  ) : t.status === "scheduled" ? (
                    <span className="text-xs text-purple-400 font-medium">⏰ Zamanlandı</span>
                  ) : (
                    <span className="text-xs text-emerald-400 font-medium">✓ Taslak Hazır</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ─── SEO Brief Add Modal ─────────────────────────────────────── */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-start justify-center p-4 z-50 overflow-y-auto">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full p-6 space-y-5 shadow-2xl my-8">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="font-bold text-lg text-white flex items-center gap-2">
                  📝 SEO Brief ile Konu Ekle
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Editör direktifleri, zorunlu başlıklar ve özel talimatları burada belirtin.
                </p>
              </div>
              <button onClick={resetModal} className="text-slate-400 hover:text-white text-lg font-bold">
                ✕
              </button>
            </div>

            <form onSubmit={handleSubmitNow} className="space-y-5">
              {/* Konu Başlıkları — Chip Input */}
              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1.5 uppercase tracking-wider">
                  Konu / Makale Başlıkları <span className="text-red-400">*</span>
                  <span className="text-slate-500 font-normal ml-2">(Enter veya virgülle ayırın — toplu ekleyebilirsiniz)</span>
                </label>
                <div className="bg-slate-950 border border-slate-800 rounded-xl p-3 flex flex-wrap items-center gap-2 min-h-[72px] focus-within:border-blue-500 transition-colors">
                  {topicChips.map((chip, idx) => (
                    <span key={idx} className="bg-blue-900/40 text-blue-300 border border-blue-700/60 text-xs px-2.5 py-1 rounded-full font-medium flex items-center gap-1.5">
                      {chip}
                      <button type="button" onClick={() => setTopicChips(prev => prev.filter((_, i) => i !== idx))} className="text-blue-400 hover:text-white font-bold">×</button>
                    </span>
                  ))}
                  <input
                    type="text"
                    value={topicInput}
                    onChange={(e) => setTopicInput(e.target.value)}
                    onKeyDown={handleTopicChipKey}
                    placeholder={topicChips.length === 0 ? "Örn. Zirkonyum Diş Kaplama Nedir? (Enter'a basın)" : "Başka konu ekle..."}
                    className="flex-1 min-w-[200px] bg-transparent text-sm text-white placeholder-slate-500 focus:outline-none"
                  />
                </div>
              </div>

              {/* SEO Anahtar Kelimeleri */}
              <div>
                <label className="block text-xs font-bold text-slate-400 mb-1 uppercase tracking-wider">
                  Hedef SEO Anahtar Kelimeleri
                  <span className="text-slate-500 font-normal ml-2">(virgülle ayırın)</span>
                </label>
                <input
                  type="text"
                  value={keywordsInput}
                  onChange={(e) => setKeywordsInput(e.target.value)}
                  placeholder="zirkonyum diş, diş kaplama maliyeti, estetik diş hekimi"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
                />
              </div>

              {/* Zorunlu H2 Alt Başlıkları — Chip Input */}
              <div>
                <label className="block text-xs font-bold text-indigo-400 mb-1.5 uppercase tracking-wider flex items-center gap-2">
                  <span>📐 Zorunlu H2 Alt Başlıklar</span>
                  <span className="text-slate-500 font-normal text-[11px] normal-case">
                    (doldurulursa LLM bu başlıkları H2 olarak kullanır, ekstra başlık eklemez)
                  </span>
                </label>
                <div className="bg-slate-950 border border-indigo-900/60 rounded-xl p-3 flex flex-wrap items-center gap-2 min-h-[60px] focus-within:border-indigo-500 transition-colors">
                  {subheadingChips.map((chip, idx) => (
                    <span key={idx} className="bg-indigo-900/40 text-indigo-300 border border-indigo-700/60 text-xs px-2.5 py-1 rounded-full font-medium flex items-center gap-1.5">
                      <span className="text-[9px] font-mono text-indigo-400">H2</span>
                      {chip}
                      <button type="button" onClick={() => setSubheadingChips(prev => prev.filter((_, i) => i !== idx))} className="text-indigo-400 hover:text-white font-bold">×</button>
                    </span>
                  ))}
                  <input
                    type="text"
                    value={subheadingInput}
                    onChange={(e) => setSubheadingInput(e.target.value)}
                    onKeyDown={handleSubheadingChipKey}
                    placeholder={subheadingChips.length === 0 ? "Örn. Zirkonyum'un Avantajları (Enter ile ekleyin)" : "Başka başlık ekle..."}
                    className="flex-1 min-w-[200px] bg-transparent text-sm text-white placeholder-slate-500 focus:outline-none"
                  />
                </div>
                {subheadingChips.length > 0 && (
                  <p className="text-[11px] text-indigo-400/80 mt-1">
                    ✓ {subheadingChips.length} zorunlu H2 başlığı belirlendi. LLM sadece bunları kullanacak.
                  </p>
                )}
              </div>

              {/* Editör Özel Talimatı / Brief */}
              <div>
                <label className="block text-xs font-bold text-orange-400 mb-1.5 uppercase tracking-wider flex items-center gap-2">
                  <span>⚠️ Editör Özel Talimatı / Brief</span>
                  <span className="text-slate-500 font-normal text-[11px] normal-case">
                    (LLM buna %100 uyacak)
                  </span>
                </label>
                <textarea
                  rows={4}
                  value={specialInstructions}
                  onChange={(e) => setSpecialInstructions(e.target.value)}
                  placeholder={`Örn: "İmplant bölümünü kısa geç, alt sayfaya yönlendirilecek. Fiyat karşılaştırması kesinlikle yazılmasın. Zirkonyum ve porselen karşılaştırması için bir tablo ekle."`}
                  className="w-full bg-slate-950 border border-orange-900/50 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-orange-500 transition-colors resize-none"
                />
                {specialInstructions.trim() && (
                  <p className="text-[11px] text-orange-400/80 mt-1">
                    ⚠️ Bu talimat promptta en üst öncelikle işlenecek.
                  </p>
                )}
              </div>

              {/* Öncelik */}
              <div>
                <label className="block text-xs font-bold text-slate-400 mb-1 uppercase tracking-wider">
                  Öncelik Seviyesi (1-10)
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min={1}
                    max={10}
                    value={priority}
                    onChange={(e) => setPriority(Number(e.target.value))}
                    className="flex-1 accent-blue-500"
                  />
                  <span className="text-lg font-bold text-blue-400 w-6 text-center">{priority}</span>
                </div>
              </div>

              {/* ─── Action Buttons — İki Farklı Aksiyon ─────────────── */}
              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
                <button
                  type="button"
                  onClick={resetModal}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl text-sm font-semibold hover:bg-slate-700 transition-colors"
                >
                  İptal
                </button>

                <button
                  type="button"
                  onClick={handleScheduleTomorrow}
                  disabled={submitting}
                  className="px-5 py-2.5 bg-purple-700 hover:bg-purple-600 disabled:opacity-50 text-white rounded-xl text-sm font-bold shadow-lg shadow-purple-900/30 transition-all flex items-center gap-2"
                >
                  🗓 Yarına Zamanla
                </button>

                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl text-sm font-bold shadow-lg shadow-blue-600/30 transition-all flex items-center gap-2"
                >
                  ⚡ Hemen Kuyruğa Al
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
