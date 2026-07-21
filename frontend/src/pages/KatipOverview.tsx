import { useEffect, useState, useCallback } from 'react';
import { getTenants, getKatipTopics, getKatipDrafts } from '../api';
import type { TenantListEntry, KatipTopicSummary, KatipDraftSummary } from '../api';
import {
  FileText, Sparkles, Database, Layers, CheckCircle2,
  ExternalLink, RefreshCw, Cpu, Bot
} from 'lucide-react';

export default function KatipOverview() {
  const [tenants, setTenants] = useState<TenantListEntry[]>([]);
  const [selectedTenantId, setSelectedTenantId] = useState<string>('pilot-dental-clinic-01');
  const [loadingTenants, setLoadingTenants] = useState(false);

  const [topics, setTopics] = useState<KatipTopicSummary[]>([]);
  const [drafts, setDrafts] = useState<KatipDraftSummary[]>([]);
  const [loadingData, setLoadingData] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    async function loadTenants() {
      setLoadingTenants(true);
      try {
        const list = await getTenants();
        setTenants(list);
        if (list.length > 0 && !list.find(t => t.tenant_id === selectedTenantId)) {
          setSelectedTenantId(list[0].tenant_id);
        }
      } catch (err) {
        console.error('Failed to load tenants list:', err);
      } finally {
        setLoadingTenants(false);
      }
    }
    loadTenants();
  }, []);

  const loadKatipData = useCallback(async () => {
    if (!selectedTenantId) return;
    setLoadingData(true);
    setErrorMsg(null);
    try {
      const [topicsRes, draftsRes] = await Promise.all([
        getKatipTopics(selectedTenantId),
        getKatipDrafts(selectedTenantId),
      ]);
      setTopics(topicsRes.items);
      setDrafts(draftsRes.items);
    } catch (err: any) {
      console.error('Katip data error:', err);
      setErrorMsg(err.response?.data?.detail || 'Müşteri Kâtip verisi alınamadı.');
    } finally {
      setLoadingData(false);
    }
  }, [selectedTenantId]);

  useEffect(() => {
    loadKatipData();
  }, [loadKatipData]);

  const pendingTopicsCount = topics.filter(t => t.status === 'pending').length;
  const doneTopicsCount = topics.filter(t => t.status === 'done').length;

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto font-sans">
      {/* ── HEADER ───────────────────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900 border border-slate-800 p-6 rounded-2xl">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-900/30 shrink-0">
            <FileText className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-3">
              Mergen Kâtip Modülü
              <span className="text-xs font-mono px-2.5 py-0.5 rounded-full bg-blue-900/40 text-blue-400 border border-blue-800/60">
                AI Blog Generator
              </span>
            </h1>
            <p className="text-slate-400 text-sm mt-0.5">
              RAG & LLM Destekli YMYL Uyumlu Otomatik İçerik ve Taslak Motoru
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <a
            href="http://localhost:5174"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-semibold text-sm shadow-lg shadow-blue-900/30 transition-colors"
          >
            <ExternalLink className="w-4 h-4" />
            Kâtip Editör Web Uygulamasını Aç
          </a>
        </div>
      </div>

      {/* ── METRİKLER & SİSTEM DURUMU ──────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase">
            <span>Veritabanı & Vektör</span>
            <Database className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-xl font-bold text-white flex items-center gap-2">
            PostgreSQL + pgvector
          </div>
          <p className="text-xs text-slate-500">384-dim HNSW Semantik İndeks</p>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase">
            <span>LLM Gateway Motoru</span>
            <Bot className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-xl font-bold text-white">Qwen 2.5 32B</div>
          <p className="text-xs text-slate-500">English XML Guardrails Active</p>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase">
            <span>Bekleyen Konular</span>
            <Cpu className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-3xl font-extrabold text-amber-400">{pendingTopicsCount}</div>
          <p className="text-xs text-slate-500">Kuyrukta Üretim Bekliyor</p>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase">
            <span>Üretilen Taslaklar</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-3xl font-extrabold text-emerald-400">{drafts.length}</div>
          <p className="text-xs text-slate-500">Versiyonlama & Telemetri Kayıtlı</p>
        </div>
      </div>

      {/* ── MÜŞTERİ SEÇİCİ & DETAY TABLOSU ──────────────────────────────────── */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <Layers className="w-5 h-5 text-blue-400" />
            <h2 className="text-lg font-bold text-white">Müşteri Kâtip Paneli</h2>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-400">Müşteri Seç:</span>
            <select
              value={selectedTenantId}
              onChange={(e) => setSelectedTenantId(e.target.value)}
              disabled={loadingTenants}
              className="bg-slate-800 border border-slate-700 rounded-xl px-4 py-2 text-sm text-white font-mono focus:outline-none focus:border-blue-500"
            >
              <option value="pilot-dental-clinic-01">pilot-dental-clinic-01 (Pilot Diş Kliniği)</option>
              {tenants
                .filter(t => t.tenant_id !== 'pilot-dental-clinic-01')
                .map(t => (
                  <option key={t.tenant_id} value={t.tenant_id}>
                    {t.tenant_id} ({t.business_name})
                  </option>
                ))}
            </select>

            <button
              onClick={loadKatipData}
              disabled={loadingData}
              className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl transition-colors disabled:opacity-40"
            >
              <RefreshCw className={`w-4 h-4 ${loadingData ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {errorMsg && (
          <div className="p-4 bg-red-900/30 border border-red-800/50 rounded-xl text-red-300 text-sm">
            {errorMsg}
          </div>
        )}

        {/* IKI SÜTUNLU TABLO */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Konu Kuyruğu */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-slate-200 text-sm uppercase tracking-wider">
                Konu Kuyruğu ({topics.length})
              </h3>
              <span className="text-xs text-slate-500 font-mono">Status: pending / done</span>
            </div>

            {loadingData ? (
              <div className="py-8 text-center text-slate-500 text-sm">Yükleniyor...</div>
            ) : topics.length === 0 ? (
              <div className="p-6 bg-slate-950/60 border border-slate-800 rounded-xl text-center text-slate-500 text-sm">
                Kuyrukta henüz konu yok.
              </div>
            ) : (
              <div className="space-y-2">
                {topics.map((t) => (
                  <div
                    key={t.id}
                    className="p-3.5 bg-slate-950/60 border border-slate-800/80 rounded-xl flex items-center justify-between gap-3"
                  >
                    <div className="min-w-0">
                      <h4 className="font-semibold text-slate-200 text-sm truncate">{t.topic_title}</h4>
                      <p className="text-xs text-slate-500 font-mono">Öncelik: {t.priority}</p>
                    </div>
                    <span
                      className={`px-2.5 py-0.5 rounded-full text-xs font-mono ${
                        t.status === 'done'
                          ? 'bg-emerald-900/40 text-emerald-400 border border-emerald-800/50'
                          : 'bg-amber-900/40 text-amber-300 border border-amber-800/50'
                      }`}
                    >
                      {t.status}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Taslaklar */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-slate-200 text-sm uppercase tracking-wider">
                Üretilmiş Taslaklar ({drafts.length})
              </h3>
              <span className="text-xs text-slate-500 font-mono">Drafts & Versiyonlar</span>
            </div>

            {loadingData ? (
              <div className="py-8 text-center text-slate-500 text-sm">Yükleniyor...</div>
            ) : drafts.length === 0 ? (
              <div className="p-6 bg-slate-950/60 border border-slate-800 rounded-xl text-center text-slate-500 text-sm">
                Henüz taslak üretilmemiş.
              </div>
            ) : (
              <div className="space-y-2">
                {drafts.map((d) => (
                  <div
                    key={d.draft_id}
                    className="p-3.5 bg-slate-950/60 border border-slate-800/80 rounded-xl flex items-center justify-between gap-3"
                  >
                    <div className="min-w-0">
                      <h4 className="font-semibold text-slate-200 text-sm font-mono truncate">
                        Draft #{d.draft_id.slice(0, 8)}
                      </h4>
                      <p className="text-xs text-slate-500 font-mono">
                        {new Date(d.updated_at).toLocaleString('tr-TR')}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 bg-blue-900/40 text-blue-300 border border-blue-800/50 rounded text-xs font-mono">
                        v{d.latest_version_number ?? 1}
                      </span>
                      <span className="px-2 py-0.5 bg-slate-800 text-slate-300 rounded text-xs">
                        {d.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
