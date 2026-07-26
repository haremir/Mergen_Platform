/**
 * Sidebar.tsx
 * ───────────
 * Mergen Kâtip — Kalıcı Sol Navigasyon ve Proje/Sektör Seçici Barı
 */

import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { removeToken, createProjectApi } from "../lib/api";

export interface ProjectItem {
  id: string;
  tenant_id: string;
  brand_name: string;
  sector: string;
  is_default: boolean;
}

interface SidebarProps {
  projects: ProjectItem[];
  selectedProjectId: string;
  onSelectProject: (projectId: string) => void;
  onProjectCreated: () => void;
}

export default function Sidebar({
  projects,
  selectedProjectId,
  onSelectProject,
  onProjectCreated,
}: SidebarProps) {
  const navigate = useNavigate();
  const [showAddProjectModal, setShowAddProjectModal] = useState(false);
  const [newBrandName, setNewBrandName] = useState("");
  const [newSector, setNewSector] = useState("dental_clinic");
  const [submitting, setSubmitting] = useState(false);

  const selectedProject = projects.find((p) => p.id === selectedProjectId);

  const handleLogout = () => {
    removeToken();
    navigate("/login");
  };

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newBrandName.trim()) return;

    setSubmitting(true);
    try {
      const data = await createProjectApi({
        brand_name: newBrandName.trim(),
        sector: newSector,
      });
      setNewBrandName("");
      setShowAddProjectModal(false);
      onProjectCreated();
      onSelectProject(data.id);
    } catch (err: any) {
      alert(err.response?.data?.detail ?? "Proje eklenemedi.");
    } finally {
      setSubmitting(false);
    }
  };

  const sectorLabels: Record<string, { label: string; color: string }> = {
    dental_clinic: { label: "Diş Kliniği & Sağlık", color: "bg-teal-900/50 text-teal-300 border-teal-700/60" },
    real_estate: { label: "Gayrimenkul & İnşaat", color: "bg-amber-900/50 text-amber-300 border-amber-700/60" },
    legal: { label: "Hukuk & Danışmanlık", color: "bg-purple-900/50 text-purple-300 border-purple-700/60" },
    ecommerce: { label: "E-Ticaret & Perakende", color: "bg-pink-900/50 text-pink-300 border-pink-700/60" },
    health: { label: "Sağlık & Medikal", color: "bg-emerald-900/50 text-emerald-300 border-emerald-700/60" },
    tech: { label: "Teknoloji & Yazılım", color: "bg-blue-900/50 text-blue-300 border-blue-700/60" },
    general: { label: "Genel Sektör", color: "bg-slate-800 text-slate-300 border-slate-700" },
  };

  const currentSectorInfo = selectedProject
    ? sectorLabels[selectedProject.sector] ?? { label: selectedProject.sector, color: "bg-slate-800 text-slate-300 border-slate-700" }
    : sectorLabels["general"];

  return (
    <>
      <aside className="w-72 bg-slate-900 border-r border-slate-800 flex flex-col justify-between shrink-0 min-h-screen sticky top-0 h-screen overflow-y-auto">
        {/* Top Section */}
        <div className="p-5 space-y-6">
          {/* Logo & Brand */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-900/40 shrink-0">
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
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-900/60 text-blue-300 border border-blue-700/60 font-mono font-bold">
                  v2.0
                </span>
              </h1>
              <p className="text-slate-400 text-xs font-medium">Otonom İçerik Motoru</p>
            </div>
          </div>

          {/* Project / Brand Selector Card */}
          <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-3 space-y-2.5 shadow-inner">
            <div className="flex items-center justify-between">
              <span className="text-[11px] uppercase tracking-wider font-bold text-slate-400">
                Marka / Proje
              </span>
              <button
                onClick={() => setShowAddProjectModal(true)}
                className="text-[11px] text-blue-400 hover:text-blue-300 font-semibold hover:underline"
              >
                + Yeni Ekle
              </button>
            </div>

            <select
              value={selectedProjectId}
              onChange={(e) => onSelectProject(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-white font-bold focus:outline-none focus:border-blue-500 cursor-pointer"
            >
              <option value="">Tüm Markalar (Genel Bakış)</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.brand_name}
                </option>
              ))}
            </select>

            {/* Active Sector Badge */}
            <div className="flex items-center justify-between text-xs pt-1 border-t border-slate-800/80">
              <span className="text-slate-400 text-[11px]">Sektör:</span>
              <span
                className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${currentSectorInfo.color}`}
              >
                {currentSectorInfo.label}
              </span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="space-y-1">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all ${
                  isActive
                    ? "bg-blue-600 text-white shadow-lg shadow-blue-900/30"
                    : "text-slate-400 hover:bg-slate-800/70 hover:text-slate-200"
                }`
              }
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
                />
              </svg>
              <span>Genel Bakış (Dashboard)</span>
            </NavLink>

            <NavLink
              to="/topics"
              className={({ isActive }) =>
                `flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all ${
                  isActive
                    ? "bg-blue-600 text-white shadow-lg shadow-blue-900/30"
                    : "text-slate-400 hover:bg-slate-800/70 hover:text-slate-200"
                }`
              }
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 6h16M4 10h16M4 14h16M4 18h16"
                />
              </svg>
              <span>Konu Kuyruğu</span>
            </NavLink>

            <NavLink
              to="/drafts"
              className={({ isActive }) =>
                `flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all ${
                  isActive
                    ? "bg-blue-600 text-white shadow-lg shadow-blue-900/30"
                    : "text-slate-400 hover:bg-slate-800/70 hover:text-slate-200"
                }`
              }
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              <span>Taslaklarım</span>
            </NavLink>
          </nav>
        </div>

        {/* Footer / User & Logout */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/40 space-y-3">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-slate-300 font-medium truncate max-w-[130px]">
                {selectedProject?.brand_name ?? "Kâtip Bayisi"}
              </span>
            </div>
          </div>

          <button
            onClick={handleLogout}
            className="w-full px-3 py-2 bg-red-950/40 hover:bg-red-900/60 text-red-300 border border-red-900/50 rounded-xl text-xs font-semibold transition-all flex items-center justify-center gap-2"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            Çıkış Yap
          </button>
        </div>
      </aside>

      {/* New Project Modal */}
      {showAddProjectModal && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="font-bold text-lg text-white">Yeni Marka / Proje Ekle</h3>
              <button
                onClick={() => setShowAddProjectModal(false)}
                className="text-slate-400 hover:text-white text-lg"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateProject} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1 uppercase tracking-wider">
                  Marka / Proje Adı *
                </label>
                <input
                  type="text"
                  required
                  value={newBrandName}
                  onChange={(e) => setNewBrandName(e.target.value)}
                  placeholder="Örn. DentSmile Klinik veya Elite İnşaat"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1 uppercase tracking-wider">
                  Sektör Kategorisi *
                </label>
                <select
                  value={newSector}
                  onChange={(e) => setNewSector(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
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

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowAddProjectModal(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl text-sm font-semibold hover:bg-slate-700"
                >
                  İptal
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-bold shadow-lg shadow-blue-600/30 disabled:opacity-50"
                >
                  {submitting ? "Ekleniyor..." : "Proje Oluştur"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
