import React from 'react';
import { HashRouter as Router, Routes, Route, Navigate, Link, useLocation, useNavigate } from 'react-router-dom';
import Onboarding from './pages/Onboarding';
import Dashboard from './pages/Dashboard';
import Settings from './pages/Settings';
import Analytics from './pages/Analytics';
import KatipOverview from './pages/KatipOverview';
import Login from './pages/Login';
import { getAdminToken, removeAdminToken } from './api';
import { Sparkles, LayoutDashboard, UserCheck, Code, Activity, Settings as SettingsGear, BarChart3, Users, LogOut } from 'lucide-react';

function AdminRoute({ children }: { children: React.ReactNode }) {
  const token = getAdminToken();
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();

  const isActive = (path: string) => {
    return location.pathname === path;
  };

  const handleLogout = () => {
    removeAdminToken();
    navigate('/login');
  };

  return (
    <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col justify-between shrink-0 h-screen sticky top-0">
      <div>
        {/* Brand Header */}
        <div className="h-20 flex items-center justify-between px-6 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-blue-600/10 border border-blue-500/30 rounded-xl flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-blue-500" />
            </div>
            <span className="font-bold text-lg text-white tracking-tight">
              Mergen Panel
            </span>
          </div>
        </div>

        {/* Navigation Section */}
        <nav className="p-4 space-y-1.5">
          <div className="px-3 mb-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Yönlendirme
          </div>
          
          <Link
            to="/onboarding"
            className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
              isActive('/onboarding')
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
                : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
            }`}
          >
            <UserCheck className="w-5 h-5" />
            Yeni Müşteri Kaydı
          </Link>

          <Link
            to="/dashboard"
            className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
              isActive('/dashboard')
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
                : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
            }`}
          >
            <LayoutDashboard className="w-5 h-5" />
            Kontrol Paneli
          </Link>

          <Link
            to="/bayiler"
            className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
              isActive('/bayiler') || isActive('/katip')
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
                : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
            }`}
          >
            <Users className="w-5 h-5" />
            Bayiler & Kâtip Denetimi
          </Link>

          <Link
            to="/analytics"
            className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
              isActive('/analytics')
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
                : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
            }`}
          >
            <BarChart3 className="w-5 h-5" />
            Analiz ve Performans
          </Link>

          <Link
            to="/settings"
            className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
              isActive('/settings')
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
                : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
            }`}
          >
            <SettingsGear className="w-5 h-5" />
            Sistem Ayarları
          </Link>
        </nav>
      </div>

      {/* Footer System Status & Logout */}
      <div className="p-4 border-t border-slate-800 space-y-3">
        <button
          onClick={handleLogout}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-red-950/40 hover:bg-red-900/60 text-red-300 border border-red-800/60 rounded-xl text-xs font-semibold transition-all"
        >
          <LogOut className="w-4 h-4" />
          Çıkış Yap
        </button>

        <div className="flex items-center justify-between text-xs text-slate-500 font-mono pt-1">
          <span className="flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5 text-emerald-500" />
            Sistem Aktif
          </span>
          <span className="flex items-center gap-1">
            <Code className="w-3 h-3" />
            v7.3.0
          </span>
        </div>
      </div>
    </aside>
  );
}

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        
        <Route
          path="*"
          element={
            <AdminRoute>
              <div className="min-h-screen bg-slate-950 flex font-sans">
                <Sidebar />
                <main className="flex-grow h-screen overflow-y-auto">
                  <Routes>
                    <Route path="/onboarding" element={<Onboarding />} />
                    <Route path="/dashboard" element={<Dashboard />} />
                    <Route path="/bayiler" element={<KatipOverview />} />
                    <Route path="/bayiler/:tenantId" element={<KatipOverview />} />
                    <Route path="/katip" element={<KatipOverview />} />
                    <Route path="/settings" element={<Settings />} />
                    <Route path="/analytics" element={<Analytics />} />
                    <Route path="*" element={<Navigate to="/dashboard" replace />} />
                  </Routes>
                </main>
              </div>
            </AdminRoute>
          }
        />
      </Routes>
    </Router>
  );
}
