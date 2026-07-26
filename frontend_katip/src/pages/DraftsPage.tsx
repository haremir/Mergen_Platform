/**
 * DraftsPage.tsx
 * ──────────────
 * Mergen Kâtip — Taslak Listesi ve Sektörel Filtreleme Sayfası
 */

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { getDraftsApi } from "../lib/api";

interface DraftListItem {
  draft_id: string;
  topic_id: string;
  topic_title?: string;
  tenant_id: string;
  brand_guide_id?: string | null;
  status: "draft" | "in_review" | "approved" | "published" | "archived";
  latest_version_number: number | null;
  created_at: string;
  updated_at: string;
}

interface DraftsPageProps {
  selectedProjectId: string;
}

export default function DraftsPage({ selectedProjectId }: DraftsPageProps) {
  const navigate = useNavigate();
  const [drafts, setDrafts] = useState<DraftListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const fetchDrafts = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getDraftsApi({
        brand_guide_id: selectedProjectId || undefined,
        draft_status: statusFilter !== "all" ? statusFilter : undefined,
      });
      setDrafts(data.items);
    } catch (err: any) {
      console.error("Drafts fetch error:", err);
    } finally {
      setLoading(false);
    }
  }, [selectedProjectId, statusFilter]);

  useEffect(() => {
    fetchDrafts();
  }, [fetchDrafts]);

  const draftStatusBadges: Record<string, { bg: string; text: string; label: string }> = {
    draft: { bg: "bg-slate-800 border-slate-700", text: "text-slate-300", label: "Taslak" },
    in_review: { bg: "bg-amber-950/60 border-amber-800/80", text: "text-amber-300", label: "İncelemede" },
    approved: { bg: "bg-emerald-950/60 border-emerald-800/80", text: "text-emerald-300", label: "Onaylandı" },
    published: { bg: "bg-blue-950/60 border-blue-800/80", text: "text-blue-300", label: "Yayınlandı" },
    archived: { bg: "bg-slate-900 border-slate-800", text: "text-slate-500", label: "Arşiv" },
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">Taslaklarım (Drafts)</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Üretilmiş tüm taslaklar, versiyon geçmişleri ve inceleme durumları.
          </p>
        </div>
      </div>

      {/* Filter Sub-bar */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        {[
          { id: "all", label: "Tüm Taslaklar" },
          { id: "draft", label: "Taslak (Yeni)" },
          { id: "in_review", label: "İncelemede (Revizyon)" },
          { id: "approved", label: "Onaylandı" },
          { id: "published", label: "Yayınlandı (CMS)" },
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

      {/* Drafts List */}
      {loading ? (
        <div className="py-12 text-center text-slate-500 text-sm">Taslaklar yükleniyor...</div>
      ) : drafts.length === 0 ? (
        <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-12 text-center space-y-3">
          <p className="text-slate-400 text-sm">Seçilen filtrede henüz taslak bulunmuyor.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {drafts.map((d) => {
            const st = draftStatusBadges[d.status] ?? draftStatusBadges.draft;
            return (
              <div
                key={d.draft_id}
                onClick={() => navigate(`/drafts/${d.draft_id}`)}
                className="bg-slate-900/80 border border-slate-800 hover:border-blue-500/50 rounded-2xl p-5 flex items-center justify-between gap-4 cursor-pointer transition-all hover:bg-slate-900"
              >
                <div className="space-y-1.5 min-w-0 flex-1">
                  <div className="flex items-center gap-2.5">
                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${st.bg} ${st.text}`}>
                      {st.label}
                    </span>
                    <span className="text-xs font-mono text-blue-400 bg-blue-950/60 px-2 py-0.5 rounded border border-blue-800/40">
                      Versiyon: v{d.latest_version_number ?? 1}
                    </span>
                  </div>

                  <h4 className="font-bold text-slate-100 text-base leading-snug">
                    {d.topic_title ?? `Taslak #${d.draft_id.slice(0, 8)}`}
                  </h4>

                  <div className="flex items-center gap-3 text-xs text-slate-500 font-mono">
                    <span>Taslak ID: {d.draft_id.slice(0, 8)}...</span>
                  </div>
                </div>

                <div className="flex items-center gap-4 shrink-0">
                  <div className="text-right">
                    <span className="text-xs text-slate-500 block">Son Güncelleme</span>
                    <span className="text-xs text-slate-300 font-medium">
                      {new Date(d.updated_at).toLocaleString("tr-TR")}
                    </span>
                  </div>

                  <div className="w-9 h-9 rounded-xl bg-slate-800 text-slate-300 hover:text-white flex items-center justify-center font-bold text-sm">
                    →
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
