/**
 * DraftEditor.tsx
 * ───────────────
 * Mergen Kâtip — Taslak Düzenleme & Versiyon Yönetimi Sayfası
 *
 * Düzen:
 *   Sol panel  → Salt okunur taslak metni (en son versiyon)
 *   Sağ panel  → VersionTimeline + FeedbackForm
 *
 * API bağlantıları:
 *   GET  /api/katip/drafts/:id          → DraftDetailResponse
 *   POST /api/katip/drafts/:id/feedback → FeedbackResponse
 *   PUT  /api/katip/drafts/:id/status   → Durum güncellemesi
 *
 * Tenant kimliği: localStorage'daki "katip_tenant_id" değerinden okunur.
 * Üretim ortamında bu JWT middleware ile değiştirilmelidir.
 */

import { useState, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import axios, { AxiosError } from "axios";
import ReactMarkdown from "react-markdown";

// ---------------------------------------------------------------------------
// Sabitler
// ---------------------------------------------------------------------------

const API_BASE = (import.meta as any).env?.VITE_API_BASE ?? "http://localhost:8000";

function getTenantId(): string {
  const val = localStorage.getItem("katip_tenant_id");
  return (val && val.trim()) ? val.trim() : "pilot-dental-clinic-01";
}

// ---------------------------------------------------------------------------
// Tipler
// ---------------------------------------------------------------------------

interface DraftVersionItem {
  id: string;
  version_number: number;
  content?: string;
  word_count: number;
  parent_version_id: string | null;
  created_at: string;
}

interface LatestVersion {
  id: string;
  version_number: number;
  content: string;
  word_count: number;
  parent_version_id: string | null;
  created_at: string;
}

interface DraftDetail {
  draft_id: string;
  topic_id: string;
  tenant_id: string;
  status: string;
  created_at: string;
  updated_at: string;
  latest_version: LatestVersion | null;
  versions: DraftVersionItem[];
}

interface FeedbackResponse {
  status: string;
  feedback_id: string;
  draft_id: string;
  source_version_number: number;
  message: string;
}

type DraftStatus = "draft" | "in_review" | "approved" | "published" | "archived";

// ---------------------------------------------------------------------------
// Yardımcı: durum etiketi renkleri
// ---------------------------------------------------------------------------

const STATUS_STYLES: Record<string, string> = {
  draft: "bg-slate-700 text-slate-200 border-slate-600",
  in_review: "bg-amber-900/60 text-amber-300 border-amber-700",
  approved: "bg-emerald-900/60 text-emerald-300 border-emerald-700",
  published: "bg-blue-900/60 text-blue-300 border-blue-700",
  archived: "bg-slate-800 text-slate-500 border-slate-700",
};

function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_STYLES[status] ?? "bg-slate-700 text-slate-300 border-slate-600";
  const labels: Record<string, string> = {
    draft: "Taslak",
    in_review: "İncelemede",
    approved: "Onaylandı",
    published: "Yayınlandı",
    archived: "Arşiv",
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${cls}`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-80" />
      {labels[status] ?? status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Alt bileşen: VersionTimeline
// ---------------------------------------------------------------------------

interface VersionTimelineProps {
  versions: DraftVersionItem[];
  activeVersionId: string | null;
  onSelectVersion: (v: DraftVersionItem) => void;
}

function VersionTimeline({ versions, activeVersionId, onSelectVersion }: VersionTimelineProps) {
  if (versions.length === 0) {
    return (
      <div className="text-slate-500 text-sm italic py-6 text-center">
        Henüz versiyon yok.
      </div>
    );
  }

  return (
    <div className="relative">
      {/* Dikey çizgi */}
      <div className="absolute left-[11px] top-2 bottom-2 w-px bg-slate-700" />

      <div className="space-y-2">
        {[...versions].reverse().map((v, idx) => {
          const isActive = v.id === activeVersionId;
          const isLatest = idx === 0;
          const date = new Date(v.created_at);
          const dateStr = date.toLocaleDateString("tr-TR", {
            day: "2-digit",
            month: "short",
          });
          const timeStr = date.toLocaleTimeString("tr-TR", {
            hour: "2-digit",
            minute: "2-digit",
          });

          return (
            <button
              key={v.id}
              onClick={() => onSelectVersion(v)}
              className={`
                group relative w-full flex items-start gap-4 pl-7 pr-3 py-3 rounded-xl
                text-left transition-all duration-150 border
                ${
                  isActive
                    ? "bg-blue-600/15 border-blue-500/40 shadow-sm shadow-blue-900/30"
                    : "bg-transparent border-transparent hover:bg-slate-800/60 hover:border-slate-700"
                }
              `}
            >
              {/* Zaman çizelgesi noktası */}
              <span
                className={`
                  absolute left-[7px] top-4 w-[9px] h-[9px] rounded-full border-2 flex-shrink-0 z-10
                  ${
                    isActive
                      ? "bg-blue-500 border-blue-400"
                      : isLatest
                      ? "bg-emerald-500 border-emerald-400"
                      : "bg-slate-600 border-slate-500 group-hover:bg-slate-400"
                  }
                `}
              />
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span
                    className={`text-sm font-bold ${
                      isActive ? "text-blue-300" : "text-slate-200"
                    }`}
                  >
                    v{v.version_number}
                  </span>
                  {isLatest && (
                    <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-emerald-900/50 text-emerald-400 border border-emerald-700/50">
                      SON
                    </span>
                  )}
                  {v.parent_version_id && (
                    <span className="text-[10px] text-slate-500 font-mono">
                      ↑ dallanma
                    </span>
                  )}
                </div>
                <div className="text-xs text-slate-500 mt-0.5">
                  {dateStr}, {timeStr}
                </div>
                <div className="text-xs text-slate-500">
                  {v.word_count.toLocaleString("tr-TR")} kelime
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Alt bileşen: FeedbackForm
// ---------------------------------------------------------------------------

interface FeedbackFormProps {
  draftId: string;
  latestVersionNumber: number;
  onSuccess: (res: FeedbackResponse) => void;
}

function FeedbackForm({ draftId, latestVersionNumber, onSuccess }: FeedbackFormProps) {
  const [note, setNote] = useState("");
  const [authorLabel, setAuthorLabel] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const MIN_LENGTH = 5;
  const MAX_LENGTH = 4000;
  const remaining = MAX_LENGTH - note.length;
  const isValid = note.trim().length >= MIN_LENGTH && note.length <= MAX_LENGTH;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isValid || submitting) return;

    setSubmitting(true);
    setError(null);

    try {
      const { data } = await axios.post(
        `${API_BASE}/api/katip/drafts/${draftId}/regenerate`,
        {
          feedback_note: note.trim(),
          author_label: authorLabel.trim() || undefined,
        },
        {
          headers: {
            "Content-Type": "application/json",
            "X-Tenant-ID": getTenantId(),
          },
        }
      );
      setNote("");
      setAuthorLabel("");
      onSuccess({
        status: data.status,
        feedback_id: data.feedback_id,
        draft_id: draftId,
        source_version_number: data.new_version_number - 1,
        message: `v${data.new_version_number} taslak versiyonu LLM & RAG motoru ile başarıyla üretildi!`,
      });
    } catch (err) {
      const ae = err as AxiosError<{ detail: string }>;
      setError(
        ae.response?.data?.detail ??
          "Revizyon notu gönderilemedi. Lütfen tekrar deneyin."
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <label
          htmlFor="feedback-note"
          className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wide"
        >
          Revizyon Notu <span className="text-red-400">*</span>
        </label>
        <textarea
          id="feedback-note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={5}
          maxLength={MAX_LENGTH}
          placeholder={`v${latestVersionNumber} için revizyon talebinizi yazın…\n\nÖrn: "Giriş paragrafı çok teknik, daha sade bir dil kullanılsın. CTA butonu cümlesini güçlendir."`}
          className="
            w-full bg-slate-800/80 border border-slate-700 rounded-xl px-4 py-3
            text-sm text-slate-200 placeholder-slate-600
            focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50
            resize-none transition-colors
          "
        />
        <div className="flex justify-between mt-1">
          <span className="text-xs text-slate-600">
            Min. {MIN_LENGTH} karakter
          </span>
          <span
            className={`text-xs ${
              remaining < 200 ? "text-amber-400" : "text-slate-600"
            }`}
          >
            {remaining} karakter kaldı
          </span>
        </div>
      </div>

      <div>
        <label
          htmlFor="author-label"
          className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wide"
        >
          İmza (isteğe bağlı)
        </label>
        <input
          id="author-label"
          type="text"
          value={authorLabel}
          onChange={(e) => setAuthorLabel(e.target.value)}
          maxLength={100}
          placeholder="Editör adı veya departman"
          className="
            w-full bg-slate-800/80 border border-slate-700 rounded-xl px-4 py-2.5
            text-sm text-slate-200 placeholder-slate-600
            focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50
            transition-colors
          "
        />
      </div>

      {error && (
        <div className="flex items-start gap-2 bg-red-900/30 border border-red-800/50 rounded-xl px-4 py-3">
          <svg
            className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
            />
          </svg>
          <span className="text-xs text-red-300">{error}</span>
        </div>
      )}

      <button
        type="submit"
        disabled={!isValid || submitting}
        className="
          w-full py-3 rounded-xl text-sm font-semibold transition-all duration-200
          flex items-center justify-center gap-2
          bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-900/30
          disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none
          focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-slate-900
        "
      >
        {submitting ? (
          <>
            <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
            Gönderiliyor…
          </>
        ) : (
          <>
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Yeni Versiyon İste (v{latestVersionNumber + 1})
          </>
        )}
      </button>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Ana bileşen: DraftEditor
// ---------------------------------------------------------------------------

export default function DraftEditor() {
  const { draftId } = useParams<{ draftId: string }>();
  const [draft, setDraft] = useState<DraftDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Zaman çizelgesinde seçili versiyon — varsayılan: en son
  const [activeVersionId, setActiveVersionId] = useState<string | null>(null);
  // Görüntülenen içerik — seçili versiyona göre değişir
  const [displayedContent, setDisplayedContent] = useState<string>("");

  // Durum güncelleme
  const [statusUpdating, setStatusUpdating] = useState(false);

  // Başarı bildirimi
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // ---------------------------------------------------------------------------
  // Veri çekme
  // ---------------------------------------------------------------------------

  const fetchDraft = useCallback(async () => {
    if (!draftId) return;
    setLoading(true);
    setFetchError(null);

    try {
      const { data } = await axios.get<DraftDetail>(
        `${API_BASE}/api/katip/drafts/${draftId}`,
        {
          headers: { "X-Tenant-ID": getTenantId() },
        }
      );
      setDraft(data);

      // En son versiyonu varsayılan seç
      if (data.latest_version) {
        setActiveVersionId(data.latest_version.id);
        setDisplayedContent(data.latest_version.content);
      }
    } catch (err) {
      const ae = err as AxiosError<{ detail: string }>;
      setFetchError(
        ae.response?.data?.detail ?? "Taslak yüklenemedi. Sunucu hatası."
      );
    } finally {
      setLoading(false);
    }
  }, [draftId]);

  useEffect(() => {
    fetchDraft();
  }, [fetchDraft]);

  // ---------------------------------------------------------------------------
  // Versiyon seçimi — sadece içeriği değiştir (tam veri fetch etmez)
  // ---------------------------------------------------------------------------

  function handleSelectVersion(v: DraftVersionItem) {
    setActiveVersionId(v.id);
    if (v.content) {
      setDisplayedContent(v.content);
    } else if (draft?.latest_version?.id === v.id) {
      setDisplayedContent(draft.latest_version.content);
    } else {
      setDisplayedContent(
        `[v${v.version_number} içeriği yükleniyor...]\n\nOluşturulma Tarihi: ${new Date(v.created_at).toLocaleString("tr-TR")}\nKelime Sayısı: ${v.word_count.toLocaleString("tr-TR")}`
      );
    }
  }

  // ---------------------------------------------------------------------------
  // Durum güncelleme
  // ---------------------------------------------------------------------------

  async function handleStatusChange(newStatus: DraftStatus) {
    if (!draft || statusUpdating) return;
    setStatusUpdating(true);
    try {
      await axios.put(
        `${API_BASE}/api/katip/drafts/${draft.draft_id}/status`,
        { status: newStatus },
        { headers: { "X-Tenant-ID": getTenantId() } }
      );
      setDraft((prev) => (prev ? { ...prev, status: newStatus } : prev));
      setSuccessMessage(`Taslak durumu "${newStatus}" olarak güncellendi.`);
      setTimeout(() => setSuccessMessage(null), 3500);
    } catch {
      // Hata, kullanıcıya inline göster
    } finally {
      setStatusUpdating(false);
    }
  }

  // ---------------------------------------------------------------------------
  // Feedback başarı
  // ---------------------------------------------------------------------------

  function handleFeedbackSuccess(res: FeedbackResponse) {
    setSuccessMessage(res.message);
    setTimeout(() => setSuccessMessage(null), 5000);
    // Taslak durumunu güncelle ve veriyi yenile
    setDraft((prev) => (prev ? { ...prev, status: "draft" } : prev));
    fetchDraft();
  }

  // ---------------------------------------------------------------------------
  // Render: Yükleniyor
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-slate-400 text-sm">Taslak yükleniyor…</span>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render: Hata
  // ---------------------------------------------------------------------------

  if (fetchError || !draft) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-slate-900 border border-red-900/50 rounded-2xl p-8 text-center">
          <div className="w-14 h-14 bg-red-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-7 h-7 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
          <h2 className="text-white font-bold text-lg mb-2">Taslak Yüklenemedi</h2>
          <p className="text-slate-400 text-sm mb-6">{fetchError ?? "Bilinmeyen hata."}</p>
          <button
            onClick={fetchDraft}
            className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold rounded-xl transition-colors"
          >
            Tekrar Dene
          </button>
        </div>
      </div>
    );
  }

  const latestVersionNumber = draft.latest_version?.version_number ?? 0;

  // ---------------------------------------------------------------------------
  // Render: Ana sayfa
  // ---------------------------------------------------------------------------

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">

      {/* ── Başlık çubuğu ─────────────────────────────────────────────────── */}
      <header className="bg-slate-900 border-b border-slate-800 px-6 py-4 flex items-center justify-between gap-4 sticky top-0 z-20">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 bg-blue-600/15 border border-blue-500/30 rounded-lg flex items-center justify-center flex-shrink-0">
            <svg className="w-4 h-4 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
              />
            </svg>
          </div>
          <div className="min-w-0">
            <h1 className="text-white font-bold text-base leading-tight truncate">
              Taslak Düzenleyici
            </h1>
            <p className="text-slate-500 text-xs font-mono truncate">
              {draft.draft_id}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 flex-shrink-0">
          <StatusBadge status={draft.status} />

          {/* Approval Lock Actions */}
          {draft.status !== "approved" && draft.status !== "published" ? (
            <button
              onClick={() => handleStatusChange("approved")}
              disabled={statusUpdating}
              className="px-4 py-2 text-xs font-bold rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-900/30 border border-emerald-500/50 transition-all flex items-center gap-1.5 disabled:opacity-50"
            >
              <span>✓ Taslağı Onayla ve Tamamla</span>
            </button>
          ) : (
            <span className="text-xs text-emerald-400 font-semibold px-3 py-1 rounded-lg bg-emerald-950/60 border border-emerald-800">
              ✓ Onaylandı (Hafıza İşlendi)
            </span>
          )}

          {/* Copy Button (Approval Locked) */}
          <button
            onClick={() => {
              if (draft.status !== "approved" && draft.status !== "published") return;
              navigator.clipboard.writeText(displayedContent);
              setSuccessMessage("Metin panoya kopyalandı!");
              setTimeout(() => setSuccessMessage(null), 3000);
            }}
            disabled={draft.status !== "approved" && draft.status !== "published"}
            title={
              draft.status !== "approved" && draft.status !== "published"
                ? "Metni kopyalamak için önce taslağı onaylamalısınız."
                : "Metni Kopyala"
            }
            className={`px-3 py-2 text-xs font-semibold rounded-lg border transition-all flex items-center gap-1.5 ${
              draft.status === "approved" || draft.status === "published"
                ? "bg-slate-800 hover:bg-slate-700 text-slate-200 border-slate-700 cursor-pointer"
                : "bg-slate-900 text-slate-600 border-slate-800 opacity-50 cursor-not-allowed"
            }`}
          >
            <span>📋 Metni Kopyala</span>
          </button>

          {/* CMS Export Button (Approval Locked) */}
          <button
            onClick={() => {
              if (draft.status !== "approved" && draft.status !== "published") return;
              handleStatusChange("published");
            }}
            disabled={draft.status !== "approved" && draft.status !== "published"}
            title={
              draft.status !== "approved" && draft.status !== "published"
                ? "WordPress/CMS'e aktarmak için önce taslağı onaylamalısınız."
                : "WordPress / CMS'e Gönder"
            }
            className={`px-3 py-2 text-xs font-semibold rounded-lg border transition-all flex items-center gap-1.5 ${
              draft.status === "approved" || draft.status === "published"
                ? "bg-blue-600 hover:bg-blue-500 text-white border-blue-500 shadow-md shadow-blue-900/30 cursor-pointer"
                : "bg-slate-900 text-slate-600 border-slate-800 opacity-50 cursor-not-allowed"
            }`}
          >
            <span>🚀 CMS'e Gönder</span>
          </button>

          <button
            onClick={fetchDraft}
            disabled={loading}
            title="Yenile"
            className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors disabled:opacity-40"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
          </button>
        </div>
      </header>

      {/* ── Başarı bildirimi ──────────────────────────────────────────────── */}
      {successMessage && (
        <div className="mx-4 mt-3 flex items-center gap-3 bg-emerald-900/40 border border-emerald-700/50 rounded-xl px-4 py-3 animate-pulse">
          <svg className="w-4 h-4 text-emerald-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          <span className="text-emerald-300 text-sm">{successMessage}</span>
        </div>
      )}

      {/* ── Ana içerik: iki panel ─────────────────────────────────────────── */}
      <div className="flex flex-1 min-h-0 overflow-hidden">

        {/* ── SOL PANEL: Taslak metni ──────────────────────────────────── */}
        <main className="flex-1 flex flex-col overflow-y-auto border-r border-slate-800">

          {/* Meta bilgi şeridi */}
          <div className="flex items-center gap-6 px-6 py-3 bg-slate-900/50 border-b border-slate-800/60 flex-wrap">
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              {draft.latest_version?.word_count.toLocaleString("tr-TR") ?? "—"} kelime
            </div>
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {draft.latest_version
                ? new Date(draft.latest_version.created_at).toLocaleString("tr-TR")
                : "—"}
            </div>
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
              </svg>
              Konu #{draft.topic_id.slice(0, 8)}
            </div>
            {latestVersionNumber > 0 && (
              <div className="ml-auto">
                <span className="text-xs font-mono text-blue-400 bg-blue-900/30 border border-blue-800/50 px-2 py-0.5 rounded-md">
                  v{latestVersionNumber} görüntüleniyor
                </span>
              </div>
            )}
          </div>

          {/* Taslak içeriği */}
          <div className="flex-1 p-6 md:p-8 lg:p-10">
            {displayedContent ? (
              <article
                className="
                  prose prose-invert prose-slate max-w-none
                  prose-headings:font-bold prose-headings:text-slate-100 prose-headings:tracking-tight
                  prose-h1:text-2xl prose-h2:text-xl prose-h3:text-lg
                  prose-p:text-slate-300 prose-p:leading-relaxed
                  prose-a:text-blue-400 prose-a:underline hover:prose-a:text-blue-300
                  prose-strong:text-slate-100 prose-strong:font-semibold
                  prose-li:text-slate-300 prose-ul:list-disc prose-ol:list-decimal
                  prose-code:text-amber-300 prose-code:bg-slate-800 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded
                  select-text
                "
              >
                <ReactMarkdown>{displayedContent}</ReactMarkdown>
              </article>
            ) : (
              <div className="flex flex-col items-center justify-center h-64 gap-4">
                <div className="w-16 h-16 bg-slate-800 rounded-2xl flex items-center justify-center">
                  <svg className="w-8 h-8 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <p className="text-slate-500 text-sm">Bu taslak henüz içerik üretilmemiş.</p>
              </div>
            )}
          </div>
        </main>

        {/* ── SAĞ PANEL: Versiyon zaman çizelgesi + Feedback formu ─────── */}
        <aside className="w-[340px] flex-shrink-0 flex flex-col overflow-y-auto bg-slate-900/30">

          {/* Versiyon zaman çizelgesi */}
          <section className="border-b border-slate-800">
            <div className="px-5 py-4 flex items-center justify-between">
              <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Versiyon Geçmişi
              </h2>
              <span className="text-xs text-slate-600 font-mono">
                {draft.versions.length} versiyon
              </span>
            </div>
            <div className="px-5 pb-5">
              <VersionTimeline
                versions={draft.versions}
                activeVersionId={activeVersionId}
                onSelectVersion={handleSelectVersion}
              />
            </div>
          </section>

          {/* Feedback formu */}
          <section className="flex-1 px-5 py-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Revizyon İste
              </h2>
              {latestVersionNumber > 0 && (
                <span className="text-xs text-slate-600 font-mono">
                  v{latestVersionNumber} → v{latestVersionNumber + 1}
                </span>
              )}
            </div>

            {draft.status === "published" || draft.status === "archived" ? (
              <div className="bg-slate-800/50 border border-slate-700 rounded-xl px-4 py-4 text-center">
                <p className="text-slate-400 text-sm">
                  {draft.status === "published"
                    ? "Yayınlanmış taslaklar için revizyon istenemez."
                    : "Arşivlenmiş taslaklar için revizyon istenemez."}
                </p>
              </div>
            ) : latestVersionNumber === 0 ? (
              <div className="bg-slate-800/50 border border-slate-700 rounded-xl px-4 py-4 text-center">
                <p className="text-slate-400 text-sm">
                  Önce bir taslak versiyonu üretilmeli.
                </p>
              </div>
            ) : (
              <FeedbackForm
                draftId={draft.draft_id}
                latestVersionNumber={latestVersionNumber}
                onSuccess={handleFeedbackSuccess}
              />
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}
